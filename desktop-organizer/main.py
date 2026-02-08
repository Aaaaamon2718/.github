#!/usr/bin/env python3
"""デスクトップ整理ツール

デスクトップに散乱したスクリーンショットを日付別フォルダに自動整理する。
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from src.config_loader import load_config
from src.organizer import execute_plan, scan_desktop


def parse_args() -> argparse.Namespace:
    """コマンドライン引数を解析する。"""
    parser = argparse.ArgumentParser(
        description="デスクトップのスクリーンショットを日付別に整理する",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="実際には移動せず、計画のみ表示する",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="設定ファイルのパス（デフォルト: config/settings.yaml）",
    )
    parser.add_argument(
        "--desktop",
        type=str,
        default=None,
        help="デスクトップのパスを直接指定する",
    )
    return parser.parse_args()


def print_plan(plan: list[dict]) -> None:
    """整理計画を表示する。"""
    if not plan:
        print("整理対象のファイルが見つかりませんでした。")
        return

    print(f"\n整理対象: {len(plan)} ファイル")
    print("-" * 60)

    # 日付ごとにグループ化して表示
    current_group = None
    for entry in plan:
        date = entry["date"]
        group_label = date.strftime("%Y-%m") if date else "日付不明"

        if group_label != current_group:
            current_group = group_label
            count = sum(
                1 for e in plan
                if (e["date"].strftime("%Y-%m") if e["date"] else "日付不明") == group_label
            )
            print(f"\n📁 {group_label}/ ({count} ファイル)")

        dest = entry["destination"]
        print(f"  → {dest.parent.name}/{entry['filename']}")


def write_log(plan: list[dict], stats: dict, config: dict) -> None:
    """整理ログを出力する。"""
    log_config = config.get("logging", {})
    if not log_config.get("enabled", False):
        return

    log_path = Path(log_config["file"]).expanduser()
    log_path.parent.mkdir(parents=True, exist_ok=True)

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"\n{'='*60}\n")
        f.write(f"実行日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"移動: {stats['moved']}, スキップ: {stats['skipped']}, エラー: {stats['errors']}\n")
        for entry in plan:
            f.write(f"  {entry['filename']} → {entry['destination']}\n")


def main() -> int:
    """メイン処理。"""
    args = parse_args()

    try:
        config = load_config(args.config)
    except FileNotFoundError as e:
        print(f"エラー: {e}", file=sys.stderr)
        return 1

    # コマンドラインでデスクトップパスが指定されていれば上書き
    if args.desktop:
        config["desktop_path"] = args.desktop

    # ドライランモード（コマンドライン引数が優先）
    dry_run = args.dry_run or config.get("dry_run", False)

    print("🖥️  デスクトップ整理ツール")
    print(f"対象: {Path(config['desktop_path']).expanduser()}")

    if dry_run:
        print("⚠️  ドライランモード（実際のファイル移動は行いません）")

    # スキャン
    try:
        plan = scan_desktop(config)
    except FileNotFoundError as e:
        print(f"エラー: {e}", file=sys.stderr)
        return 1

    # 計画表示
    print_plan(plan)

    if not plan:
        return 0

    # ドライランなら終了
    if dry_run:
        print(f"\n✅ ドライラン完了: {len(plan)} ファイルが整理対象です")
        return 0

    # 確認プロンプト
    print(f"\n{len(plan)} ファイルを整理します。実行しますか？ [y/N] ", end="")
    answer = input().strip().lower()
    if answer not in ("y", "yes"):
        print("キャンセルしました。")
        return 0

    # 実行
    stats = execute_plan(plan, dry_run=False)

    print(f"\n✅ 整理完了:")
    print(f"  移動: {stats['moved']} ファイル")
    print(f"  スキップ: {stats['skipped']} ファイル（同名ファイルが既に存在）")
    if stats["errors"] > 0:
        print(f"  エラー: {stats['errors']} ファイル")

    # ログ出力
    write_log(plan, stats, config)

    return 0


if __name__ == "__main__":
    sys.exit(main())
