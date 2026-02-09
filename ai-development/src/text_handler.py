"""テキストコンテンツの管理

Markdown形式のテキストエントリの作成・読取・一覧を担当する。
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml


class TextHandler:
    """テキストエントリの管理クラス"""

    def __init__(self, base_dir: Path, config: dict) -> None:
        self.base_dir = base_dir
        self.config = config
        self.text_dir = base_dir / config["content"]["text"]["directory"]
        self.text_dir.mkdir(parents=True, exist_ok=True)

    def create_entry(
        self,
        title: str,
        body: str,
        category: str = "conversation",
        tags: Optional[list[str]] = None,
        source: Optional[str] = None,
    ) -> Path:
        """テキストエントリを新規作成する

        Args:
            title: タイトル
            body: 本文（Markdown）
            category: カテゴリ
            tags: タグリスト
            source: 情報源

        Returns:
            作成されたファイルのパス
        """
        now = datetime.now()
        date_str = now.strftime(self.config["output"]["date_format"])
        datetime_str = now.strftime(self.config["output"]["datetime_format"])

        # ファイル名生成: YYYY-MM-DD_slug.md
        slug = self._slugify(title)
        filename = f"{date_str}_{slug}.md"

        # カテゴリディレクトリ
        category_dir = self.text_dir / category
        category_dir.mkdir(parents=True, exist_ok=True)
        file_path = category_dir / filename

        # 重複回避
        counter = 1
        while file_path.exists():
            filename = f"{date_str}_{slug}_{counter}.md"
            file_path = category_dir / filename
            counter += 1

        # YAML Front Matter + 本文
        frontmatter = {
            "title": title,
            "category": category,
            "created_at": datetime_str,
            "updated_at": datetime_str,
            "tags": tags or [],
            "source": source or "",
            "status": "draft",
        }

        content_lines = [
            "---",
            yaml.dump(frontmatter, allow_unicode=True, default_flow_style=False).strip(),
            "---",
            "",
            f"# {title}",
            "",
            body,
            "",
        ]

        file_path.write_text("\n".join(content_lines), encoding="utf-8")
        return file_path

    def read_entry(self, file_path: Path) -> dict:
        """テキストエントリを読み込む

        Args:
            file_path: エントリファイルのパス

        Returns:
            パースされたエントリ情報
        """
        text = file_path.read_text(encoding="utf-8")
        frontmatter, body = self._parse_frontmatter(text)

        return {
            "type": "text",
            "path": str(file_path.relative_to(self.base_dir)),
            "title": frontmatter.get("title", ""),
            "category": frontmatter.get("category", ""),
            "created_at": frontmatter.get("created_at", ""),
            "updated_at": frontmatter.get("updated_at", ""),
            "tags": frontmatter.get("tags", []),
            "source": frontmatter.get("source", ""),
            "status": frontmatter.get("status", ""),
            "body": body.strip(),
        }

    def list_entries(
        self,
        category: Optional[str] = None,
        tag: Optional[str] = None,
    ) -> list[dict]:
        """テキストエントリの一覧を取得する

        Args:
            category: カテゴリでフィルタ
            tag: タグでフィルタ

        Returns:
            エントリ情報のリスト
        """
        entries: list[dict] = []

        search_dirs = []
        if category:
            cat_dir = self.text_dir / category
            if cat_dir.exists():
                search_dirs.append(cat_dir)
        else:
            search_dirs = [
                d for d in self.text_dir.iterdir()
                if d.is_dir() and not d.name.startswith(".")
            ]

        for search_dir in search_dirs:
            for md_file in search_dir.glob("*.md"):
                try:
                    entry = self.read_entry(md_file)
                    if tag and tag not in entry.get("tags", []):
                        continue
                    entries.append(entry)
                except Exception:
                    continue

        return entries

    def _slugify(self, text: str) -> str:
        """タイトルをファイル名用のスラグに変換する"""
        # 英数字・ひらがな・カタカナ・漢字・ハイフン・アンダースコア以外を除去
        slug = re.sub(r"[^\w\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF-]", "_", text)
        slug = re.sub(r"_+", "_", slug).strip("_")
        # 長すぎる場合は切り詰め
        if len(slug) > 80:
            slug = slug[:80].rstrip("_")
        return slug

    def _parse_frontmatter(self, text: str) -> tuple[dict, str]:
        """YAML Front Matterと本文を分離する"""
        pattern = r"^---\s*\n(.*?)\n---\s*\n(.*)$"
        match = re.match(pattern, text, re.DOTALL)
        if match:
            fm_text = match.group(1)
            body = match.group(2)
            try:
                frontmatter = yaml.safe_load(fm_text) or {}
            except yaml.YAMLError:
                frontmatter = {}
            return frontmatter, body
        return {}, text
