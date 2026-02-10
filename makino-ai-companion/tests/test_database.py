"""データベースのテスト。"""

import sqlite3
from pathlib import Path

import pytest

from src.database.models import DB_SCHEMA, init_db, get_connection
from src.database.operations import (
    save_conversation,
    save_feedback,
    get_conversation_history,
    calculate_metrics,
    save_interaction_log,
    get_or_create_profile,
    update_profile,
)


@pytest.fixture
def db_conn(tmp_path: Path) -> sqlite3.Connection:
    """テスト用インメモリDBを作成する。"""
    db_path = tmp_path / "test.db"
    conn = init_db(db_path)
    return conn


class TestInitDb:
    """データベース初期化のテスト。"""

    def test_tables_created(self, db_conn: sqlite3.Connection) -> None:
        """全テーブルが作成されること。"""
        cursor = db_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = {row[0] for row in cursor.fetchall()}
        expected = {
            "conversations", "feedback", "escalations",
            "knowledge_updates", "interaction_logs",
            "user_profiles", "collective_insights",
        }
        assert expected.issubset(tables)

    def test_wal_mode(self, db_conn: sqlite3.Connection) -> None:
        """WALモードが有効であること。"""
        cursor = db_conn.execute("PRAGMA journal_mode")
        mode = cursor.fetchone()[0]
        assert mode == "wal"


class TestConversations:
    """会話保存・取得のテスト。"""

    def test_save_and_retrieve(self, db_conn: sqlite3.Connection) -> None:
        """会話を保存して取得できること。"""
        conv_id = save_conversation(
            conn=db_conn,
            session_id="test-session",
            user_id="user1",
            bot_pattern="pattern_1",
            question="赤字決算のアプローチ方法は？",
            answer="赤字の会社こそ保障が必要です。",
            sources_used=["qa/sample.md"],
            confidence=0.85,
            category="法人保険",
        )
        assert conv_id > 0

        history = get_conversation_history(db_conn, "test-session")
        assert len(history) == 1
        assert history[0]["question"] == "赤字決算のアプローチ方法は？"

    def test_multiple_conversations(self, db_conn: sqlite3.Connection) -> None:
        """複数の会話が正しく保存されること。"""
        for i in range(3):
            save_conversation(
                conn=db_conn,
                session_id="multi-session",
                user_id="user1",
                bot_pattern="pattern_1",
                question=f"質問{i}",
                answer=f"回答{i}",
                sources_used=[],
                confidence=0.8,
            )
        history = get_conversation_history(db_conn, "multi-session")
        assert len(history) == 3

    def test_different_sessions(self, db_conn: sqlite3.Connection) -> None:
        """セッション別に取得できること。"""
        save_conversation(
            db_conn, "s1", "u1", "pattern_1", "Q1", "A1", [], 0.8
        )
        save_conversation(
            db_conn, "s2", "u1", "pattern_1", "Q2", "A2", [], 0.8
        )

        h1 = get_conversation_history(db_conn, "s1")
        h2 = get_conversation_history(db_conn, "s2")
        assert len(h1) == 1
        assert len(h2) == 1


class TestFeedback:
    """フィードバック保存のテスト。"""

    def test_save_feedback(self, db_conn: sqlite3.Connection) -> None:
        """フィードバックが保存できること。"""
        conv_id = save_conversation(
            db_conn, "sess", "user1", "pattern_1", "Q", "A", [], 0.8
        )
        save_feedback(db_conn, conv_id, "good", "とても参考になりました")

        cursor = db_conn.execute(
            "SELECT rating, comment FROM feedback WHERE conversation_id = ?",
            (conv_id,),
        )
        row = cursor.fetchone()
        assert row[0] == "good"
        assert row[1] == "とても参考になりました"


class TestMetrics:
    """メトリクス計算のテスト。"""

    def test_empty_metrics(self, db_conn: sqlite3.Connection) -> None:
        """データなしでもメトリクスが返ること。"""
        metrics = calculate_metrics(db_conn)
        assert "total_questions" in metrics
        assert metrics["total_questions"] == 0

    def test_metrics_with_data(self, db_conn: sqlite3.Connection) -> None:
        """データありでメトリクスが正しいこと。"""
        for _ in range(5):
            save_conversation(
                db_conn, "s", "u", "pattern_1", "Q", "A", [], 0.8
            )
        metrics = calculate_metrics(db_conn)
        assert metrics["total_questions"] == 5

    def test_metrics_with_feedback(self, db_conn: sqlite3.Connection) -> None:
        """フィードバック付きメトリクスが正しいこと。"""
        for i in range(4):
            cid = save_conversation(
                db_conn, "s", "u", "pattern_1", f"Q{i}", f"A{i}", [], 0.8
            )
            rating = "good" if i < 3 else "bad"
            save_feedback(db_conn, cid, rating)

        metrics = calculate_metrics(db_conn)
        assert metrics["total_questions"] == 4
        assert metrics["feedback_count"] == 4
        assert metrics["user_satisfaction"] == 0.75


class TestInteractionLogs:
    """操作ログのテスト。"""

    def test_save_interaction_log(self, db_conn: sqlite3.Connection) -> None:
        """操作ログが保存できること。"""
        conv_id = save_conversation(
            db_conn, "sess", "user1", "pattern_1", "Q", "A", [], 0.8
        )
        save_interaction_log(
            conn=db_conn,
            conversation_id=conv_id,
            user_id="user1",
            input_method="guided_nav",
            question_length=20,
            session_position=1,
            guide_category="法人保険",
            guide_sub_topic="決算書分析",
            guide_steps_taken=3,
            guide_backtrack=1,
            guide_ai_used=True,
            response_time_ms=1500,
        )

        cursor = db_conn.execute(
            "SELECT input_method, guide_category FROM interaction_logs WHERE conversation_id = ?",
            (conv_id,),
        )
        row = cursor.fetchone()
        assert row[0] == "guided_nav"
        assert row[1] == "法人保険"


class TestUserProfiles:
    """ユーザープロファイルのテスト。"""

    def test_get_or_create(self, db_conn: sqlite3.Connection) -> None:
        """プロファイルが作成・取得できること。"""
        profile = get_or_create_profile(db_conn, "user1")
        assert profile["user_id"] == "user1"
        assert profile["total_sessions"] == 0

        # 2回目は同じものが返る
        profile2 = get_or_create_profile(db_conn, "user1")
        assert profile2["user_id"] == "user1"

    def test_update_profile(self, db_conn: sqlite3.Connection) -> None:
        """プロファイルが更新できること。"""
        get_or_create_profile(db_conn, "user1")
        update_profile(
            db_conn,
            "user1",
            profile_json='{"level": "intermediate"}',
        )

        cursor = db_conn.execute(
            "SELECT profile_json FROM user_profiles WHERE user_id = ?",
            ("user1",),
        )
        row = cursor.fetchone()
        assert '"level"' in row[0]
