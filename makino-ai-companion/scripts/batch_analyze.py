"""週次バッチ分析スクリプト。

蓄積された会話ログ + 操作ログを Claude で分析し、
ユーザープロファイルと集合知を生成・更新する。

Usage:
    python scripts/batch_analyze.py
    python scripts/batch_analyze.py --since 2026-02-01
    python scripts/batch_analyze.py --db data/conversations.db
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import yaml

from src.database.models import init_db
from src.memory.batch_analyzer import BatchAnalyzer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def load_config() -> dict:
    """設定ファイルを読み込む。"""
    config_path = project_root / "config" / "settings.yaml"
    with open(config_path, encoding="utf-8") as f:
        content = f.read()
    for key, value in os.environ.items():
        content = content.replace(f"${{{key}}}", value)
    return yaml.safe_load(content)


def main() -> None:
    """メインエントリーポイント。"""
    parser = argparse.ArgumentParser(description="週次バッチ分析")
    parser.add_argument(
        "--since",
        type=str,
        default=None,
        help="分析対象の開始日（ISO形式）。省略時は7日前。",
    )
    parser.add_argument(
        "--db",
        type=str,
        default=None,
        help="SQLiteデータベースのパス。省略時はsettings.yamlの設定を使用。",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="分析に使用するClaudeモデル。省略時はsettings.yamlの設定を使用。",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="分析対象のデータ量だけ表示して終了する。",
    )
    args = parser.parse_args()

    # 設定読み込み
    config = load_config()
    claude_config = config.get("claude", {})
    api_key = claude_config.get("api_key", os.environ.get("ANTHROPIC_API_KEY", ""))

    if not api_key:
        logger.error("ANTHROPIC_API_KEY が未設定です")
        sys.exit(1)

    # DB接続
    db_path = args.db or config.get("database", {}).get("sqlite", {}).get("path", "data/conversations.db")
    conn = init_db(project_root / db_path)

    # 分析期間
    since = args.since
    if not since:
        since = (datetime.now() - timedelta(days=7)).isoformat()

    # モデル
    model = args.model or claude_config.get("model", "claude-sonnet-4-5-20250929")

    if args.dry_run:
        # ドライラン: データ量の確認のみ
        from src.database.operations import get_users_for_batch
        user_ids = get_users_for_batch(conn, since)
        total_convs = conn.execute(
            "SELECT COUNT(*) as cnt FROM conversations WHERE timestamp >= ?",
            (since,),
        ).fetchone()
        logger.info(f"ドライラン結果:")
        logger.info(f"  分析期間: {since} 〜")
        logger.info(f"  対象ユーザー: {len(user_ids)}人")
        logger.info(f"  対象会話数: {total_convs['cnt']}件")
        logger.info(f"  使用モデル: {model}")
        return

    # バッチ実行
    analyzer = BatchAnalyzer(
        conn=conn,
        api_key=api_key,
        model=model,
    )

    summary = analyzer.run_weekly(since=since)

    # 結果出力
    print("\n=== 週次バッチ分析完了 ===")
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    conn.close()


if __name__ == "__main__":
    main()
