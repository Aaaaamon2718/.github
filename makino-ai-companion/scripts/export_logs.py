"""ログデータのエクスポート・分析スクリプト。

SQLiteデータベースからログデータをエクスポートし、
KPI指標を算出してレポートを生成する。

Usage:
    python scripts/export_logs.py
    python scripts/export_logs.py --output reports/monthly_report.json
    python scripts/export_logs.py --date-from 2025-01-01 --date-to 2025-01-31
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import yaml

from src.database.models import get_connection
from src.database.operations import (
    calculate_metrics,
    export_to_csv,
    get_pattern_breakdown,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    """メイン処理。"""
    parser = argparse.ArgumentParser(
        description="SQLiteログデータのエクスポートと分析"
    )
    parser.add_argument(
        "--output",
        type=str,
        help="出力JSONファイルのパス（省略時は標準出力）",
    )
    parser.add_argument(
        "--csv-export",
        action="store_true",
        help="CSVエクスポートも実施する（logs/exports/に出力）",
    )
    parser.add_argument(
        "--date-from",
        type=str,
        help="集計開始日（YYYY-MM-DD形式）",
    )
    parser.add_argument(
        "--date-to",
        type=str,
        help="集計終了日（YYYY-MM-DD形式）",
    )
    args = parser.parse_args()

    # 設定読み込み
    config_path = project_root / "config" / "settings.yaml"
    with open(config_path, encoding="utf-8") as f:
        content = f.read()
    for key, value in os.environ.items():
        content = content.replace(f"${{{key}}}", value)
    config = yaml.safe_load(content)

    db_path = config.get("database", {}).get("sqlite", {}).get("path", "data/conversations.db")

    # データベース接続
    try:
        conn = get_connection(project_root / db_path)
    except Exception as e:
        logger.error(f"データベース接続エラー: {e}")
        sys.exit(1)

    # 全体のKPI算出
    logger.info("KPI指標を算出中...")
    overall_metrics = calculate_metrics(conn, args.date_from, args.date_to)

    # パターン別の内訳
    logger.info("パターン別統計を算出中...")
    pattern_breakdown = get_pattern_breakdown(conn, args.date_from, args.date_to)

    # レポート生成
    report = {
        "summary": {
            "date_from": args.date_from,
            "date_to": args.date_to,
        },
        "overall_metrics": overall_metrics,
        "pattern_breakdown": pattern_breakdown,
    }

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        logger.info(f"レポートを出力しました: {output_path}")
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2))

    # CSVエクスポート
    if args.csv_export:
        logger.info("CSVエクスポートを実行中...")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_output = project_root / "logs" / "exports" / f"conversations_{timestamp}.csv"
        count = export_to_csv(
            conn, csv_output,
            date_from=args.date_from,
            date_to=args.date_to,
        )
        logger.info(f"CSVエクスポート完了: {csv_output} ({count}件)")

    conn.close()


if __name__ == "__main__":
    main()
