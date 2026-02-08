"""デスクトップファイルの整理ロジック"""

from __future__ import annotations

import fnmatch
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any


# スクリーンショットファイル名から日付を抽出するパターン
DATE_PATTERNS: list[re.Pattern[str]] = [
    # "スクリーンショット 2026-01-17 22.42.10" 形式
    re.compile(r"(\d{4}-\d{2}-\d{2})"),
    # "Screenshot 2026-01-17 at 22.42.10" 形式
    re.compile(r"(\d{4}-\d{2}-\d{2})"),
    # "Screen Shot 2026-01-17" 形式
    re.compile(r"(\d{4}-\d{2}-\d{2})"),
]


def extract_date(filename: str) -> datetime | None:
    """ファイル名から日付を抽出する。

    Args:
        filename: 解析するファイル名

    Returns:
        抽出された日付、またはNone
    """
    for pattern in DATE_PATTERNS:
        match = pattern.search(filename)
        if match:
            try:
                return datetime.strptime(match.group(1), "%Y-%m-%d")
            except ValueError:
                continue
    return None


def is_screenshot(filename: str, patterns: list[str]) -> bool:
    """ファイルがスクリーンショットかどうかを判定する。

    Args:
        filename: 判定するファイル名
        patterns: スクリーンショットのファイル名パターンリスト

    Returns:
        スクリーンショットならTrue
    """
    return any(fnmatch.fnmatch(filename, pattern) for pattern in patterns)


def should_exclude(filename: str, exclude_patterns: list[str]) -> bool:
    """ファイルが除外対象かどうかを判定する。

    Args:
        filename: 判定するファイル名
        exclude_patterns: 除外パターンリスト

    Returns:
        除外対象ならTrue
    """
    return any(fnmatch.fnmatch(filename, pattern) for pattern in exclude_patterns)


def scan_desktop(config: dict[str, Any]) -> list[dict[str, Any]]:
    """デスクトップをスキャンし、整理計画を作成する。

    Args:
        config: 設定辞書

    Returns:
        移動計画のリスト。各要素は {source, destination, date, filename} を含む。
    """
    desktop_path = Path(config["desktop_path"]).expanduser()
    organized_folder = desktop_path / config["organized_folder"]
    screenshot_patterns = config["screenshot_patterns"]
    target_extensions = config["target_extensions"]
    exclude_patterns = config.get("exclude_patterns", [])
    group_by_date = config.get("group_by_date", True)
    date_format = config.get("date_folder_format", "%Y-%m")

    plan: list[dict[str, Any]] = []

    if not desktop_path.exists():
        raise FileNotFoundError(f"デスクトップが見つかりません: {desktop_path}")

    for item in desktop_path.iterdir():
        # ディレクトリはスキップ
        if item.is_dir():
            continue

        filename = item.name

        # 除外パターンに該当するものはスキップ
        if should_exclude(filename, exclude_patterns):
            continue

        # 拡張子チェック
        if item.suffix.lower() not in target_extensions:
            continue

        # スクリーンショットパターンに一致するか確認
        if not is_screenshot(filename, screenshot_patterns):
            continue

        # 日付を抽出
        file_date = extract_date(filename)

        # 移動先を決定
        if group_by_date and file_date:
            date_folder = file_date.strftime(date_format)
            destination = organized_folder / date_folder / filename
        else:
            destination = organized_folder / "other" / filename

        plan.append({
            "source": item,
            "destination": destination,
            "date": file_date,
            "filename": filename,
        })

    # 日付順にソート（日付なしは末尾）
    plan.sort(key=lambda x: x["date"] or datetime.min)

    return plan


def execute_plan(
    plan: list[dict[str, Any]],
    dry_run: bool = False,
) -> dict[str, int]:
    """整理計画を実行する。

    Args:
        plan: scan_desktopで作成した移動計画
        dry_run: Trueの場合、実際には移動しない

    Returns:
        実行結果の統計 {moved, skipped, errors}
    """
    stats = {"moved": 0, "skipped": 0, "errors": 0}

    for entry in plan:
        source: Path = entry["source"]
        destination: Path = entry["destination"]

        try:
            if destination.exists():
                stats["skipped"] += 1
                continue

            if not dry_run:
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(source), str(destination))

            stats["moved"] += 1
        except OSError as e:
            print(f"  エラー: {entry['filename']} - {e}")
            stats["errors"] += 1

    return stats
