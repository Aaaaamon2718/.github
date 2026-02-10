"""Claudeによるナレッジコンテンツの分析・ラベリング・構造化。

抽出されたテキストをClaude APIに送り、以下の3段階パイプラインで最高精度の
ラベリングを実現する:

  Pass 1: カテゴリ分類（ドメイン知識を注入した専門分類）
  Pass 2: 構造化・Q&A抽出（セクション分割、QAペア生成）
  Pass 3: 品質検証（分類の妥当性をクロスチェック）

生命保険営業ドメインの専門用語辞書による表記統一も行う。
"""

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import anthropic

from src.knowledge_base.media_processor import (
    ExtractedContent,
    encode_image_base64,
    get_image_media_type,
)

logger = logging.getLogger(__name__)


# =============================================================================
# ドメイン定義（labeling-schema.md 完全準拠）
# =============================================================================

VALID_CATEGORIES = [
    "法人保険", "ドクターマーケット", "相続",
    "営業マインド", "営業スキル", "コンプライアンス",
]

# カテゴリ → サブカテゴリの全量マッピング
SUBCATEGORY_MAP: dict[str, list[str]] = {
    "法人保険": [
        "決算書分析", "退職金設計", "事業承継", "節税対策", "資金繰り",
        "役員報酬", "福利厚生", "損害保険連携", "法人契約全般",
    ],
    "ドクターマーケット": [
        "医療法人設立", "個人開業医", "MS法人", "医師賠償",
        "医療法人の事業承継", "勤務医対策", "開業資金",
    ],
    "相続": [
        "相続税対策", "資産承継", "遺言・信託", "納税資金準備",
        "自社株対策", "不動産対策", "二次相続",
    ],
    "営業マインド": [
        "プロ意識", "モチベーション", "目標設定", "自己投資",
        "時間管理", "人間力", "成功哲学",
    ],
    "営業スキル": [
        "アプローチ", "クロージング", "紹介入手", "話法",
        "ヒアリング", "プレゼンテーション", "反対処理", "電話営業",
    ],
    "コンプライアンス": [
        "募集規制", "個人情報保護", "適合性原則", "比較説明",
        "意向把握", "クーリングオフ", "保険業法",
    ],
}

VALID_PRIORITIES = ["高", "中", "低"]

VALID_EMOTION_TAGS = [
    "励まし", "叱咤", "論理的解説", "共感", "雑談/アイスブレイク", "情熱",
]

VALID_EXPRESSION_TAGS = [
    "断定", "比喩表現", "関西弁", "厳しい指摘", "問いかけ", "ユーモア",
]

# ファイル種別 → ID prefix
ID_PREFIX_MAP = {
    "video": "VID",
    "audio": "AUD",
    "pdf": "BK",
    "docx": "ML",
    "text": "ML",
    "image": "PR",
}

# ID prefix → knowledge/ 配下のサブディレクトリ
KNOWLEDGE_DIR_MAP = {
    "VID": "seminars",
    "AUD": "trainings",
    "QA": "qa",
    "ML": "articles",
    "BK": "articles",
    "TL": "sales_tools",
    "NL": "articles",
    "PR": "sales_tools",
}


# =============================================================================
# 生命保険営業 専門用語 表記統一辞書
# =============================================================================

TERMINOLOGY_NORMALIZATION: dict[str, str] = {
    # 表記揺れ → 正規表記
    "けっさんしょ": "決算書",
    "たいしょくきん": "退職金",
    "じぎょうしょうけい": "事業承継",
    "そうぞく": "相続",
    "ほうじんほけん": "法人保険",
    "いりょうほうじん": "医療法人",
    "ドクターマーケット": "ドクターマーケット",
    "ドクター・マーケット": "ドクターマーケット",
    "Doctor Market": "ドクターマーケット",
    "Ｐ／Ｌ": "P/L",
    "Ｂ／Ｓ": "B/S",
    "P&L": "P/L",
    "PL": "P/L",
    "BS": "B/S",
    "損益計算書": "P/L（損益計算書）",
    "貸借対照表": "B/S（貸借対照表）",
    "クロージング": "クロージング",
    "クロウジング": "クロージング",
    "アポ": "アポイント",
    "アポイントメント": "アポイント",
    "プレゼン": "プレゼンテーション",
    "コンプラ": "コンプライアンス",
    "MS法人": "MS法人（メディカルサービス法人）",
    "エムエス法人": "MS法人（メディカルサービス法人）",
}


