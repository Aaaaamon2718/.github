"""ナレッジパイプライン: 生データをナレッジベース形式に変換する。

intake/raw/ 内のテキストファイルを読み込み、
カテゴリ推定・フロントマター付与・Markdown変換を行い、
knowledge/ ディレクトリに配置する。

Usage:
    python scripts/knowledge_pipeline.py --dry-run
    python scripts/knowledge_pipeline.py
    python scripts/knowledge_pipeline.py --input intake/raw/specific.txt
    python scripts/knowledge_pipeline.py --report latest
"""

import argparse
import logging
import os
import re
import sys
from datetime import datetime
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# カテゴリ推定用キーワードマッピング
CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "法人保険": ["法人", "決算書", "赤字", "黒字", "P/L", "B/S", "損益", "貸借"],
    "ドクターマーケット": ["ドクター", "医師", "医療法人", "開業医", "クリニック", "病院"],
    "相続": ["相続", "遺言", "遺産", "贈与", "生前"],
    "営業マインド": ["プロ", "マインド", "覚悟", "信念", "言い訳", "結果を出す", "負けない"],
    "決算書分析": ["決算", "財務", "経常利益", "売上", "粗利", "営業利益"],
    "退職金設計": ["退職金", "退職", "功績倍率", "役員退職"],
    "事業承継": ["事業承継", "後継者", "M&A", "株価", "自社株"],
    "アプローチ手法": ["アプローチ", "初回面談", "社長に会", "紹介", "テレアポ"],
    "クロージング": ["クロージング", "契約", "申込", "成約"],
}

# サブカテゴリ推定用キーワード
SUB_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "赤字決算対策": ["赤字", "赤字決算"],
    "退職金準備": ["退職金"],
    "社長へのアプローチ": ["社長", "アプローチ"],
    "決算書の読み方": ["P/L", "B/S", "決算書", "損益"],
    "メンタリング": ["プロ", "覚悟", "言い訳", "結果を出す"],
}

# カテゴリ → 推奨配置先ディレクトリ
CATEGORY_TO_DIR: dict[str, str] = {
    "法人保険": "seminars",
    "ドクターマーケット": "trainings",
    "相続": "seminars",
    "営業マインド": "seminars",
    "決算書分析": "seminars",
    "退職金設計": "seminars",
    "事業承継": "seminars",
    "アプローチ手法": "sales_tools",
    "クロージング": "sales_tools",
}


def detect_category(text: str) -> str:
    """テキスト内容からカテゴリを推定する。

    Args:
        text: 解析対象のテキスト

    Returns:
        推定されたカテゴリ名
    """
    scores: dict[str, int] = {}
    for category, keywords in CATEGORY_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text)
        if score > 0:
            scores[category] = score

    if not scores:
        return "営業マインド"

    return max(scores, key=scores.get)


def detect_sub_category(text: str) -> str:
    """テキスト内容からサブカテゴリを推定する。

    Args:
        text: 解析対象のテキスト

    Returns:
        推定されたサブカテゴリ名
    """
    scores: dict[str, int] = {}
    for sub_cat, keywords in SUB_CATEGORY_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text)
        if score > 0:
            scores[sub_cat] = score

    if not scores:
        return "一般"

    return max(scores, key=scores.get)


def detect_emotion_tags(text: str) -> list[str]:
    """テキストの感情タグを推定する。

    Args:
        text: 解析対象のテキスト

    Returns:
        感情タグのリスト
    """
    tags: list[str] = []

    encouragement_kw = ["大事", "必要", "間違いない", "できる"]
    strict_kw = ["言い訳はしない", "考えなさい", "甘い", "覚悟"]
    logical_kw = ["なぜなら", "つまり", "理由", "原因"]
    passion_kw = ["必ず", "絶対", "こそ", "間違いない"]

    if any(kw in text for kw in encouragement_kw):
        tags.append("励まし")
    if any(kw in text for kw in strict_kw):
        tags.append("叱咤")
    if any(kw in text for kw in logical_kw):
        tags.append("論理的解説")
    if any(kw in text for kw in passion_kw):
        tags.append("情熱")

    return tags if tags else ["論理的解説"]


def extract_title(text: str) -> str:
    """テキストの先頭行からタイトルを抽出する。

    Args:
        text: テキスト全文

    Returns:
        タイトル文字列
    """
    lines = text.strip().split("\n")
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            return stripped
    return "無題"


