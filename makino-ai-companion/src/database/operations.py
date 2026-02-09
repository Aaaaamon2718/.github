"""データベースの読み書き操作。

会話ログの保存、フィードバックの記録、操作ログ、
ユーザープロファイル、集合知の管理、分析用クエリを提供する。
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


def save_interaction_log(
    conn: sqlite3.Connection,
    conversation_id: int,
    user_id: str,
    input_method: str,
    question_length: int,
    session_position: int,
    guide_category: str = "",
    guide_sub_topic: str = "",
    guide_steps_taken: int = 0,
    guide_backtrack: int = 0,
    guide_ai_used: bool = False,
    guide_freetext_len: int = 0,
    question_has_number: bool = False,
    response_time_ms: int = 0,
) -> int:
    """操作ログを保存する。ユーザーの行動シグナルを構造化して記録。"""
    cursor = conn.execute(
        """INSERT INTO interaction_logs
           (conversation_id, user_id, input_method,
            guide_category, guide_sub_topic, guide_steps_taken,
            guide_backtrack, guide_ai_used, guide_freetext_len,
            question_length, question_has_number,
            response_time_ms, session_position)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            conversation_id,
            user_id,
            input_method,
            guide_category,
            guide_sub_topic,
            guide_steps_taken,
            guide_backtrack,
            1 if guide_ai_used else 0,
            guide_freetext_len,
            question_length,
            1 if question_has_number else 0,
            response_time_ms,
            session_position,
        ),
    )
    conn.commit()
    return cursor.lastrowid


def get_or_create_profile(
    conn: sqlite3.Connection,
    user_id: str,
    display_name: str = "",
) -> dict:
    """ユーザープロファイルを取得する。存在しなければ新規作成。"""
    row = conn.execute(
        "SELECT * FROM user_profiles WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    if row:
        return dict(row)

    conn.execute(
        """INSERT INTO user_profiles (user_id, display_name)
           VALUES (?, ?)""",
        (user_id, display_name),
    )
    conn.commit()
    return {
        "user_id": user_id,
        "display_name": display_name,
        "profile_json": "{}",
        "total_sessions": 0,
        "total_questions": 0,
        "primary_pattern": "pattern_1",
        "last_active": None,
        "updated_at": datetime.now().isoformat(),
    }


def update_profile(
    conn: sqlite3.Connection,
    user_id: str,
    profile_json: str,
) -> None:
    """ユーザープロファイルのJSON部分を更新する（バッチ分析後に呼ばれる）。"""
    conn.execute(
        """UPDATE user_profiles
           SET profile_json = ?, updated_at = datetime('now')
           WHERE user_id = ?""",
        (profile_json, user_id),
    )
    conn.commit()


def update_profile_stats(
    conn: sqlite3.Connection,
    user_id: str,
) -> None:
    """ユーザーの統計情報を会話データから再計算して更新する。"""
    row = conn.execute(
        """SELECT
            COUNT(*) as total_questions,
            COUNT(DISTINCT session_id) as total_sessions,
            MAX(timestamp) as last_active
           FROM conversations WHERE user_id = ?""",
        (user_id,),
    ).fetchone()

    pattern_row = conn.execute(
        """SELECT bot_pattern, COUNT(*) as cnt
           FROM conversations WHERE user_id = ?
           GROUP BY bot_pattern ORDER BY cnt DESC LIMIT 1""",
        (user_id,),
    ).fetchone()

    primary_pattern = pattern_row["bot_pattern"] if pattern_row else "pattern_1"

    conn.execute(
        """UPDATE user_profiles
           SET total_questions = ?, total_sessions = ?,
               primary_pattern = ?, last_active = ?,
               updated_at = datetime('now')
           WHERE user_id = ?""",
        (
            row["total_questions"] or 0,
            row["total_sessions"] or 0,
            primary_pattern,
            row["last_active"],
            user_id,
        ),
    )
    conn.commit()


def save_collective_insight(
    conn: sqlite3.Connection,
    period: str,
    insight_type: str,
    insight_json: str,
) -> int:
    """集合知の分析結果を保存する。"""
    cursor = conn.execute(
        """INSERT INTO collective_insights (period, insight_type, insight_json)
           VALUES (?, ?, ?)""",
        (period, insight_type, insight_json),
    )
    conn.commit()
    return cursor.lastrowid


def get_users_for_batch(
    conn: sqlite3.Connection,
    since: Optional[str] = None,
) -> list[str]:
    """バッチ処理対象のユーザーIDリストを返す。"""
    if since:
        rows = conn.execute(
            """SELECT DISTINCT user_id FROM conversations
               WHERE timestamp >= ? AND user_id != 'anonymous'""",
            (since,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT DISTINCT user_id FROM conversations WHERE user_id != 'anonymous'"
        ).fetchall()
    return [row["user_id"] for row in rows]


def get_user_conversations_with_logs(
    conn: sqlite3.Connection,
    user_id: str,
    since: Optional[str] = None,
) -> list[dict]:
    """ユーザーの会話ログ + 操作ログを結合して取得する（バッチ分析用）。"""
    where = "WHERE c.user_id = ?"
    params: list = [user_id]
    if since:
        where += " AND c.timestamp >= ?"
        params.append(since)

    rows = conn.execute(
        f"""SELECT
            c.id, c.timestamp, c.session_id, c.bot_pattern,
            c.question, c.answer, c.confidence, c.escalated, c.category,
            f.rating as feedback_rating,
            il.input_method, il.guide_category, il.guide_sub_topic,
            il.guide_steps_taken, il.guide_backtrack, il.guide_ai_used,
            il.guide_freetext_len, il.question_length,
            il.question_has_number, il.response_time_ms, il.session_position
           FROM conversations c
           LEFT JOIN feedback f ON c.id = f.conversation_id
           LEFT JOIN interaction_logs il ON c.id = il.conversation_id
           {where}
           ORDER BY c.timestamp""",
        params,
    ).fetchall()
    return [dict(row) for row in rows]


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