# =============================================================================
# Pass 1: カテゴリ分類プロンプト
# =============================================================================

PASS1_CLASSIFICATION_PROMPT = """あなたは「牧野生保塾」の教材データを分類する専門AIです。
牧野克彦氏は生命保険営業のカリスマ講師で、以下の分野を専門としています。

## あなたの分類知識

### カテゴリとサブカテゴリの全量定義:

**法人保険**（法人向け保険商品・財務対策全般）:
  → 決算書分析, 退職金設計, 事業承継, 節税対策, 資金繰り, 役員報酬, 福利厚生, 損害保険連携, 法人契約全般
  判定キーワード: 法人, 社長, 経営者, 決算, B/S, P/L, 損金, 益金, 退職慰労金, 役員, 事業保障

**ドクターマーケット**（医師・医療法人向け）:
  → 医療法人設立, 個人開業医, MS法人, 医師賠償, 医療法人の事業承継, 勤務医対策, 開業資金
  判定キーワード: 医師, ドクター, 医療法人, 開業, MS法人, 病院, クリニック, 勤務医, 医師賠償

**相続**（相続対策・資産承継）:
  → 相続税対策, 資産承継, 遺言・信託, 納税資金準備, 自社株対策, 不動産対策, 二次相続
  判定キーワード: 相続, 遺言, 資産, 承継, 自社株, 納税, 贈与, 信託, 相続税

**営業マインド**（精神論・哲学・動機づけ）:
  → プロ意識, モチベーション, 目標設定, 自己投資, 時間管理, 人間力, 成功哲学
  判定キーワード: 心構え, 覚悟, プロ, 努力, 成功, 目標, 信念, 哲学, 人間力, 自分を変える

**営業スキル**（具体的な営業テクニック）:
  → アプローチ, クロージング, 紹介入手, 話法, ヒアリング, プレゼンテーション, 反対処理, 電話営業
  判定キーワード: トーク, 話法, アプローチ, クロージング, 紹介, ヒアリング, ニーズ喚起, 反対処理

**コンプライアンス**（法令遵守・リスク管理）:
  → 募集規制, 個人情報保護, 適合性原則, 比較説明, 意向把握, クーリングオフ, 保険業法
  判定キーワード: 法令, コンプライアンス, 規制, 個人情報, 適合性, 保険業法, 募集

### 分類の注意事項:
- 複数カテゴリにまたがる場合は「最も中心的なテーマ」を選ぶ
- 事業承継は文脈で判断: 法人の事業承継→法人保険、医療法人の事業承継→ドクターマーケット、個人資産の承継→相続
- 営業マインドとスキルの境界: 具体的手法があればスキル、精神論ならマインド
- 判断に迷う場合はconfidenceを下げて正直に報告する

### 優先度の判定基準:
- **高**: 牧野氏が繰り返し強調する内容、鉄板トーク、代表的エピソード、頻出質問への回答
- **中**: 補足的な知識、応用的な内容、特定場面でのみ使う話法
- **低**: 稀な事例、背景情報、一般的な業界知識

### 感情タグ（該当するものすべて選択）:
- 励まし: 前向きな力を与える発言（「大丈夫」「できる」「信じろ」）
- 叱咤: 厳しい指摘（「甘い」「プロなら」「言い訳するな」）
- 論理的解説: 客観的・体系的な説明（数値、根拠、理論）
- 共感: 相手に寄り添う（「わかる」「つらいよな」）
- 雑談/アイスブレイク: 軽い話題、冗談
- 情熱: 熱い想い（「命懸け」「人生を変える」）

### 言い回しタグ（該当するものすべて選択）:
- 断定: 「間違いない」「絶対に」「これしかない」
- 比喩表現: たとえ話を使った説明
- 関西弁: 「〜やないですか」「〜やで」
- 厳しい指摘: 容赦ない直言
- 問いかけ: 「本当にそれでいいのか？」形式
- ユーモア: 笑いを交えた表現

## 分析対象テキスト:

{text}

## 出力（厳密にこのJSON構造で出力。JSON以外の文字は一切不要）:

```json
{{
  "category": "カテゴリ名（上記6つのいずれか）",
  "sub_category": "サブカテゴリ名（上記の定義リストから選択）",
  "priority": "高|中|低",
  "emotion_tags": ["該当するタグ"],
  "expression_tags": ["該当するタグ"],
  "title": "コンテンツの適切なタイトル（30文字以内）",
  "summary": "内容の要約（50文字以内）",
  "confidence": 0.85,
  "reasoning": "このカテゴリ・サブカテゴリに分類した理由（簡潔に）"
}}
```"""


