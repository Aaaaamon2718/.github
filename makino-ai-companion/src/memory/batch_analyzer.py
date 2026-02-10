"""週次バッチ分析。

蓄積された会話ログ + 操作ログを Claude に渡し、
ユーザープロファイルと集合知を生成・更新する。

Usage:
    python -m src.memory.batch_analyzer --db data/conversations.db
"""

import json
import logging
import sqlite3
from datetime import datetime, timedelta
from typing import Optional

import anthropic

from src.database.operations import (
    get_user_conversations_with_logs,
    get_users_for_batch,
    save_collective_insight,
    update_profile,
    update_profile_stats,
    get_or_create_profile,
)

logger = logging.getLogger(__name__)

# バッチ分析で使用するプロンプト
PROFILE_ANALYSIS_PROMPT = """\
あなたは生命保険営業の教育システムのデータアナリストです。
以下のユーザーの会話履歴と操作ログを分析し、ユーザープロファイルを生成してください。

## ユーザーID: {user_id}
## 既存プロファイル:
{existing_profile}

## 会話ログ + 操作ログ（直近1週間）:
{conversation_data}

## 出力形式
以下のJSON形式で出力してください。JSONのみを出力し、他のテキストは含めないでください。

{{
  "understanding_level": {{
    "トピック名": {{
      "level": "未着手 | 基礎学習中 | 中級 | 上級・実践",
      "evidence": "判断根拠（具体的な質問内容や傾向を1文で）",
      "trend": "improving | stable | none"
    }}
  }},
  "behavior_pattern": {{
    "preferred_input": "free_text | guided_nav | mixed",
    "avg_question_length": 数値,
    "tends_to_deep_dive": true/false,
    "needs_concrete_examples": true/false
  }},
  "unresolved_topics": [
    {{
      "topic": "未解決のトピック",
      "last_asked": "YYYY-MM-DD",
      "times_asked": 数値,
      "satisfaction": "good | bad | unknown"
    }}
  ],
  "session_summaries": [
    {{
      "date": "YYYY-MM-DD",
      "topics": ["トピック1", "トピック2"],
      "resolved": true/false,
      "key_insight": "このセッションで何がわかったか1文"
    }}
  ]
}}
"""

COLLECTIVE_ANALYSIS_PROMPT = """\
あなたは生命保険営業の教育システムのデータアナリストです。
以下は直近1週間の全ユーザーの会話データの要約統計です。
これを分析し、集合知として以下の4種類のインサイトを抽出してください。

## 集計データ:
{aggregated_data}

## 出力形式
以下のJSON配列で出力してください。JSONのみを出力し、他のテキストは含めないでください。

[
  {{
    "type": "faq",
    "topic": "よく聞かれるトピック",
    "question_count": 数値,
    "common_patterns": ["よくある質問パターン1", "パターン2"],
    "suggestion": "質問ナビや教材への反映提案"
  }},
  {{
    "type": "knowledge_gap",
    "topic": "ナレッジベースが不足しているトピック",
    "signal": {{
      "escalation_rate": 0.0〜1.0,
      "question_count": 数値,
      "unique_users": 数値,
      "avg_satisfaction": 0.0〜1.0
    }},
    "recommendation": "ナレッジベース改善の具体的提案",
    "priority": "high | medium | low"
  }},
  {{
    "type": "low_satisfaction",
    "topic": "満足度が低い回答パターン",
    "bad_rate": 0.0〜1.0,
    "sample_questions": ["問題のある質問例1"],
    "possible_cause": "原因の推測",
    "improvement": "改善案"
  }},
  {{
    "type": "effective_pattern",
    "topic": "効果的だった回答パターン",
    "good_rate": 0.0〜1.0,
    "what_worked": "何が効果的だったか"
  }}
]
"""


