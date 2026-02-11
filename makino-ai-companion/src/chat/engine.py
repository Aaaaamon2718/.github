"""チャットエンジン本体。

Claude API（Anthropic SDK）を使用して回答を生成する。
RAGで取得したナレッジコンテキストとシステムプロンプトを組み合わせ、
牧野氏の人格を再現した回答を行う。
"""

import logging
import uuid
from dataclasses import dataclass
from typing import Optional

import anthropic

from src.chat.rag import KnowledgeLoader, SearchResult, SimpleRAG
from src.chat.vector_rag import create_rag
from src.prompts.system_prompts import build_system_prompt
from src.prompts.persona_config import PersonaConfig, load_persona_config

logger = logging.getLogger(__name__)


@dataclass
class ChatResponse:
    """チャットエンジンからの応答。"""

    answer: str
    sources: list[str]
    confidence: float
    should_escalate: bool
    escalation_reason: str
    tokens_used: int
    category: str


class ChatEngine:
    """Claude APIを使用したチャットエンジン。

    RAGによるナレッジ検索 + Claude APIでの回答生成を統合し、
    牧野氏の人格トレースを反映した応答を生成する。
    """

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-5-20250929",
        knowledge_dir: str = "knowledge",
        config_path: Optional[str] = None,
        max_tokens: int = 4096,
        vector_index_path: Optional[str] = None,
        use_vector_rag: bool = True,
    ) -> None:
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.max_tokens = max_tokens

        # 人格設定
        self.persona = load_persona_config(config_path)

        # ナレッジベース読み込み & RAGセットアップ
        loader = KnowledgeLoader(knowledge_dir)
        chunks = loader.load_all()
        self.rag = create_rag(
            chunks=chunks,
            index_path=vector_index_path,
            use_vector=use_vector_rag,
        )

        rag_type = type(self.rag).__name__
        logger.info(
            f"ChatEngine初期化完了: model={model}, "
            f"RAG={rag_type}, ナレッジ={len(chunks)}チャンク"
        )

    # エスカレーション必須カテゴリ
    ESCALATION_CATEGORIES = {
        "コンプライアンス関連",
        "個別顧客の契約内容",
        "具体的な保険料試算",
        "税務の最終判断",
    }

    def chat(
        self,
        question: str,
        pattern: int = 1,
        conversation_history: Optional[list[dict]] = None,
        temperature: Optional[float] = None,
        user_profile_context: Optional[str] = None,
    ) -> ChatResponse:
        """質問に対して回答を生成する。

        Args:
            question: ユーザーからの質問テキスト
            pattern: エージェントパターン番号 (1-4)
            conversation_history: 過去の会話履歴
            temperature: 生成温度（省略時はパターンのデフォルト）
            user_profile_context: ユーザープロファイルのプロンプト注入テキスト

        Returns:
            ChatResponse
        """
        # RAG検索（パターン別フィルタリング）
        search_results = self.rag.search(question, pattern=pattern)
        context = self.rag.format_context(search_results)
        sources = self.rag.get_sources(search_results)

        # エスカレーション判定
        should_escalate, escalation_reason = self._check_escalation(
            question, search_results
        )

        if should_escalate:
            return ChatResponse(
                answer=(
                    "この質問については、より正確にお答えするために"
                    "牧野に確認いたします。回答までしばらくお待ちください。"
                ),
                sources=sources,
                confidence=0.0,
                should_escalate=True,
                escalation_reason=escalation_reason,
                tokens_used=0,
                category=self._classify_question(question),
            )

        # システムプロンプト構築
        system_prompt = build_system_prompt(pattern, self.persona)
        system_prompt += f"\n\n## 参照ナレッジ\n{context}"

        # ユーザープロファイル注入（パーソナライズ）
        if user_profile_context:
            system_prompt += f"\n\n{user_profile_context}"

        # メッセージ構築
        messages: list[dict] = []
        if conversation_history:
            for entry in conversation_history[-10:]:  # 直近10件まで
                messages.append({"role": "user", "content": entry["question"]})
                messages.append({"role": "assistant", "content": entry["answer"]})
        messages.append({"role": "user", "content": question})

        # Claude API呼び出し
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=system_prompt,
                messages=messages,
                temperature=temperature,
            )

            answer = response.content[0].text
            tokens_used = (
                response.usage.input_tokens + response.usage.output_tokens
            )

        except anthropic.APIError as e:
            logger.error(f"Claude API エラー: {e}")
            return ChatResponse(
                answer="申し訳ありません。一時的にシステムに問題が発生しております。しばらく経ってから再度お試しください。",
                sources=[],
                confidence=0.0,
                should_escalate=False,
                escalation_reason="",
                tokens_used=0,
                category="システムエラー",
            )

        # 確信度の推定（RAG検索結果のスコアベース）
        confidence = self._estimate_confidence(search_results)

        return ChatResponse(
            answer=answer,
            sources=sources,
            confidence=confidence,
            should_escalate=False,
            escalation_reason="",
            tokens_used=tokens_used,
            category=self._classify_question(question),
        )

    def _check_escalation(
        self,
        question: str,
        search_results: list[SearchResult],
    ) -> tuple[bool, str]:
        """エスカレーション要否を判定する。"""
        # カテゴリベースの強制エスカレーション
        for cat in self.ESCALATION_CATEGORIES:
            if cat.replace("関連", "") in question:
                return True, f"強制エスカレーションカテゴリ: {cat}"

        # 検索結果なし（ナレッジ不足）
        if not search_results:
            return True, "関連ナレッジが見つかりません"

        # 確信度ベースのエスカレーション
        confidence = self._estimate_confidence(search_results)
        if confidence < 0.3:
            return True, f"確信度が低い: {confidence:.2f}"

        return False, ""

    def _estimate_confidence(self, search_results: list[SearchResult]) -> float:
        """検索結果から確信度を推定する。"""
        if not search_results:
            return 0.0
        avg_score = sum(r.score for r in search_results) / len(search_results)
        return min(avg_score, 1.0)

    def _classify_question(self, question: str) -> str:
        """質問を簡易分類する。"""
        keywords = {
            "法人保険": ["法人", "会社", "経営", "企業"],
            "ドクターマーケット": ["ドクター", "医師", "医療", "開業医", "クリニック"],
            "決算書分析": ["決算", "P/L", "B/S", "貸借", "損益"],
            "退職金設計": ["退職金", "退職"],
            "事業承継": ["承継", "後継者"],
            "相続": ["相続", "遺産"],
            "営業マインド": ["辛い", "落ち込", "やる気", "モチベ", "悩み"],
        }
        for category, words in keywords.items():
            if any(w in question for w in words):
                return category
        return "一般"

    def generate_session_id(self) -> str:
        """新しいセッションIDを生成する。"""
        return str(uuid.uuid4())[:8]