# =============================================================================
# Pass 2: 構造化・Q&A抽出プロンプト
# =============================================================================

PASS2_STRUCTURING_PROMPT = """あなたは生命保険営業の教材を構造化するエキスパートです。
以下のテキストを分析し、2つの処理を行ってください。

## 処理1: セクション分割

テキストを論理的なセクションに分割してください。
- 話題の転換点で区切る
- 各セクションに適切な見出しをつける
- セクション内の原文は意味を変えずに保持する
- 最低1セクション、多くても8セクション以内

## 処理2: Q&Aペア抽出

テキストから教育的なQ&Aペアを抽出してください。
- 明示的な質問と回答がある場合はそのまま抽出
- 暗黙的にQ&A形式に変換できる部分も抽出（例: 「〜の場合はどうするか。答えは〜」）
- 生命保険営業の実務で使える形にする
- 質問は具体的に、回答は牧野氏の言葉を尊重する
- Q&Aが抽出できない内容の場合は空配列で良い

## テキスト（カテゴリ: {category} / サブカテゴリ: {sub_category}）:

{text}

## 出力（厳密にこのJSON構造で出力。JSON以外の文字は一切不要）:

```json
{{
  "sections": [
    {{"heading": "セクション見出し", "content": "セクション本文（原文ベース）"}}
  ],
  "qa_pairs": [
    {{"question": "具体的な質問文", "answer": "牧野氏の言葉に基づく回答"}}
  ]
}}
```"""


# =============================================================================
# Pass 3: 品質検証プロンプト
# =============================================================================

PASS3_VERIFICATION_PROMPT = """あなたは品質管理の専門家です。
以下のコンテンツ分析結果を検証してください。

## 検証項目:
1. カテゴリ分類は適切か？（テキスト内容と一致するか）
2. サブカテゴリは妥当か？
3. 優先度は適切か？
4. タグは過不足ないか？
5. タイトル・要約は内容を正確に表しているか？

## 元テキスト（冒頭2000文字）:

{text_preview}

## 分析結果:

カテゴリ: {category}
サブカテゴリ: {sub_category}
優先度: {priority}
タイトル: {title}
要約: {summary}
感情タグ: {emotion_tags}
言い回しタグ: {expression_tags}

## 検証結果を以下のJSON形式で（JSON以外の文字は一切不要）:

```json
{{
  "is_valid": true,
  "corrections": {{
    "category": "修正が必要なら正しいカテゴリ（不要ならnull）",
    "sub_category": "修正が必要なら正しいサブカテゴリ（不要ならnull）",
    "priority": "修正が必要なら正しい優先度（不要ならnull）",
    "title": "修正が必要なら正しいタイトル（不要ならnull）",
    "summary": "修正が必要なら正しい要約（不要ならnull）"
  }},
  "quality_score": 0.9,
  "issues": ["検出された問題点があれば記載"]
}}
```"""


# =============================================================================
# 画像・文字起こし用プロンプト
# =============================================================================

IMAGE_DESCRIPTION_PROMPT = """この画像は「牧野生保塾」の教材・セミナー資料です。
生命保険営業の教育という文脈で、画像の内容を日本語で正確かつ詳細に記述してください。

## 記述ルール:

### 図表の場合:
- 表のヘッダーとデータを正確にテキスト化（Markdown表形式）
- 数値は1桁の誤りも許さない
- 単位を明記する（万円、%、件など）

### グラフの場合:
- グラフの種類（棒、折れ線、円グラフ等）
- 軸ラベルと範囲
- 具体的な数値（読み取れる範囲で）
- データの傾向・特徴

### スライドの場合:
- タイトル
- 箇条書きを階層構造で再現
- 強調されているテキスト（色付き、太字、下線）を明記
- レイアウトの論理的構造を保持

### 写真・イラストの場合:
- 何が写っているか
- 営業教材としてのコンテキストを推測
- テキストが含まれていれば正確に読み取る

Markdown形式で出力。"""


