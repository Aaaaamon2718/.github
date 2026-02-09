"""画像コンテンツの管理

画像ファイルの登録・メタデータ管理・一覧を担当する。
"""

from __future__ import annotations

import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml


class ImageHandler:
    """画像エントリの管理クラス"""

    def __init__(self, base_dir: Path, config: dict) -> None:
        self.base_dir = base_dir
        self.config = config
        self.image_dir = base_dir / config["content"]["images"]["directory"]
        self.image_dir.mkdir(parents=True, exist_ok=True)
        self.allowed_extensions = config["content"]["images"]["allowed_extensions"]

    def register_image(
        self,
        title: str,
        image_path: str,
        description: str = "",
        category: str = "reference",
        tags: Optional[list[str]] = None,
        source: Optional[str] = None,
    ) -> Path:
        """画像を登録する（コピー + メタデータ作成）

        Args:
            title: タイトル
            image_path: 元画像ファイルのパス
            description: 画像の説明
            category: カテゴリ
            tags: タグリスト
            source: 情報源

        Returns:
            作成されたメタデータファイルのパス
        """
        src_path = Path(image_path).resolve()
        if not src_path.exists():
            raise FileNotFoundError(f"画像ファイルが見つかりません: {image_path}")

        ext = src_path.suffix.lower()
        if ext not in self.allowed_extensions:
            raise ValueError(
                f"サポートされていない画像形式: {ext}  "
                f"(許可: {', '.join(self.allowed_extensions)})"
            )

        now = datetime.now()
        date_str = now.strftime(self.config["output"]["date_format"])
        datetime_str = now.strftime(self.config["output"]["datetime_format"])

        slug = self._slugify(title)

        # カテゴリディレクトリ
        category_dir = self.image_dir / category
        category_dir.mkdir(parents=True, exist_ok=True)

        # 画像ファイルをコピー
        image_filename = f"{date_str}_{slug}{ext}"
        dest_image = category_dir / image_filename
        counter = 1
        while dest_image.exists():
            image_filename = f"{date_str}_{slug}_{counter}{ext}"
            dest_image = category_dir / image_filename
            counter += 1

        shutil.copy2(src_path, dest_image)

        # メタデータファイル作成
        meta_filename = f"{date_str}_{slug}.meta.yaml"
        meta_path = category_dir / meta_filename

        metadata = {
            "title": title,
            "category": category,
            "created_at": datetime_str,
            "image_file": image_filename,
            "original_path": str(src_path),
            "description": description,
            "tags": tags or [],
            "source": source or "",
            "status": "draft",
        }

        with open(meta_path, "w", encoding="utf-8") as f:
            yaml.dump(metadata, f, allow_unicode=True, default_flow_style=False)

        return meta_path

    def read_entry(self, meta_path: Path) -> dict:
        """画像エントリのメタデータを読み込む

        Args:
            meta_path: メタデータファイルのパス

        Returns:
            パースされたエントリ情報
        """
        with open(meta_path, encoding="utf-8") as f:
            metadata = yaml.safe_load(f) or {}

        image_file = metadata.get("image_file", "")
        image_path = meta_path.parent / image_file if image_file else None

        return {
            "type": "image",
            "path": str(meta_path.relative_to(self.base_dir)),
            "image_path": str(image_path.relative_to(self.base_dir)) if image_path else "",
            "title": metadata.get("title", ""),
            "category": metadata.get("category", ""),
            "created_at": metadata.get("created_at", ""),
            "description": metadata.get("description", ""),
            "tags": metadata.get("tags", []),
            "source": metadata.get("source", ""),
            "status": metadata.get("status", ""),
        }

    def list_entries(
        self,
        category: Optional[str] = None,
        tag: Optional[str] = None,
    ) -> list[dict]:
        """画像エントリの一覧を取得する

        Args:
            category: カテゴリでフィルタ
            tag: タグでフィルタ

        Returns:
            エントリ情報のリスト
        """
        entries: list[dict] = []

        search_dirs = []
        if category:
            cat_dir = self.image_dir / category
            if cat_dir.exists():
                search_dirs.append(cat_dir)
        else:
            search_dirs = [
                d for d in self.image_dir.iterdir()
                if d.is_dir() and not d.name.startswith(".")
            ]

        for search_dir in search_dirs:
            for meta_file in search_dir.glob("*.meta.yaml"):
                try:
                    entry = self.read_entry(meta_file)
                    if tag and tag not in entry.get("tags", []):
                        continue
                    entries.append(entry)
                except Exception:
                    continue

        return entries

    def _slugify(self, text: str) -> str:
        """タイトルをファイル名用のスラグに変換する"""
        slug = re.sub(r"[^\w\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF-]", "_", text)
        slug = re.sub(r"_+", "_", slug).strip("_")
        if len(slug) > 80:
            slug = slug[:80].rstrip("_")
        return slug
