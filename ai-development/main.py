#!/usr/bin/env python3
"""AI開発 ナレッジベース - CLIエントリーポイント

テキストと画像のコンテンツを管理するCLIツール。

使い方:
    python main.py add-text --title "タイトル" --body "本文" --category conversation
    python main.py add-image --title "タイトル" --path image.png --category diagram
    python main.py list [--type text|images] [--category カテゴリ]
    python main.py search "キーワード"
    python main.py index
    python main.py stats
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from src.content_manager import ContentManager


def cmd_add_text(manager: ContentManager, args: argparse.Namespace) -> None:
    """テキストエントリを追加する"""
    body = args.body
    if args.file:
        body = Path(args.file).read_text(encoding="utf-8")

    tags = [t.strip() for t in args.tags.split(",")] if args.tags else []

    path = manager.add_text(
        title=args.title,
        body=body,
        category=args.category,
        tags=tags,
        source=args.source,
    )
    print(f"テキストエントリを作成しました: {path}")


def cmd_add_image(manager: ContentManager, args: argparse.Namespace) -> None:
    """画像エントリを追加する"""
    tags = [t.strip() for t in args.tags.split(",")] if args.tags else []

    path = manager.add_image(
        title=args.title,
        image_path=args.path,
        description=args.description,
        category=args.category,
        tags=tags,
        source=args.source,
    )
    print(f"画像エントリを登録しました: {path}")


def cmd_list(manager: ContentManager, args: argparse.Namespace) -> None:
    """エントリ一覧を表示する"""
    entries = manager.list_entries(
        content_type=args.type,
        category=args.category,
        tag=args.tag,
    )

    if not entries:
        print("エントリが見つかりません。")
        return

    for entry in entries:
        type_label = "TEXT" if entry["type"] == "text" else "IMG"
        tags_str = ", ".join(entry.get("tags", []))
        tags_display = f" [{tags_str}]" if tags_str else ""
        print(
            f"  [{type_label}] {entry['title']}  "
            f"({entry['category']}{tags_display})  "
            f"{entry['created_at']}"
        )
        print(f"         {entry['path']}")

    print(f"\n合計: {len(entries)} 件")


def cmd_search(manager: ContentManager, args: argparse.Namespace) -> None:
    """キーワード検索する"""
    results = manager.search(args.query)

    if not results:
        print(f"'{args.query}' に一致するエントリが見つかりません。")
        return

    print(f"'{args.query}' の検索結果: {len(results)} 件\n")
    for entry in results:
        type_label = "TEXT" if entry["type"] == "text" else "IMG"
        print(f"  [{type_label}] {entry['title']}  ({entry['category']})")
        print(f"         {entry['path']}")


def cmd_index(manager: ContentManager, args: argparse.Namespace) -> None:
    """INDEX.md を再生成する"""
    path = manager.update_index()
    print(f"インデックスを更新しました: {path}")


def cmd_stats(manager: ContentManager, args: argparse.Namespace) -> None:
    """統計情報を表示する"""
    stats = manager.get_stats()
    print("=== AI開発 ナレッジベース 統計 ===\n")
    print(f"総エントリ数: {stats['total']}")
    print(f"  テキスト: {stats['text_count']}")
    print(f"  画像:     {stats['image_count']}")

    if stats["text_by_category"]:
        print("\nテキスト (カテゴリ別):")
        for cat, count in sorted(stats["text_by_category"].items()):
            print(f"  {cat}: {count}")

    if stats["image_by_category"]:
        print("\n画像 (カテゴリ別):")
        for cat, count in sorted(stats["image_by_category"].items()):
            print(f"  {cat}: {count}")


def build_parser() -> argparse.ArgumentParser:
    """引数パーサーを構築する"""
    parser = argparse.ArgumentParser(
        description="AI開発 ナレッジベース - テキストと画像のコンテンツ管理",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="コマンド")

    # add-text
    p_text = subparsers.add_parser("add-text", help="テキストエントリを追加")
    p_text.add_argument("--title", required=True, help="タイトル")
    p_text.add_argument("--body", default="", help="本文（直接入力）")
    p_text.add_argument("--file", help="本文をファイルから読み込む")
    p_text.add_argument(
        "--category", default="conversation",
        choices=["conversation", "decision", "insight", "specification", "reference"],
        help="カテゴリ (default: conversation)",
    )
    p_text.add_argument("--tags", default="", help="タグ（カンマ区切り）")
    p_text.add_argument("--source", default="", help="情報源")
    p_text.set_defaults(func=cmd_add_text)

    # add-image
    p_img = subparsers.add_parser("add-image", help="画像エントリを追加")
    p_img.add_argument("--title", required=True, help="タイトル")
    p_img.add_argument("--path", required=True, help="画像ファイルのパス")
    p_img.add_argument("--description", default="", help="画像の説明")
    p_img.add_argument(
        "--category", default="reference",
        choices=["diagram", "screenshot", "generated", "reference", "architecture"],
        help="カテゴリ (default: reference)",
    )
    p_img.add_argument("--tags", default="", help="タグ（カンマ区切り）")
    p_img.add_argument("--source", default="", help="情報源")
    p_img.set_defaults(func=cmd_add_image)

    # list
    p_list = subparsers.add_parser("list", help="エントリ一覧")
    p_list.add_argument("--type", choices=["text", "images"], help="種類でフィルタ")
    p_list.add_argument("--category", help="カテゴリでフィルタ")
    p_list.add_argument("--tag", help="タグでフィルタ")
    p_list.set_defaults(func=cmd_list)

    # search
    p_search = subparsers.add_parser("search", help="キーワード検索")
    p_search.add_argument("query", help="検索キーワード")
    p_search.set_defaults(func=cmd_search)

    # index
    p_index = subparsers.add_parser("index", help="INDEX.md を再生成")
    p_index.set_defaults(func=cmd_index)

    # stats
    p_stats = subparsers.add_parser("stats", help="統計情報を表示")
    p_stats.set_defaults(func=cmd_stats)

    return parser


def main() -> None:
    """メインエントリーポイント"""
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    base_dir = Path(__file__).resolve().parent
    manager = ContentManager(base_dir)
    args.func(manager, args)


if __name__ == "__main__":
    main()