TRANSCRIPT_CLEANUP_PROMPT = """以下は牧野生保塾セミナーの文字起こしテキストです。
最高品質の教材テキストに整理してください。

## 整理ルール（優先順位順）:

### 1. 絶対ルール（違反不可）:
- 牧野氏の発言の意図・ニュアンス・独特の言い回しは一切変えない
- 専門的な内容の正確性は100%維持する
- 数値・固有名詞は原文のまま

### 2. フィラー除去:
- 「えー」「あのー」「まあ」「えっと」「うーん」→ 除去
- 「〜ですね、〜ですね」の連続 → 1回にまとめる
- ただし、間を取る意味のある「…」は保持

### 3. 段落分割:
- 話題の転換点で段落を分ける
- 1段落は3〜6文を目安にする
- 長い説明は論理的な区切りで分割

### 4. 表記統一:
- ほけん → 保険
- けっさんしょ → 決算書
- P/L, B/S は半角英字で統一
- 数値は算用数字に統一（百万円 → 100万円）

### 5. 強調:
- 牧野氏が声を強めたり繰り返した部分 → **太字**
- 重要な格言・教訓 → > 引用ブロック

### 6. 構造化:
- 列挙は箇条書きにする
- ステップ説明は番号付きリストにする

## 文字起こしテキスト:

{text}

## 出力（整理後のテキストのみ。説明・注釈は不要）:
"""


# =============================================================================
# データクラス
# =============================================================================

@dataclass
class AnalysisResult:
    """Claude分析の最終結果。3パス分析を経た高精度データ。"""

    source_path: str
    file_type: str
    category: str = ""
    sub_category: str = ""
    priority: str = "中"
    emotion_tags: list[str] = field(default_factory=list)
    expression_tags: list[str] = field(default_factory=list)
    title: str = ""
    summary: str = ""
    qa_pairs: list[dict] = field(default_factory=list)
    sections: list[dict] = field(default_factory=list)
    confidence: float = 0.0
    quality_score: float = 0.0
    full_text: str = ""
    image_descriptions: list[str] = field(default_factory=list)
    id_prefix: str = ""
    knowledge_dir: str = ""
    needs_manual_review: bool = False
    review_reasons: list[str] = field(default_factory=list)
    error: str = ""


# =============================================================================
# 分析エンジン
# =============================================================================

