"""SQLiteデータベースのモデル定義。

会話ログ、ユーザー情報、フィードバックを管理する。
SQLiteを採用し、定期的にGitHubへCSVエクスポートして監査性を担保する。
"""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

DB_SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL DEFAULT (datetime('now')),
    session_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    bot_pattern TEXT NOT NULL CHECK(bot_pattern IN ('pattern_1','pattern_2','pattern_3','pattern_4')),
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    sources_used TEXT,
    confidence REAL DEFAULT 0.0,
    escalated INTEGER DEFAULT 0,
    category TEXT,
    tokens_used INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL,
    timestamp TEXT NOT NULL DEFAULT (datetime('now')),
    rating TEXT CHECK(rating IN ('good','bad')),
    comment TEXT,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
);

CREATE TABLE IF NOT EXISTS escalations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL,
    timestamp TEXT NOT NULL DEFAULT (datetime('now')),
    reason TEXT NOT NULL,
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending','in_progress','resolved')),
    assigned_to TEXT,
    resolution TEXT,
    resolved_at TEXT,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
);

CREATE TABLE IF NOT EXISTS knowledge_updates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL DEFAULT (datetime('now')),
    file_path TEXT NOT NULL,
    action TEXT NOT NULL CHECK(action IN ('add','update','delete')),
    commit_hash TEXT,
    description TEXT
);

-- 操作ログ: ユーザーの行動シグナルを構造化して記録
CREATE TABLE IF NOT EXISTS interaction_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL,
    user_id TEXT NOT NULL,
    timestamp TEXT NOT NULL DEFAULT (datetime('now')),
    input_method TEXT NOT NULL CHECK(input_method IN ('free_text','guided_nav')),
    guide_category TEXT,
    guide_sub_topic TEXT,
    guide_steps_taken INTEGER DEFAULT 0,
    guide_backtrack INTEGER DEFAULT 0,
    guide_ai_used INTEGER DEFAULT 0,
    guide_freetext_len INTEGER DEFAULT 0,
    question_length INTEGER DEFAULT 0,
    question_has_number INTEGER DEFAULT 0,
    response_time_ms INTEGER DEFAULT 0,
    session_position INTEGER DEFAULT 1,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
);

-- ユーザープロファイル: 週次バッチで Claude が生成・更新する構造化サマリー
CREATE TABLE IF NOT EXISTS user_profiles (
    user_id TEXT PRIMARY KEY,
    display_name TEXT DEFAULT '',
    registered_at TEXT NOT NULL DEFAULT (datetime('now')),
    profile_json TEXT DEFAULT '{}',
    total_sessions INTEGER DEFAULT 0,
    total_questions INTEGER DEFAULT 0,
    primary_pattern TEXT DEFAULT 'pattern_1',
    last_active TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- 集合知: 週次/月次バッチで全ユーザーデータから抽出した分析結果
CREATE TABLE IF NOT EXISTS collective_insights (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    period TEXT NOT NULL,
    insight_type TEXT NOT NULL CHECK(insight_type IN ('faq','low_satisfaction','knowledge_gap','trending','effective_pattern')),
    insight_json TEXT NOT NULL,
    generated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_conversations_session ON conversations(session_id);
CREATE INDEX IF NOT EXISTS idx_conversations_user ON conversations(user_id);
CREATE INDEX IF NOT EXISTS idx_conversations_pattern ON conversations(bot_pattern);
CREATE INDEX IF NOT EXISTS idx_conversations_timestamp ON conversations(timestamp);
CREATE INDEX IF NOT EXISTS idx_feedback_conversation ON feedback(conversation_id);
CREATE INDEX IF NOT EXISTS idx_escalations_status ON escalations(status);
CREATE INDEX IF NOT EXISTS idx_interaction_logs_user ON interaction_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_interaction_logs_conversation ON interaction_logs(conversation_id);
CREATE INDEX IF NOT EXISTS idx_interaction_logs_timestamp ON interaction_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_collective_insights_period ON collective_insights(period);
CREATE INDEX IF NOT EXISTS idx_collective_insights_type ON collective_insights(insight_type);
"""


def init_db(db_path: str | Path) -> sqlite3.Connection:
    """データベースを初期化し、スキーマを適用する。

    Args:
        db_path: SQLiteデータベースファイルのパス

    Returns:
        データベース接続
    """
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(DB_SCHEMA)
    conn.commit()

    return conn


def get_connection(db_path: str | Path) -> sqlite3.Connection:
    """既存のデータベースに接続する。

    Args:
        db_path: SQLiteデータベースファイルのパス

    Returns:
        データベース接続
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn
