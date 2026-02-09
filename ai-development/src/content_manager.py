"""コンテンツ管理のコアロジック

テキスト・画像エントリの統合管理を担当する。
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml

from src.text_handler import TextHandler
from src.image_handler import ImageHandler


class ContentManager:
    """ナレッジベース全体のコンテンツを管理するクラス"""

    def __init__(self, base_dir: Optional[Path] = None) -> None:
        """初期化

        Args:
            base_dir: プロジェクトルートディレクトリ。Noneの場合は自動検出。
        """
        self.base_dir = base_dir or Path(__file__).resolve().parent.parent
        self.config = self._load_config()
        self.text_handler = TextHandler(self.base_dir, self.config)
        self.image_handler = ImageHandler(self.base_dir, self.config)

    def _load_config(self) -> dict:
        """設定ファイルを読み込む"""
        config_path = self.base_dir / "config" / "settings.yaml"
        if not config_path.exists():
            raise FileNotFoundError(f"設定ファイルが見つかりません: {config_path}")
        with open(config_path, encoding="utf-8") as f:
            return yaml.safe_load(f)

    def add_text(
        self,
        title: str,
        body: str,
        category: str = "conversation",
        tags: Optional[list[str]] = None,
        source: Optional[str] = None,
    ) -> Path:
        """テキストエントリを追加する

        Args:
            title: エントリのタイトル
            body: 本文（Markdown形式）
            category: カテゴリ（conversation, decision, insight, specification, reference）
            tags: タグのリスト
            source: 情報源

        Returns:
            作成されたファイルのパス
        """
        return self.text_handler.create_entry(
            title=title,
            body=body,
            category=category,
            tags=tags,
            source=source,
        )

    def add_image(
        self,
        title: str,
        image_path: str,
        description: str = "",
        category: str = "reference",
        tags: Optional[list[str]] = None,
        source: Optional[str] = None,
    ) -> Path:
        """画像エントリを追加する

        Args:
            title: エントリのタイトル
            image_path: 画像ファイルのパス
            description: 画像の説明
            category: カテゴリ（diagram, screenshot, generated, reference, architecture）
            tags: タグのリスト
            source: 情報源

        Returns:
            作成されたメタデータファイルのパス
        """
        return self.image_handler.register_image(
            title=title,
            image_path=image_path,
            description=description,
            category=category,
            tags=tags,
            source=source,
        )

    def list_entries(
        self,
        content_type: Optional[str] = None,
        category: Optional[str] = None,
        tag: Optional[str] = None,
    ) -> list[dict]:
        """エントリ一覧を取得する

        Args:
            content_type: "text" or "images"。Noneの場合は両方。
            category: カテゴリでフィルタ
            tag: タグでフィルタ

        Returns:
            エントリ情報のリスト
        """
        entries: list[dict] = []

        if content_type is None or content_type == "text":
            entries.extend(self.text_handler.list_entries(category=category, tag=tag))

        if content_type is None or content_type == "images":
            entries.extend(self.image_handler.list_entries(category=category, tag=tag))

        entries.sort(key=lambda e: e.get("created_at", ""), reverse=True)
        return entries

    def search(self, query: str) -> list[dict]:
        """キーワードでエントリを検索する

        Args:
            query: 検索キーワード

        Returns:
            マッチしたエントリ情報のリスト
        """
        results: list[dict] = []
        query_lower = query.lower()

        for entry in self.list_entries():
            searchable = " ".join([
                entry.get("title", ""),
                entry.get("category", ""),
                " ".join(entry.get("tags", [])),
                entry.get("body", ""),
                entry.get("description", ""),
            ]).lower()

            if query_lower in searchable:
                results.append(entry)

        return results

    def update_index(self) -> Path:
        """INDEX.md を再生成する

        Returns:
            INDEX.mdのパス
        """
        index_path = self.base_dir / self.config["output"]["index_file"]
        entries = self.list_entries()

        lines = [
            "# AI開発 ナレッジベース インデックス",
            "",
            f"最終更新: {datetime.now().strftime(self.config['output']['datetime_format'])}",
            "",
            f"総エントリ数: {len(entries)}",
            "",
        ]

        # テキストエントリ
        text_entries = [e for e in entries if e["type"] == "text"]
        if text_entries:
            lines.append("## テキスト")
            lines.append("")
            for entry in text_entries:
                tags_str = ", ".join(entry.get("tags", []))
                tags_display = f" `{tags_str}`" if tags_str else ""
                lines.append(
                    f"- [{entry['title']}]({entry['path']}) "
                    f"[{entry['category']}]{tags_display} "
                    f"({entry['created_at']})"
                )
            lines.append("")

        # 画像エントリ
        image_entries = [e for e in entries if e["type"] == "image"]
        if image_entries:
            lines.append("## 画像")
            lines.append("")
            for entry in image_entries:
                tags_str = ", ".join(entry.get("tags", []))
                tags_display = f" `{tags_str}`" if tags_str else ""
                lines.append(
                    f"- [{entry['title']}]({entry['path']}) "
                    f"[{entry['category']}]{tags_display} "
                    f"({entry['created_at']})"
                )
            lines.append("")

        index_path.parent.mkdir(parents=True, exist_ok=True)
        index_path.write_text("\n".join(lines), encoding="utf-8")
        return index_path

    def get_stats(self) -> dict:
        """ナレッジベースの統計情報を返す"""
        entries = self.list_entries()
        text_entries = [e for e in entries if e["type"] == "text"]
        image_entries = [e for e in entries if e["type"] == "image"]

        text_categories: dict[str, int] = {}
        for e in text_entries:
            cat = e.get("category", "unknown")
            text_categories[cat] = text_categories.get(cat, 0) + 1

        image_categories: dict[str, int] = {}
        for e in image_entries:
            cat = e.get("category", "unknown")
            image_categories[cat] = image_categories.get(cat, 0) + 1

        return {
            "total": len(entries),
            "text_count": len(text_entries),
            "image_count": len(image_entries),
            "text_by_category": text_categories,
            "image_by_category": image_categories,
        }