class ContentAnalyzer:
    """3パス分析による最高精度のコンテンツ分析エンジン。

    Pass 1: カテゴリ分類（ドメイン知識注入）
    Pass 2: 構造化・Q&A抽出
    Pass 3: 品質検証（クロスチェック）
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-sonnet-4-5-20250929",
        max_concurrent: int = 5,
        retry_count: int = 3,
        verification_enabled: bool = True,
    ) -> None:
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.retry_count = retry_count
        self.verification_enabled = verification_enabled

    async def analyze(self, content: ExtractedContent) -> AnalysisResult:
        """3パス分析を実行する。"""
        async with self.semaphore:
            return await self._analyze_internal(content)

    async def _analyze_internal(self, content: ExtractedContent) -> AnalysisResult:
        """セマフォ内で実行される分析本体。"""
        result = AnalysisResult(
            source_path=content.source_path,
            file_type=content.file_type,
        )

        try:
            # === 前処理: メディア変換 ===
            text = await self._preprocess(content, result)
            if not text or len(text.strip()) < 30:
                result.error = "テキスト抽出結果が不十分（30文字未満）"
                result.needs_manual_review = True
                result.review_reasons.append("テキスト不足")
                return result

            # 表記統一を適用
            text = self._normalize_terminology(text)
            result.full_text = text

            # === Pass 1: カテゴリ分類 ===
            logger.info(f"[Pass1] 分類開始: {Path(content.source_path).name}")
            classification = await self._pass1_classify(text)
            result.category = classification.get("category", "")
            result.sub_category = classification.get("sub_category", "")
            result.priority = classification.get("priority", "中")
            result.emotion_tags = classification.get("emotion_tags", [])
            result.expression_tags = classification.get("expression_tags", [])
            result.title = classification.get("title", "")
            result.summary = classification.get("summary", "")
            result.confidence = classification.get("confidence", 0.0)

            # カテゴリ・タグのバリデーション（即時修正）
            self._validate_and_fix_labels(result)

            # === Pass 2: 構造化・Q&A抽出 ===
            logger.info(f"[Pass2] 構造化開始: {Path(content.source_path).name}")
            structure = await self._pass2_structure(text, result.category, result.sub_category)
            result.sections = structure.get("sections", [])
            result.qa_pairs = structure.get("qa_pairs", [])

            # セクションが空なら全文を1セクションにする
            if not result.sections:
                result.sections = [{"heading": result.title or "内容", "content": text[:3000]}]

            # === Pass 3: 品質検証 ===
            if self.verification_enabled and result.confidence < 0.95:
                logger.info(f"[Pass3] 品質検証開始: {Path(content.source_path).name}")
                verification = await self._pass3_verify(text, result)
                result.quality_score = verification.get("quality_score", 0.0)

                # 検証で修正が必要な場合は適用
                corrections = verification.get("corrections", {})
                if corrections.get("category") and corrections["category"] in VALID_CATEGORIES:
                    logger.info(f"  検証修正: カテゴリ {result.category} → {corrections['category']}")
                    result.category = corrections["category"]
                if corrections.get("sub_category"):
                    result.sub_category = corrections["sub_category"]
                if corrections.get("priority") and corrections["priority"] in VALID_PRIORITIES:
                    result.priority = corrections["priority"]
                if corrections.get("title"):
                    result.title = corrections["title"]
                if corrections.get("summary"):
                    result.summary = corrections["summary"]

                issues = verification.get("issues", [])
                if issues:
                    result.review_reasons.extend(issues)
            else:
                result.quality_score = result.confidence

            # === 後処理: ID prefix・格納先決定・最終判定 ===
            result.id_prefix = ID_PREFIX_MAP.get(content.file_type, "ML")
            result.knowledge_dir = KNOWLEDGE_DIR_MAP.get(result.id_prefix, "articles")

            # 手動レビュー判定
            if result.confidence < 0.6:
                result.needs_manual_review = True
                result.review_reasons.append(f"分類confidence低 ({result.confidence:.2f})")
            if result.quality_score < 0.6 and result.quality_score > 0:
                result.needs_manual_review = True
                result.review_reasons.append(f"品質スコア低 ({result.quality_score:.2f})")

            logger.info(
                f"[完了] {Path(content.source_path).name}: "
                f"{result.category}/{result.sub_category} "
                f"(conf={result.confidence:.2f}, quality={result.quality_score:.2f})"
                f"{' ★要レビュー' if result.needs_manual_review else ''}"
            )

        except Exception as e:
            logger.error(f"分析エラー {content.source_path}: {e}", exc_info=True)
            result.error = str(e)
            result.needs_manual_review = True
            result.review_reasons.append(f"例外: {e}")

        return result

    # =========================================================================
    # 前処理
    # =========================================================================

    async def _preprocess(self, content: ExtractedContent, result: AnalysisResult) -> str:
        """メディアファイルの前処理（画像記述・文字起こし整形）。"""
        text = content.text

        # 画像がある場合はClaude Visionで記述
        image_texts = await self._describe_images(content)
        result.image_descriptions = image_texts

        # 動画/音声の文字起こし整形
        if content.file_type in ("video", "audio") and text and len(text) > 100:
            text = await self._cleanup_transcript(text)

        # 画像記述を本文に追加
        if image_texts:
            text += "\n\n## 教材内の図表・画像\n\n"
            text += "\n\n---\n\n".join(image_texts)

        # 画像のみファイル
        if content.file_type == "image" and not text.strip():
            source_path = Path(content.source_path)
            text = await self._describe_single_image(source_path)

        return text

    def _normalize_terminology(self, text: str) -> str:
        """生保専門用語の表記を統一する。"""
        for wrong, correct in TERMINOLOGY_NORMALIZATION.items():
            text = text.replace(wrong, correct)
        return text

    # =========================================================================
    # Pass 1: カテゴリ分類
    # =========================================================================

    async def _pass1_classify(self, text: str) -> dict:
        """ドメイン知識を注入した専門分類。"""
        truncated = text[:8000] if len(text) > 8000 else text
        prompt = PASS1_CLASSIFICATION_PROMPT.format(text=truncated)

        for attempt in range(self.retry_count):
            try:
                response = await asyncio.to_thread(
                    self.client.messages.create,
                    model=self.model,
                    max_tokens=1500,
                    temperature=0.1,  # 分類は決定論的に
                    messages=[{"role": "user", "content": prompt}],
                )
                json_str = self._extract_json(response.content[0].text)
                parsed = json.loads(json_str)

                # 最低限のフィールド存在チェック
                if "category" in parsed and "confidence" in parsed:
                    return parsed

                logger.warning(f"Pass1: 必須フィールド不足 (attempt {attempt+1})")
            except (json.JSONDecodeError, IndexError, KeyError) as e:
                logger.warning(f"Pass1: 解析エラー (attempt {attempt+1}): {e}")
                if attempt < self.retry_count - 1:
                    await asyncio.sleep(1 * (attempt + 1))

        # 全リトライ失敗時のフォールバック
        return {
            "category": "",
            "sub_category": "",
            "priority": "中",
            "emotion_tags": [],
            "expression_tags": [],
            "title": Path(text[:50]).stem if text else "不明",
            "summary": "",
            "confidence": 0.0,
            "reasoning": "分類失敗",
        }

    # =========================================================================
    # Pass 2: 構造化・Q&A抽出
    # =========================================================================

    async def _pass2_structure(self, text: str, category: str, sub_category: str) -> dict:
        """テキストをセクション分割し、Q&Aペアを抽出する。"""
        truncated = text[:10000] if len(text) > 10000 else text
        prompt = PASS2_STRUCTURING_PROMPT.format(
            text=truncated,
            category=category,
            sub_category=sub_category,
        )

        for attempt in range(self.retry_count):
            try:
                response = await asyncio.to_thread(
                    self.client.messages.create,
                    model=self.model,
                    max_tokens=4000,
                    temperature=0.2,
                    messages=[{"role": "user", "content": prompt}],
                )
                json_str = self._extract_json(response.content[0].text)
                parsed = json.loads(json_str)
                if "sections" in parsed:
                    return parsed
                logger.warning(f"Pass2: sections不足 (attempt {attempt+1})")
            except (json.JSONDecodeError, IndexError) as e:
                logger.warning(f"Pass2: 解析エラー (attempt {attempt+1}): {e}")
                if attempt < self.retry_count - 1:
                    await asyncio.sleep(1 * (attempt + 1))

        return {"sections": [], "qa_pairs": []}

    # =========================================================================
    # Pass 3: 品質検証
    # =========================================================================

    async def _pass3_verify(self, text: str, result: AnalysisResult) -> dict:
        """分類結果のクロスチェック。"""
        text_preview = text[:2000] if len(text) > 2000 else text
        prompt = PASS3_VERIFICATION_PROMPT.format(
            text_preview=text_preview,
            category=result.category,
            sub_category=result.sub_category,
            priority=result.priority,
            title=result.title,
            summary=result.summary,
            emotion_tags=", ".join(result.emotion_tags),
            expression_tags=", ".join(result.expression_tags),
        )

        try:
            response = await asyncio.to_thread(
                self.client.messages.create,
                model=self.model,
                max_tokens=1000,
                temperature=0.1,
                messages=[{"role": "user", "content": prompt}],
            )
            json_str = self._extract_json(response.content[0].text)
            return json.loads(json_str)
        except Exception as e:
            logger.warning(f"Pass3: 検証エラー: {e}")
            return {"is_valid": True, "quality_score": result.confidence, "corrections": {}, "issues": []}

    # =========================================================================
    # バリデーション
    # =========================================================================

    def _validate_and_fix_labels(self, result: AnalysisResult) -> None:
        """ラベルの妥当性を検証し、不正な値を修正する。"""
        # カテゴリ
        if result.category not in VALID_CATEGORIES:
            best = self._fuzzy_match(result.category, VALID_CATEGORIES)
            if best:
                logger.info(f"カテゴリ自動修正: '{result.category}' → '{best}'")
                result.category = best
            else:
                logger.warning(f"カテゴリ不明: '{result.category}' → 手動レビュー対象")
                result.needs_manual_review = True
                result.review_reasons.append(f"カテゴリ不明: {result.category}")
                result.category = "営業スキル"  # 安全なフォールバック
                result.confidence = min(result.confidence, 0.4)

        # サブカテゴリ
        valid_subs = SUBCATEGORY_MAP.get(result.category, [])
        if valid_subs and result.sub_category not in valid_subs:
            best = self._fuzzy_match(result.sub_category, valid_subs)
            if best:
                logger.info(f"サブカテゴリ自動修正: '{result.sub_category}' → '{best}'")
                result.sub_category = best

        # 優先度
        if result.priority not in VALID_PRIORITIES:
            result.priority = "中"

        # タグのフィルタリング（無効なタグを除去）
        result.emotion_tags = [t for t in result.emotion_tags if t in VALID_EMOTION_TAGS]
        result.expression_tags = [t for t in result.expression_tags if t in VALID_EXPRESSION_TAGS]

    def _fuzzy_match(self, value: str, candidates: list[str]) -> Optional[str]:
        """文字列の部分一致でベストマッチを探す。"""
        if not value:
            return None
        # 完全一致
        for c in candidates:
            if c == value:
                return c
        # 部分一致（候補が入力に含まれる or 入力が候補に含まれる）
        for c in candidates:
            if c in value or value in c:
                return c
        return None

    # =========================================================================
    # 画像・文字起こし処理
    # =========================================================================

    async def _describe_images(self, content: ExtractedContent) -> list[str]:
        """ExtractedContent内の画像をClaude Visionで記述する。"""
        descriptions: list[str] = []
        for img_info in content.images:
            img_path = Path(img_info["path"])
            if img_path.exists():
                desc = await self._describe_single_image(img_path)
                descriptions.append(desc)
        return descriptions

    async def _describe_single_image(self, image_path: Path) -> str:
        """1枚の画像をClaude Visionで記述する。"""
        for attempt in range(self.retry_count):
            try:
                b64 = encode_image_base64(image_path)
                media_type = get_image_media_type(image_path)

                response = await asyncio.to_thread(
                    self.client.messages.create,
                    model=self.model,
                    max_tokens=1500,
                    messages=[{
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": media_type,
                                    "data": b64,
                                },
                            },
                            {"type": "text", "text": IMAGE_DESCRIPTION_PROMPT},
                        ],
                    }],
                )
                return response.content[0].text
            except Exception as e:
                logger.warning(f"画像記述エラー {image_path.name} (attempt {attempt+1}): {e}")
                if attempt < self.retry_count - 1:
                    await asyncio.sleep(1 * (attempt + 1))

        return f"[画像: {image_path.name} - 記述生成失敗（{self.retry_count}回リトライ後）]"

    async def _cleanup_transcript(self, text: str) -> str:
        """文字起こしテキストを整形する。長文は分割して処理。"""
        max_chunk = 10000
        if len(text) <= max_chunk:
            return await self._cleanup_transcript_chunk(text)

        # 長文は分割処理
        chunks: list[str] = []
        for i in range(0, len(text), max_chunk):
            chunk = text[i:i + max_chunk]
            # 文の途中で切れないよう調整
            if i + max_chunk < len(text):
                last_period = chunk.rfind("。")
                if last_period > 0:
                    chunk = chunk[:last_period + 1]
            cleaned = await self._cleanup_transcript_chunk(chunk)
            chunks.append(cleaned)

        return "\n\n".join(chunks)

    async def _cleanup_transcript_chunk(self, text: str) -> str:
        """文字起こしテキスト1チャンクを整形する。"""
        prompt = TRANSCRIPT_CLEANUP_PROMPT.format(text=text)

        try:
            response = await asyncio.to_thread(
                self.client.messages.create,
                model=self.model,
                max_tokens=4000,
                temperature=0.15,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text
        except Exception as e:
            logger.warning(f"文字起こし整形エラー: {e}")
            return text  # 失敗時は原文を返す

    # =========================================================================
    # ユーティリティ
    # =========================================================================

    def _extract_json(self, text: str) -> str:
        """レスポンスからJSONブロックを抽出する。"""
        # ```json ... ``` ブロック
        if "```json" in text:
            start = text.index("```json") + 7
            end = text.index("```", start)
            return text[start:end].strip()
        # ``` ... ```
        if "```" in text:
            start = text.index("```") + 3
            end = text.index("```", start)
            return text[start:end].strip()
        # { ... } を探す（ネスト対応）
        depth = 0
        start_idx = -1
        for i, ch in enumerate(text):
            if ch == "{":
                if depth == 0:
                    start_idx = i
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0 and start_idx >= 0:
                    return text[start_idx:i + 1]
        return text


# =============================================================================
# Markdown生成
# =============================================================================

def generate_markdown(
    result: AnalysisResult,
    entry_id: str,
    source_name: str,
) -> str:
    """AnalysisResultからYAMLフロントマター付きMarkdownを生成する。"""
    tags_str = ", ".join(result.expression_tags) if result.expression_tags else ""
    emotion_str = ", ".join(result.emotion_tags) if result.emotion_tags else ""

    frontmatter = f"""---
