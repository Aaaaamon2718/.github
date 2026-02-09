"""データベースの読み書き操作。

会話ログの保存、フィードバックの記録、分析用クエリを提供する。
"""

import csv
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional


def save_conversation(
    conn: sqlite3.Connection,
    session_id: str,
    user_id: str,
    bot_pattern: str,
    question: str,
    answer: str,
    sources_used: list[str],
    confidence: float,
    escalated: bool = False,
    category: str = "",
    tokens_used: int = 0,
) -> int:
    """会話ログを保存する。

    Returns:
        挿入されたレコードのID
    """
    cursor = conn.execute(
        """INSERT INTO conversations
           (session_id, user_id, bot_pattern, question, answer,
            sources_used, confidence, escalated, category, tokens_used)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            session_id,
            user_id,
            bot_pattern,
            question,
            answer,
            json.dumps(sources_used, ensure_ascii=False),
            confidence,
            1 if escalated else 0,
            category,
            tokens_used,
        ),
    )
    conn.commit()
    return cursor.lastrowid


def save_feedback(
    conn: sqlite3.Connection,
    conversation_id: int,
    rating: str,
    comment: str = "",
) -> int:
    """フィードバックを保存する。"""
    cursor = conn.execute(
        "INSERT INTO feedback (conversation_id, rating, comment) VALUES (?, ?, ?)",
        (conversation_id, rating, comment),
    )
    conn.commit()
    return cursor.lastrowid


def save_escalation(
    conn: sqlite3.Connection,
    conversation_id: int,
    reason: str,
) -> int:
    """エスカレーションを記録する。"""
    cursor = conn.execute(
        "INSERT INTO escalations (conversation_id, reason) VALUES (?, ?)",
        (conversation_id, reason),
    )
    conn.commit()
    return cursor.lastrowid


def get_conversation_history(
    conn: sqlite3.Connection,
    session_id: str,
    limit: int = 20,
) -> list[dict]:
    """セッションの会話履歴を取得する。"""
    rows = conn.execute(
        """SELECT question, answer, bot_pattern, timestamp
           FROM conversations
           WHERE session_id = ?
           ORDER BY timestamp DESC
           LIMIT ?""",
        (session_id, limit),
    ).fetchall()
    return [dict(row) for row in reversed(rows)]


def calculate_metrics(
    conn: sqlite3.Connection,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> dict:
    """KPI指標を算出する。"""
    where = "WHERE 1=1"
    params: list = []
    if date_from:
        where += " AND c.timestamp >= ?"
        params.append(date_from)
    if date_to:
        where += " AND c.timestamp <= ?"
        params.append(date_to)

    row = conn.execute(
        f"""SELECT
            COUNT(*) as total,
            SUM(CASE WHEN escalated = 0 THEN 1 ELSE 0 END) as resolved,
            AVG(confidence) as avg_confidence,
            SUM(escalated) as escalated_count
           FROM conversations c {where}""",
        params,
    ).fetchone()

    total = row["total"] or 0
    resolved = row["resolved"] or 0

    fb_row = conn.execute(
        f"""SELECT
            COUNT(CASE WHEN f.rating = 'good' THEN 1 END) as good,
            COUNT(CASE WHEN f.rating = 'bad' THEN 1 END) as bad
           FROM feedback f
           JOIN conversations c ON f.conversation_id = c.id {where}""",
        params,
    ).fetchone()

    good = fb_row["good"] or 0
    bad = fb_row["bad"] or 0

    return {
        "total_questions": total,
        "answer_success_rate": resolved / total if total > 0 else 0.0,
        "average_confidence": row["avg_confidence"] or 0.0,
        "escalation_count": row["escalated_count"] or 0,
        "escalation_rate": (row["escalated_count"] or 0) / total if total > 0 else 0.0,
        "user_satisfaction": good / (good + bad) if (good + bad) > 0 else 0.0,
        "feedback_count": good + bad,
    }


def get_pattern_breakdown(
    conn: sqlite3.Connection,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> dict:
    """パターン別の利用統計を取得する。"""
    where = "WHERE 1=1"
    params: list = []
    if date_from:
        where += " AND timestamp >= ?"
        params.append(date_from)
    if date_to:
        where += " AND timestamp <= ?"
        params.append(date_to)

    rows = conn.execute(
        f"""SELECT bot_pattern, COUNT(*) as count,
            AVG(confidence) as avg_confidence,
            SUM(escalated) as escalated
           FROM conversations {where}
           GROUP BY bot_pattern""",
        params,
    ).fetchall()

    return {row["bot_pattern"]: dict(row) for row in rows}


def export_to_csv(
    conn: sqlite3.Connection,
    output_path: str | Path,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> int:
    """会話ログをCSVにエクスポートする（GitHub監査用）。

    Returns:
        エクスポートされたレコード数
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    where = "WHERE 1=1"
    params: list = []
    if date_from:
        where += " AND c.timestamp >= ?"
        params.append(date_from)
    if date_to:
        where += " AND c.timestamp <= ?"
        params.append(date_to)

    rows = conn.execute(
        f"""SELECT c.*, f.rating as user_rating, f.comment as feedback_comment
           FROM conversations c
           LEFT JOIN feedback f ON c.id = f.conversation_id
           {where}
           ORDER BY c.timestamp""",
        params,
    ).fetchall()

    if not rows:
        return 0

    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(rows[0].keys())
        for row in rows:
            writer.writerow(tuple(row))

    return len(rows)
