"""FastAPIのルーティング定義。

チャットAPI、フィードバックAPI、管理APIを提供する。
フロントエンドのチャットUIおよび将来のウィジェット埋め込みから呼び出される。
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.chat.engine import ChatEngine
from src.database.operations import (
    calculate_metrics,
    get_conversation_history,
    get_pattern_breakdown,
    save_conversation,
    save_escalation,
    save_feedback,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# --- リクエスト/レスポンスモデル ---

class ChatRequest(BaseModel):
    """チャットリクエスト。"""

    question: str = Field(..., min_length=1, max_length=5000)
    pattern: int = Field(default=1, ge=1, le=4)
    session_id: Optional[str] = None
    user_id: str = Field(default="anonymous")


class ChatResponseModel(BaseModel):
    """チャットレスポンス。"""

    answer: str
    sources: list[str]
    confidence: float
    session_id: str
    conversation_id: int
    escalated: bool


class FeedbackRequest(BaseModel):
    """フィードバックリクエスト。"""

    conversation_id: int
    rating: str = Field(..., pattern="^(good|bad)$")
    comment: str = ""


class GuideSuggestionsRequest(BaseModel):
    """質問ナビのAI生成サブトピックリクエスト。"""

    pattern: int = Field(..., ge=1, le=4)
    category: str = Field(..., min_length=1, max_length=200)


class GuideSuggestionsResponse(BaseModel):
    """質問ナビのAI生成サブトピックレスポンス。"""

    suggestions: list[str]


class MetricsResponse(BaseModel):
    """KPIメトリクスレスポンス。"""

    total_questions: int
    answer_success_rate: float
    average_confidence: float
    escalation_count: int
    escalation_rate: float
    user_satisfaction: float
    feedback_count: int


# --- エンドポイント ---

def create_routes(engine: ChatEngine, db_conn) -> APIRouter:
    """ルーターを生成する。

    Args:
        engine: チャットエンジンインスタンス
        db_conn: データベース接続

    Returns:
        設定済みAPIRouter
    """

    @router.post("/api/chat", response_model=ChatResponseModel)
    async def chat(request: ChatRequest) -> ChatResponseModel:
        """チャットエンドポイント。質問を受け取り回答を返す。"""
        session_id = request.session_id or engine.generate_session_id()

        # 会話履歴取得
        history = get_conversation_history(db_conn, session_id)

        # 回答生成
        response = engine.chat(
            question=request.question,
            pattern=request.pattern,
            conversation_history=history,
        )

        # DB保存
        conv_id = save_conversation(
            conn=db_conn,
            session_id=session_id,
            user_id=request.user_id,
            bot_pattern=f"pattern_{request.pattern}",
            question=request.question,
            answer=response.answer,
            sources_used=response.sources,
            confidence=response.confidence,
            escalated=response.should_escalate,
            category=response.category,
            tokens_used=response.tokens_used,
        )

        # エスカレーション保存
        if response.should_escalate:
            save_escalation(db_conn, conv_id, response.escalation_reason)

        return ChatResponseModel(
            answer=response.answer,
            sources=response.sources,
            confidence=response.confidence,
            session_id=session_id,
            conversation_id=conv_id,
            escalated=response.should_escalate,
        )

    @router.post("/api/feedback")
    async def feedback(request: FeedbackRequest) -> dict:
        """フィードバックエンドポイント。ユーザー評価を記録する。"""
        fb_id = save_feedback(
            conn=db_conn,
            conversation_id=request.conversation_id,
            rating=request.rating,
            comment=request.comment,
        )
        return {"status": "ok", "feedback_id": fb_id}

    @router.get("/api/metrics", response_model=MetricsResponse)
    async def metrics(
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> MetricsResponse:
        """KPIメトリクスエンドポイント。"""
        data = calculate_metrics(db_conn, date_from, date_to)
        return MetricsResponse(**data)

    @router.get("/api/metrics/patterns")
    async def pattern_metrics(
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> dict:
        """パターン別メトリクスエンドポイント。"""
        return get_pattern_breakdown(db_conn, date_from, date_to)

    @router.post("/api/guide/suggestions", response_model=GuideSuggestionsResponse)
    async def guide_suggestions(request: GuideSuggestionsRequest) -> GuideSuggestionsResponse:
        """質問ナビ用のAI生成サブトピックを返す。

        選択されたパターンとカテゴリに基づき、
        ユーザーが質問しやすいサブトピックの選択肢をAIで生成する。
        """
        pattern_names = {
            1: "生命保険全般の質問対応",
            2: "ドクターマーケット特化",
            3: "法人保険特化",
            4: "励まし・メンタリング",
        }
        pattern_name = pattern_names.get(request.pattern, "汎用")

        prompt = (
            f"あなたは生命保険営業のコンサルタントです。\n"
            f"エージェントパターン「{pattern_name}」で、"
            f"カテゴリ「{request.category}」に関して、\n"
            f"営業担当者がよく質問するサブトピックを6つ、短いフレーズで列挙してください。\n"
            f"各項目は簡潔に（10文字〜20文字程度）。\n"
            f"JSON配列形式で出力してください。例: [\"項目1\", \"項目2\", ...]\n"
            f"JSON配列のみを出力し、他のテキストは含めないでください。"
        )

        try:
            response = engine.client.messages.create(
                model=engine.model,
                max_tokens=256,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
            )
            import json
            text = response.content[0].text.strip()
            suggestions = json.loads(text)
            if isinstance(suggestions, list) and all(isinstance(s, str) for s in suggestions):
                return GuideSuggestionsResponse(suggestions=suggestions[:8])
        except Exception as e:
            logger.warning(f"質問ナビAI生成エラー: {e}")

        return GuideSuggestionsResponse(suggestions=[])

    @router.get("/api/health")
    async def health() -> dict:
        """ヘルスチェック。"""
        return {"status": "ok", "model": engine.model}

    return router
