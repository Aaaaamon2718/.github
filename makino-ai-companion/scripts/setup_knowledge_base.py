"""ナレッジベースのセットアップスクリプト。

CSVファイルからナレッジベースデータを読み込み、
バリデーションを実施した上で統計情報を表示する。

Usage:
    python scripts/setup_knowledge_base.py --input templates/knowledge_base_template.csv
    python scripts/setup_knowledge_base.py --input data/knowledge_base.csv --validate-only
"""

import argparse
import logging
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.knowledge_base.processor import (
    generate_stats,
    load_knowledge_csv,
    validate_knowledge_base,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    """メイン処理。"""
    parser = argparse.ArgumentParser(
        description="ナレッジベースのセットアップとバリデーション"
    )
    parser.add_argument(
        "--input",
        type=str,
        required=True,
        help="入力CSVファイルのパス",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="バリデーションのみ実施（データ処理は行わない）",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    logger.info(f"ナレッジベースファイルを読み込みます: {input_path}")

    try:
        entries = load_knowledge_csv(input_path)
    except FileNotFoundError as e:
        logger.error(str(e))
        sys.exit(1)

    logger.info(f"読み込み完了: {len(entries)}件のエントリ")

    # バリデーション
    errors = validate_knowledge_base(entries)
    if errors:
        logger.warning("バリデーションエラーが検出されました:")
        for entry_id, entry_errors in errors.items():
            for error in entry_errors:
                logger.warning(f"  [{entry_id}] {error}")
        if args.validate_only:
            sys.exit(1)
    else:
        logger.info("バリデーション: 全エントリが正常です")

    if args.validate_only:
        return

    # 統計情報の表示
    stats = generate_stats(entries)
    logger.info("=== ナレッジベース統計 ===")
    for key, value in stats.items():
        logger.info(f"  {key}: {value}")

    logger.info("セットアップ完了")


if __name__ == "__main__":
    main()
