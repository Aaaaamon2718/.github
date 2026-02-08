"""質問・回答ログの処理・蓄積を行うモジュール。

Difyからのwebhookデータを受信し、Google Sheetsへの
自動蓄積を行う処理を管理する。
"""

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ConversationLog:
    """1回の対話ログを表すデータクラス。"""

    timestamp: str
    user_id: str
    bot_pattern: str
    question: str
    answer: str
    source_used: str
    confidence: float
    user_rating: Optional[str]  # "good" / "bad" / None
    escalated: bool
    category: str
    review_status: str = "未"  # 未 / 済 / 要対応
    action_taken: str = ""

    def to_sheet_row(self) -> list:
        """スプレッドシートの1行として出力する。"""
        return [
            self.timestamp,
            self.user_id,
            self.bot_pattern,
            self.question,
            self.answer,
            self.source_used,
            str(self.confidence),
            self.user_rating or "",
            str(self.escalated).lower(),
            self.category,
            self.review_status,
            self.action_taken,
        ]

    def to_dict(self) -> dict:
        """辞書形式に変換する。"""
        return asdict(self)


def parse_webhook_payload(payload: dict) -> ConversationLog:
    """Difyからのwebhookペイロードを解析してConversationLogに変換する。

    Args:
        payload: webhookで受信したJSONデータ

    Returns:
        ConversationLogインスタンス

    Raises:
        KeyError: 必須フィールドが不足している場合
    """
    return ConversationLog(
        timestamp=payload.get("timestamp", datetime.utcnow().isoformat()),
        user_id=payload.get("user_id", "unknown"),
        bot_pattern=payload.get("bot_pattern", "pattern_1"),
        question=payload["question"],
        answer=payload["answer"],
        source_used=payload.get("source_used", ""),
        confidence=float(payload.get("confidence", 0.0)),
        user_rating=payload.get("user_rating"),
        escalated=payload.get("escalated", False),
        category=payload.get("category", "未分類"),
    )


def should_escalate(confidence: float, threshold: float = 0.5) -> bool:
    """確信度に基づきエスカレーションが必要か判定する。

    Args:
        confidence: 回答の確信度スコア (0.0-1.0)
        threshold: エスカレーション閾値

    Returns:
        エスカレーションが必要な場合True
    """
    return confidence < threshold


# エスカレーション必須カテゴリ
MANDATORY_ESCALATION_CATEGORIES = [
    "コンプライアンス関連",
    "個別顧客の契約内容",
    "具体的な保険料試算",
    "税務の最終判断",
]


def requires_mandatory_escalation(category: str) -> bool:
    """カテゴリに基づき強制エスカレーションが必要か判定する。

    Args:
        category: 質問のカテゴリ

    Returns:
        強制エスカレーションが必要な場合True
    """
    return category in MANDATORY_ESCALATION_CATEGORIES


def calculate_metrics(logs: list[ConversationLog]) -> dict:
    """ログデータからKPI指標を算出する。

    Args:
        logs: 対象期間のログリスト

    Returns:
        各指標を格納した辞書
    """
    if not logs:
        return {
            "total_questions": 0,
            "answer_success_rate": 0.0,
            "user_satisfaction": 0.0,
            "average_confidence": 0.0,
            "escalation_rate": 0.0,
        }

    total = len(logs)
    escalated_count = sum(1 for log in logs if log.escalated)
    rated_logs = [log for log in logs if log.user_rating is not None]
    good_count = sum(1 for log in rated_logs if log.user_rating == "good")

    return {
        "total_questions": total,
        "answer_success_rate": (total - escalated_count) / total if total > 0 else 0.0,
        "user_satisfaction": good_count / len(rated_logs) if rated_logs else 0.0,
        "average_confidence": sum(log.confidence for log in logs) / total if total > 0 else 0.0,
        "escalation_rate": escalated_count / total if total > 0 else 0.0,
    }