id: {entry_id}
category: {result.category}
sub_category: {result.sub_category}
source: {source_name}
priority: {result.priority}
tags: [{tags_str}]
emotion: [{emotion_str}]
confidence: {result.confidence:.2f}
quality_score: {result.quality_score:.2f}
generated_at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
source_file: {Path(result.source_path).name}
needs_review: {str(result.needs_manual_review).lower()}
---"""

    body_parts: list[str] = [frontmatter, ""]

    # タイトル
    title = result.title or Path(result.source_path).stem
    body_parts.append(f"# {title}")
    body_parts.append("")

    # 要約
    if result.summary:
        body_parts.append(f"> {result.summary}")
        body_parts.append("")

    # セクション
    for section in result.sections:
        heading = section.get("heading", "")
        content = section.get("content", "")
        if heading:
            body_parts.append(f"## {heading}")
            body_parts.append("")
        if content:
            body_parts.append(content)
            body_parts.append("")

    # Q&Aペア
    if result.qa_pairs:
        body_parts.append("---")
        body_parts.append("")
        body_parts.append("## Q&A")
        body_parts.append("")
        for qa in result.qa_pairs:
            q = qa.get("question", "")
            a = qa.get("answer", "")
            if q and a:
                body_parts.append(f"### Q: {q}")
                body_parts.append("")
                body_parts.append(a)
                body_parts.append("")

    # 画像記述
    if result.image_descriptions:
        body_parts.append("---")
        body_parts.append("")
        body_parts.append("## 図表・画像")
        body_parts.append("")
        for desc in result.image_descriptions:
            body_parts.append(desc)
            body_parts.append("")

    return "\n".join(body_parts)


# =============================================================================
# ID自動採番
# =============================================================================

def generate_entry_id(
    prefix: str,
    knowledge_dir: Path,
    date: Optional[datetime] = None,
) -> str:
    """既存ファイルを走査してID自動採番する。

    同一prefix内で衝突しないことを保証する。
    """
    date = date or datetime.now()
    ym = date.strftime("%Y%m")

    # 既存IDの最大連番を取得
    max_num = 0
    if knowledge_dir.exists():
        for md_file in knowledge_dir.rglob("*.md"):
            try:
                # フロントマターのidフィールドのみ読む（高速化）
                with open(md_file, encoding="utf-8") as f:
                    in_frontmatter = False
                    for line in f:
                        if line.strip() == "---":
                            if in_frontmatter:
                                break  # フロントマター終了
                            in_frontmatter = True
                            continue
                        if in_frontmatter and line.startswith("id:"):
                            existing_id = line.split(":", 1)[1].strip()
                            if existing_id.startswith(prefix):
                                # 数値部分を全て抽出して最大値を取る
                                nums = re.findall(r"(\d+)", existing_id)
                                if nums:
                                    # prefix直後の連番を取得
                                    for n in nums:
                                        max_num = max(max_num, int(n))
                            break
            except Exception:
                continue

    next_num = max_num + 1

    if prefix == "QA":
        return f"QA_{next_num:03d}"
    elif prefix in ("VID", "AUD"):
        return f"{prefix}_{ym}_{next_num:02d}_01"
    elif prefix == "BK":
        return f"BK_{next_num:03d}_P001"
    else:
        return f"{prefix}_{ym}_{next_num:03d}"
