"""ログデータのエクスポート・分析スクリプト。

蓄積されたログデータからKPI指標を算出し、
改善に必要なレポートを生成する。

Usage:
    python scripts/export_logs.py --input data/logs.csv
    python scripts/export_logs.py --input data/logs.csv --output reports/monthly_report.json
"""

import argparse
import csv
import json
import logging
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.logging.log_handler import ConversationLog, calculate_metrics

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def load_logs_from_csv(file_path: Path) -> list[ConversationLog]:
    """CSVファイルからログデータを読み込む。

    Args:
        file_path: CSVファイルのパス

    Returns:
        ConversationLogのリスト
    """
    logs: list[ConversationLog] = []

    with open(file_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            log = ConversationLog(
                timestamp=row["timestamp"],
                user_id=row["user_id"],
                bot_pattern=row["bot_pattern"],
                question=row["question"],
                answer=row["answer"],
                source_used=row.get("source_used", ""),
                confidence=float(row.get("confidence", 0.0)),
                user_rating=row.get("user_rating") or None,
                escalated=row.get("escalated", "false").lower() == "true",
                category=row.get("category", "未分類"),
                review_status=row.get("review_status", "未"),
                action_taken=row.get("action_taken", ""),
            )
            logs.append(log)

    return logs


def generate_pattern_breakdown(logs: list[ConversationLog]) -> dict:
    """パターン別の内訳を生成する。

    Args:
        logs: ログリスト

    Returns:
        パターン別の統計辞書
    """
    patterns = {}
    for log in logs:
        if log.bot_pattern not in patterns:
            patterns[log.bot_pattern] = []
        patterns[log.bot_pattern].append(log)

    breakdown = {}
    for pattern, pattern_logs in patterns.items():
        breakdown[pattern] = {
            "count": len(pattern_logs),
            "metrics": calculate_metrics(pattern_logs),
        }

    return breakdown


def main() -> None:
    """メイン処理。"""
    parser = argparse.ArgumentParser(
        description="ログデータのエクスポートと分析"
    )
    parser.add_argument(
        "--input",
        type=str,
        required=True,
        help="入力CSVファイルのパス",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="出力JSONファイルのパス（省略時は標準出力）",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        logger.error(f"ファイルが見つかりません: {input_path}")
        sys.exit(1)

    logger.info(f"ログファイルを読み込みます: {input_path}")
    logs = load_logs_from_csv(input_path)
    logger.info(f"読み込み完了: {len(logs)}件のログ")

    # 全体のKPI算出
    overall_metrics = calculate_metrics(logs)

    # パターン別の内訳
    pattern_breakdown = generate_pattern_breakdown(logs)

    # レポート生成
    report = {
        "summary": {
            "total_logs": len(logs),
            "period": {
                "from": logs[0].timestamp if logs else None,
                "to": logs[-1].timestamp if logs else None,
            },
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


if __name__ == "__main__":
    main()
