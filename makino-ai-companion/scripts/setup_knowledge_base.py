"""ナレッジベースのセットアップ・バリデーションスクリプト。

knowledge/ ディレクトリ内のMarkdownファイルを検証し、
統計情報を表示する。

Usage:
    python scripts/setup_knowledge_base.py
    python scripts/setup_knowledge_base.py --validate-only
    python scripts/setup_knowledge_base.py --knowledge-dir knowledge/
"""

import argparse
import logging
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.chat.rag import KnowledgeLoader

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def validate_frontmatter(file_path: Path) -> list[str]:
    """Markdownファイルのフロントマターを検証する。

    Args:
        file_path: Markdownファイルのパス

    Returns:
        エラーメッセージのリスト（空ならOK）
    """
    errors = []
    content = file_path.read_text(encoding="utf-8")

    if not content.startswith("---"):
        errors.append("YAMLフロントマターが見つかりません")
        return errors

    parts = content.split("---", 2)
    if len(parts) < 3:
        errors.append("フロントマターの終了マーカー（---）が見つかりません")
        return errors

    frontmatter = parts[1].strip()
    if not frontmatter:
        errors.append("フロントマターが空です")
        return errors

    required_fields = ["category"]
    for field in required_fields:
        if f"{field}:" not in frontmatter:
            errors.append(f"必須フィールド '{field}' がフロントマターに含まれていません")

    return errors


def main() -> None:
    """メイン処理。"""
    parser = argparse.ArgumentParser(
        description="ナレッジベースのセットアップとバリデーション"
    )
    parser.add_argument(
        "--knowledge-dir",
        type=str,
        default="knowledge",
        help="ナレッジベースディレクトリのパス（デフォルト: knowledge/）",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="バリデーションのみ実施",
    )
    args = parser.parse_args()

    knowledge_dir = Path(args.knowledge_dir)
    if not knowledge_dir.exists():
        logger.error(f"ディレクトリが見つかりません: {knowledge_dir}")
        sys.exit(1)

    # Markdownファイルの一覧取得
    md_files = list(knowledge_dir.rglob("*.md"))
    readme_files = [f for f in md_files if f.name.lower() == "readme.md"]
    content_files = [f for f in md_files if f.name.lower() != "readme.md"]

    logger.info(f"ナレッジベースディレクトリ: {knowledge_dir}")
    logger.info(f"Markdownファイル数: {len(content_files)} （README除く）")

    # バリデーション
    has_errors = False
    for file_path in content_files:
        errors = validate_frontmatter(file_path)
        if errors:
            has_errors = True
            for error in errors:
                logger.warning(f"  [{file_path.relative_to(knowledge_dir)}] {error}")

    if has_errors:
        logger.warning("バリデーションエラーが検出されました")
        if args.validate_only:
            sys.exit(1)
    else:
        logger.info("バリデーション: 全ファイルが正常です")

    if args.validate_only:
        return

    # 統計情報の表示
    logger.info("=== ナレッジベース統計 ===")

    # サブディレクトリ別の統計
    subdirs = [d for d in knowledge_dir.iterdir() if d.is_dir()]
    for subdir in sorted(subdirs):
        files = list(subdir.rglob("*.md"))
        content = [f for f in files if f.name.lower() != "readme.md"]
        logger.info(f"  {subdir.name}/: {len(content)} ファイル")

    # RAGエンジンでの読み込みテスト
    try:
        loader = KnowledgeLoader(str(knowledge_dir))
        documents = loader.load_all()
        logger.info(f"  RAG読み込みテスト: {len(documents)} チャンク生成")
    except Exception as e:
        logger.warning(f"  RAG読み込みテスト失敗: {e}")

    logger.info("セットアップ完了")


if __name__ == "__main__":
    main()