def convert_to_markdown(
    text: str,
    category: str,
    sub_category: str,
    source_file: str,
    emotion_tags: list[str],
) -> str:
    """生テキストをフロントマター付きMarkdownに変換する。

    Args:
        text: 元のテキスト
        category: カテゴリ
        sub_category: サブカテゴリ
        source_file: 元ファイル名
        emotion_tags: 感情タグリスト

    Returns:
        Markdown形式の文字列
    """
    title = extract_title(text)
    today = datetime.now().strftime("%Y-%m-%d")
    tags_str = ", ".join(emotion_tags)

    lines = text.strip().split("\n")
    # 先頭のタイトル行を除いた本文
    body_lines = lines[1:] if len(lines) > 1 else lines
    body = "\n".join(body_lines).strip()

    # 本文を段落ごとに整形
    paragraphs = re.split(r'\n\s*\n', body)
    formatted_body = "\n\n".join(p.strip() for p in paragraphs if p.strip())

    markdown = f"""---
category: {category}
sub_category: {sub_category}
source: {source_file}
priority: high
tags: [{tags_str}]
created: {today}
---

# {title}

{formatted_body}
"""
    return markdown


def process_file(file_path: Path, dry_run: bool = False) -> dict:
    """1ファイルを処理する。

    Args:
        file_path: 入力ファイルパス
        dry_run: Trueの場合、ファイル書き込みを行わない

    Returns:
        処理結果の辞書
    """
    text = file_path.read_text(encoding="utf-8")

    category = detect_category(text)
    sub_category = detect_sub_category(text)
    emotion_tags = detect_emotion_tags(text)
    target_dir = CATEGORY_TO_DIR.get(category, "seminars")
    title = extract_title(text)

    # 出力ファイル名の生成
    stem = file_path.stem
    output_name = f"{stem}.md"
    output_dir = project_root / "knowledge" / target_dir
    output_path = output_dir / output_name

    markdown = convert_to_markdown(
        text=text,
        category=category,
        sub_category=sub_category,
        source_file=file_path.name,
        emotion_tags=emotion_tags,
    )

    result = {
        "input": str(file_path.relative_to(project_root)),
        "output": str(output_path.relative_to(project_root)),
        "title": title,
        "category": category,
        "sub_category": sub_category,
        "emotion_tags": emotion_tags,
        "target_dir": target_dir,
        "char_count": len(text),
        "markdown_preview": markdown,
    }

    if not dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path.write_text(markdown, encoding="utf-8")
        logger.info(f"  → 書き込み完了: {output_path.relative_to(project_root)}")

    return result


def report_knowledge_base(mode: str) -> None:
    """ナレッジベースの現状レポートを表示する。

    Args:
        mode: "latest" で最新ファイル順、"all" で全体統計
    """
    knowledge_dir = project_root / "knowledge"
    intake_raw = project_root / "intake" / "raw"

    logger.info("=" * 60)
    logger.info("ナレッジベース レポート")
    logger.info("=" * 60)

    if not knowledge_dir.exists():
        logger.error(f"ナレッジディレクトリが見つかりません: {knowledge_dir}")
        return

    # knowledge/ 内のMarkdownファイル収集
    md_files = sorted(
        [f for f in knowledge_dir.rglob("*.md") if f.name.lower() != "readme.md"],
        key=lambda f: os.path.getmtime(f),
        reverse=True,
    )

    # intake/raw/ 内の未処理ファイル
    raw_files = sorted(intake_raw.glob("*.txt")) if intake_raw.exists() else []

    # --- 全体統計 ---
    logger.info("")
    logger.info("【全体統計】")
    logger.info(f"  ナレッジファイル数: {len(md_files)}")
    logger.info(f"  未処理ファイル数  : {len(raw_files)}")

    # サブディレクトリ別
    subdirs = ["seminars", "trainings", "qa", "articles", "sales_tools"]
    logger.info("")
    logger.info("【ディレクトリ別】")
    for subdir in subdirs:
        subdir_path = knowledge_dir / subdir
        if subdir_path.exists():
            count = len([f for f in subdir_path.rglob("*.md") if f.name.lower() != "readme.md"])
            logger.info(f"  {subdir}/: {count} ファイル")
        else:
            logger.info(f"  {subdir}/: (未作成)")

    # カテゴリ別集計
    category_counts: dict[str, int] = {}
    total_chars = 0
    for md_file in md_files:
        content = md_file.read_text(encoding="utf-8")
        total_chars += len(content)
        match = re.search(r'^category:\s*(.+)$', content, re.MULTILINE)
        if match:
            cat = match.group(1).strip()
            category_counts[cat] = category_counts.get(cat, 0) + 1

    if category_counts:
        logger.info("")
        logger.info("【カテゴリ別】")
        for cat, count in sorted(category_counts.items(), key=lambda x: x[1], reverse=True):
            logger.info(f"  {cat}: {count} ファイル")

    logger.info("")
    logger.info(f"  合計文字数: {total_chars:,}")

    # --- 最新ファイル ---
    if mode == "latest" and md_files:
        show_count = min(10, len(md_files))
        logger.info("")
        logger.info(f"【最新 {show_count} ファイル】")
        for md_file in md_files[:show_count]:
            mtime = datetime.fromtimestamp(os.path.getmtime(md_file)).strftime("%Y-%m-%d %H:%M")
            rel_path = md_file.relative_to(knowledge_dir)
            content = md_file.read_text(encoding="utf-8")

            # フロントマターからカテゴリ取得
            cat_match = re.search(r'^category:\s*(.+)$', content, re.MULTILINE)
            category = cat_match.group(1).strip() if cat_match else "不明"

            logger.info(f"  [{mtime}] {rel_path}  ({category}, {len(content)}字)")

    # --- 未処理ファイル ---
    if raw_files:
        logger.info("")
        logger.info("【未処理ファイル（intake/raw/）】")
        for raw_file in raw_files:
            size = raw_file.stat().st_size
            logger.info(f"  {raw_file.name}  ({size:,} bytes)")
        logger.info("")
        logger.info("  → python scripts/knowledge_pipeline.py --dry-run で変換プレビュー")

    logger.info("")
    logger.info("レポート完了")