class BatchAnalyzer:
    """週次バッチ分析を実行する。"""

    def __init__(
        self,
        conn: sqlite3.Connection,
        api_key: str,
        model: str = "claude-sonnet-4-5-20250929",
    ) -> None:
        self.conn = conn
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    def run_weekly(self, since: Optional[str] = None) -> dict:
        """週次バッチを実行する。

        Args:
            since: 分析対象の開始日（ISO形式）。省略時は7日前。

        Returns:
            実行結果のサマリー
        """
        if not since:
            since = (datetime.now() - timedelta(days=7)).isoformat()

        logger.info(f"週次バッチ開始: since={since}")

        # 1. ユーザープロファイル更新
        user_ids = get_users_for_batch(self.conn, since)
        profile_results = {"updated": 0, "failed": 0}

        for user_id in user_ids:
            try:
                self._update_user_profile(user_id, since)
                profile_results["updated"] += 1
            except Exception as e:
                logger.error(f"プロファイル更新失敗 user={user_id}: {e}")
                profile_results["failed"] += 1

        # 2. 集合知分析
        insight_results = {"generated": 0, "failed": 0}
        try:
            self._generate_collective_insights(since)
            insight_results["generated"] = 1
        except Exception as e:
            logger.error(f"集合知分析失敗: {e}")
            insight_results["failed"] = 1

        summary = {
            "since": since,
            "users_processed": len(user_ids),
            "profiles": profile_results,
            "insights": insight_results,
        }
        logger.info(f"週次バッチ完了: {summary}")
        return summary

    def _update_user_profile(self, user_id: str, since: str) -> None:
        """1ユーザーのプロファイルを分析・更新する。"""
        # 会話+操作ログを取得
        conversations = get_user_conversations_with_logs(self.conn, user_id, since)
        if not conversations:
            return

        # 既存プロファイル取得
        profile = get_or_create_profile(self.conn, user_id)
        existing_json = profile.get("profile_json", "{}")

        # 会話データを要約形式に変換（トークン節約）
        conv_summary = self._format_conversations_for_prompt(conversations)

        prompt = PROFILE_ANALYSIS_PROMPT.format(
            user_id=user_id,
            existing_profile=existing_json,
            conversation_data=conv_summary,
        )

        response = self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )

        text = response.content[0].text.strip()
        # JSONパース検証
        profile_data = json.loads(text)

        update_profile(self.conn, user_id, json.dumps(profile_data, ensure_ascii=False))
        update_profile_stats(self.conn, user_id)

        logger.info(f"プロファイル更新完了: user={user_id}")

    def _generate_collective_insights(self, since: str) -> None:
        """全ユーザーのデータから集合知を抽出する。"""
        # 集計データを生成
        aggregated = self._aggregate_data(since)
        if not aggregated:
            logger.info("集合知分析: データなし")
            return

        prompt = COLLECTIVE_ANALYSIS_PROMPT.format(
            aggregated_data=json.dumps(aggregated, ensure_ascii=False, indent=2)
        )

        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )

        text = response.content[0].text.strip()
        insights = json.loads(text)

        # 期間ラベル生成（ISO week）
        period = datetime.now().strftime("%Y-W%W")

        if isinstance(insights, list):
            for insight in insights:
                insight_type = insight.get("type", "faq")
                save_collective_insight(
                    self.conn,
                    period=period,
                    insight_type=insight_type,
                    insight_json=json.dumps(insight, ensure_ascii=False),
                )
        else:
            save_collective_insight(
                self.conn,
                period=period,
                insight_type="faq",
                insight_json=json.dumps(insights, ensure_ascii=False),
            )

        logger.info(f"集合知分析完了: period={period}, insights={len(insights) if isinstance(insights, list) else 1}")

    def _format_conversations_for_prompt(self, conversations: list[dict]) -> str:
        """会話データをプロンプト用に要約形式に変換する。"""
        lines: list[str] = []
        for i, conv in enumerate(conversations, 1):
            method = conv.get("input_method") or "不明"
            guide_info = ""
            if method == "guided_nav":
                cat = conv.get("guide_category") or ""
                sub = conv.get("guide_sub_topic") or ""
                back = conv.get("guide_backtrack") or 0
                guide_info = f" [ナビ: {cat}→{sub}, 戻り{back}回]"

            q_len = conv.get("question_length") or len(conv.get("question", ""))
            has_num = "数値あり" if conv.get("question_has_number") else ""
            feedback = conv.get("feedback_rating") or "未評価"
            escalated = "エスカレ" if conv.get("escalated") else ""

            lines.append(
                f"--- 会話{i} ({conv.get('timestamp', '')}) ---\n"
                f"入力方法: {method}{guide_info}\n"
                f"パターン: {conv.get('bot_pattern', '')}\n"
                f"質問({q_len}文字{', ' + has_num if has_num else ''}): {conv.get('question', '')[:200]}\n"
                f"回答: {conv.get('answer', '')[:200]}...\n"
                f"確信度: {conv.get('confidence', 0):.2f} | 評価: {feedback} {escalated}"
            )
        return "\n\n".join(lines)

    def _aggregate_data(self, since: str) -> dict:
        """集合知分析用の集計データを生成する。"""
        # カテゴリ別質問数
        category_rows = self.conn.execute(
            """SELECT category, COUNT(*) as count,
                AVG(confidence) as avg_confidence,
                SUM(escalated) as escalated_count
               FROM conversations
               WHERE timestamp >= ? AND user_id != 'anonymous'
               GROUP BY category ORDER BY count DESC""",
            (since,),
        ).fetchall()

        # カテゴリ別満足度
        satisfaction_rows = self.conn.execute(
            """SELECT c.category,
                COUNT(CASE WHEN f.rating = 'good' THEN 1 END) as good,
                COUNT(CASE WHEN f.rating = 'bad' THEN 1 END) as bad
               FROM conversations c
               JOIN feedback f ON c.id = f.conversation_id
               WHERE c.timestamp >= ?
               GROUP BY c.category""",
            (since,),
        ).fetchall()

        # 入力方法の分布
        input_rows = self.conn.execute(
            """SELECT input_method, COUNT(*) as count
               FROM interaction_logs
               WHERE timestamp >= ?
               GROUP BY input_method""",
            (since,),
        ).fetchall()

        # ユニークユーザー数
        unique_users = self.conn.execute(
            "SELECT COUNT(DISTINCT user_id) as cnt FROM conversations WHERE timestamp >= ? AND user_id != 'anonymous'",
            (since,),
        ).fetchone()

        if not category_rows:
            return {}

        satisfaction_map = {}
        for row in satisfaction_rows:
            good = row["good"] or 0
            bad = row["bad"] or 0
            total = good + bad
            satisfaction_map[row["category"]] = {
                "good": good, "bad": bad,
                "rate": good / total if total > 0 else 0.0,
            }

        categories = []
        for row in category_rows:
            cat = row["category"] or "未分類"
            sat = satisfaction_map.get(cat, {"good": 0, "bad": 0, "rate": 0.0})
            categories.append({
                "category": cat,
                "question_count": row["count"],
                "avg_confidence": round(row["avg_confidence"] or 0.0, 3),
                "escalation_count": row["escalated_count"] or 0,
                "satisfaction": sat,
            })

        return {
            "period_since": since,
            "unique_users": unique_users["cnt"] if unique_users else 0,
            "categories": categories,
            "input_methods": {row["input_method"]: row["count"] for row in input_rows},
        }
