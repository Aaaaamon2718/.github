"""ログ処理のユーティリティ。

SQLiteデータベースへの書き込みは src/database/operations.py が担当。
本モジュールはログのフォーマット・分析補助を提供する。
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# エスカレーション必須カテゴリ
MANDATORY_ESCALATION_CATEGORIES = [
    "コンプライアンス関連",
    "個別顧客の契約内容",
    "具体的な保険料試算",
    "税務の最終判断",
]


def should_escalate(confidence: float, threshold: float = 0.5) -> bool:
    """確信度に基づきエスカレーションが必要か判定する。"""
    return confidence < threshold


def requires_mandatory_escalation(category: str) -> bool:
    """カテゴリに基づき強制エスカレーションが必要か判定する。"""
    return category in MANDATORY_ESCALATION_CATEGORIES


def format_log_summary(metrics: dict) -> str:
    """メトリクスデータを人間が読みやすいサマリーに整形する。"""
    lines = [
        "=== 運用サマリー ===",
        f"総質問数:       {metrics.get('total_questions', 0)}",
        f"回答成功率:     {metrics.get('answer_success_rate', 0):.1%}",
        f"ユーザー満足度: {metrics.get('user_satisfaction', 0):.1%}",
        f"平均確信度:     {metrics.get('average_confidence', 0):.2f}",
        f"エスカレーション: {metrics.get('escalation_count', 0)}件",
    ]
    return "\n".join(lines)