def main() -> None:
    """メイン処理。"""
    parser = argparse.ArgumentParser(
        description="intake/raw/ の生データをナレッジベース形式に変換"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="変換プレビューのみ（ファイル書き込みなし）",
    )
    parser.add_argument(
        "--input",
        type=str,
        default=None,
        help="特定ファイルのみ処理（省略時はintake/raw/内の全ファイル）",
    )
    parser.add_argument(
        "--intake-dir",
        type=str,
        default="intake/raw",
        help="入力ディレクトリ（デフォルト: intake/raw/）",
    )
    parser.add_argument(
        "--report",
        type=str,
        choices=["latest", "all"],
        default=None,
        help="ナレッジベースのレポート表示（latest: 最新順, all: 全体統計）",
    )
    args = parser.parse_args()

    # レポートモード
    if args.report:
        report_knowledge_base(args.report)
        return

    logger.info("=" * 60)
    logger.info("ナレッジパイプライン 開始")
    logger.info("=" * 60)

    if args.dry_run:
        logger.info("モード: DRY-RUN（プレビューのみ、書き込みなし）")
    else:
        logger.info("モード: 実行（ファイル書き込みあり）")

    # 入力ファイルの収集
    if args.input:
        input_path = project_root / args.input
        if not input_path.exists():
            logger.error(f"ファイルが見つかりません: {input_path}")
            sys.exit(1)
        files = [input_path]
    else:
        intake_dir = project_root / args.intake_dir
        if not intake_dir.exists():
            logger.error(f"入力ディレクトリが見つかりません: {intake_dir}")
            sys.exit(1)
        files = sorted(intake_dir.glob("*.txt"))
        if not files:
            logger.warning(f"処理対象ファイルがありません: {intake_dir}")
            sys.exit(0)

    logger.info(f"処理対象: {len(files)} ファイル")
    logger.info("-" * 60)

    results: list[dict] = []
    for file_path in files:
        logger.info(f"\n処理中: {file_path.name}")
        result = process_file(file_path, dry_run=args.dry_run)
        results.append(result)

        logger.info(f"  タイトル    : {result['title']}")
        logger.info(f"  カテゴリ    : {result['category']}")
        logger.info(f"  サブカテゴリ: {result['sub_category']}")
        logger.info(f"  感情タグ    : {result['emotion_tags']}")
        logger.info(f"  出力先      : {result['output']}")
        logger.info(f"  文字数      : {result['char_count']}")

        if args.dry_run:
            logger.info("")
            logger.info("  --- Markdown プレビュー ---")
            for line in result["markdown_preview"].split("\n"):
                logger.info(f"  | {line}")
            logger.info("  --- プレビュー終了 ---")

    # サマリー
    logger.info("")
    logger.info("=" * 60)
    logger.info("処理サマリー")
    logger.info("=" * 60)
    logger.info(f"  処理ファイル数: {len(results)}")

    categories = {}
    for r in results:
        cat = r["category"]
        categories[cat] = categories.get(cat, 0) + 1
    for cat, count in categories.items():
        logger.info(f"  {cat}: {count} ファイル")

    total_chars = sum(r["char_count"] for r in results)
    logger.info(f"  合計文字数: {total_chars}")

    if args.dry_run:
        logger.info("")
        logger.info("※ DRY-RUNモードのため、ファイルは書き込まれていません。")
        logger.info("  実行するには --dry-run を外してください:")
        logger.info("  python scripts/knowledge_pipeline.py")
    else:
        logger.info("")
        logger.info("ナレッジベースへの書き込みが完了しました。")
        logger.info("次のステップ:")
        logger.info("  1. python cli.py knowledge validate")
        logger.info("  2. python cli.py knowledge stats")
        logger.info("  3. git add & commit")

    logger.info("")
    logger.info("ナレッジパイプライン 完了")


if __name__ == "__main__":
    main()
