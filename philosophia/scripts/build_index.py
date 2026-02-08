#!/usr/bin/env python3
"""
テーマ索引の自動更新スクリプト。

各素材ファイルのフロントマターからテーマタグを読み取り、
themes/*/index.md の関連素材リンクを更新する。

Usage:
    python scripts/build_index.py
"""

import sys
import re
from pathlib import Path


def extract_frontmatter(file_path: Path) -> dict:
    """Markdownファイルからフロントマターを抽出する。"""
    content = file_path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.+?)\n---", content, re.DOTALL)
    if not match:
        return {}

    frontmatter = {}
    for line in match.group(1).split("\n"):
        if ":" in line:
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()
            # 簡易的なYAMLリスト解析
            if value.startswith("[") and value.endswith("]"):
                items = value[1:-1].split(",")
                frontmatter[key] = [item.strip().strip("\"'") for item in items if item.strip()]
            else:
                frontmatter[key] = value
    return frontmatter


def scan_materials(project_dir: Path) -> dict:
    """全素材ファイルをスキャンし、テーマ別に分類する。"""
    theme_materials = {}

    # 断片メモ
    fragments_dir = project_dir / "output" / "fragments"
    if fragments_dir.exists():
        for f in sorted(fragments_dir.glob("*.md")):
            fm = extract_frontmatter(f)
            for theme in fm.get("themes", []):
                theme_materials.setdefault(theme, {"fragments": [], "dialogues": [], "essays": []})
                theme_materials[theme]["fragments"].append(f)

    # 対話記録
    dialogues_dir = project_dir / "output" / "dialogues"
    if dialogues_dir.exists():
        for f in sorted(dialogues_dir.glob("*.md")):
            fm = extract_frontmatter(f)
            for theme in fm.get("themes", []):
                theme_materials.setdefault(theme, {"fragments": [], "dialogues": [], "essays": []})
                theme_materials[theme]["dialogues"].append(f)

    # エッセイ
    essays_dir = project_dir / "output" / "essays"
    if essays_dir.exists():
        for f in sorted(essays_dir.glob("*.md")):
            fm = extract_frontmatter(f)
            for theme in fm.get("themes", []):
                theme_materials.setdefault(theme, {"fragments": [], "dialogues": [], "essays": []})
                theme_materials[theme]["essays"].append(f)

    return theme_materials


def main() -> None:
    project_dir = Path(__file__).parent.parent
    theme_materials = scan_materials(project_dir)

    if not theme_materials:
        print("テーマタグ付きの素材が見つかりませんでした。")
        print("素材ファイルのフロントマターに themes: [theme1, theme2] を追加してください。")
        return

    print("テーマ別素材数:")
    for theme, materials in sorted(theme_materials.items()):
        total = sum(len(v) for v in materials.values())
        print(f"  {theme}: {total} 件")
        for category, files in materials.items():
            if files:
                print(f"    {category}: {len(files)} 件")

    print("\nテーマ索引の更新は今後のフェーズで自動化されます。")
    print("現在は上記の情報を参考に手動で themes/*/index.md を更新してください。")


if __name__ == "__main__":
    main()
