"""ContentManager の基本テスト"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest
import yaml

from src.content_manager import ContentManager


@pytest.fixture
def temp_project(tmp_path: Path) -> Path:
    """テスト用の一時プロジェクトディレクトリを作成する"""
    # 設定ファイルのコピー
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    src_config = Path(__file__).resolve().parent.parent / "config" / "settings.yaml"
    shutil.copy2(src_config, config_dir / "settings.yaml")

    # src ディレクトリ
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    src_root = Path(__file__).resolve().parent.parent / "src"
    for py_file in src_root.glob("*.py"):
        shutil.copy2(py_file, src_dir / py_file.name)

    # content ディレクトリ
    (tmp_path / "content" / "text").mkdir(parents=True)
    (tmp_path / "content" / "images").mkdir(parents=True)

    return tmp_path


@pytest.fixture
def manager(temp_project: Path) -> ContentManager:
    """ContentManager インスタンスを作成する"""
    return ContentManager(base_dir=temp_project)


class TestAddText:
    """テキストエントリの追加テスト"""

    def test_basic_add(self, manager: ContentManager) -> None:
        path = manager.add_text(
            title="テスト会話",
            body="これはテストの本文です。",
            category="conversation",
        )
        assert path.exists()
        assert path.suffix == ".md"
        content = path.read_text(encoding="utf-8")
        assert "テスト会話" in content
        assert "これはテストの本文です。" in content

    def test_add_with_tags(self, manager: ContentManager) -> None:
        path = manager.add_text(
            title="タグ付きエントリ",
            body="タグのテスト",
            category="decision",
            tags=["設計", "v1"],
        )
        content = path.read_text(encoding="utf-8")
        assert "設計" in content
        assert "v1" in content

    def test_add_with_source(self, manager: ContentManager) -> None:
        path = manager.add_text(
            title="ソース付き",
            body="テスト",
            source="Claude Code session #123",
        )
        content = path.read_text(encoding="utf-8")
        assert "Claude Code session #123" in content

    def test_category_directory(self, manager: ContentManager, temp_project: Path) -> None:
        manager.add_text(title="仕様テスト", body="内容", category="specification")
        spec_dir = temp_project / "content" / "text" / "specification"
        assert spec_dir.exists()
        md_files = list(spec_dir.glob("*.md"))
        assert len(md_files) == 1


class TestAddImage:
    """画像エントリの追加テスト"""

    def test_basic_add(self, manager: ContentManager, tmp_path: Path) -> None:
        # テスト画像を作成
        test_image = tmp_path / "test_image.png"
        test_image.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        path = manager.add_image(
            title="テスト画像",
            image_path=str(test_image),
            description="テスト用の画像です",
            category="reference",
        )
        assert path.exists()
        assert path.suffix == ".yaml"

        with open(path, encoding="utf-8") as f:
            meta = yaml.safe_load(f)
        assert meta["title"] == "テスト画像"
        assert meta["description"] == "テスト用の画像です"

    def test_unsupported_format(self, manager: ContentManager, tmp_path: Path) -> None:
        test_file = tmp_path / "test.bmp"
        test_file.write_bytes(b"\x00" * 10)

        with pytest.raises(ValueError, match="サポートされていない画像形式"):
            manager.add_image(title="BMP", image_path=str(test_file))

    def test_missing_file(self, manager: ContentManager) -> None:
        with pytest.raises(FileNotFoundError):
            manager.add_image(title="存在しない", image_path="/nonexistent/image.png")


class TestListEntries:
    """エントリ一覧テスト"""

    def test_empty(self, manager: ContentManager) -> None:
        entries = manager.list_entries()
        assert entries == []

    def test_list_text(self, manager: ContentManager) -> None:
        manager.add_text(title="エントリ1", body="内容1", category="conversation")
        manager.add_text(title="エントリ2", body="内容2", category="decision")
        entries = manager.list_entries(content_type="text")
        assert len(entries) == 2

    def test_filter_by_category(self, manager: ContentManager) -> None:
        manager.add_text(title="会話1", body="a", category="conversation")
        manager.add_text(title="決定1", body="b", category="decision")
        entries = manager.list_entries(content_type="text", category="conversation")
        assert len(entries) == 1
        assert entries[0]["title"] == "会話1"


class TestSearch:
    """検索テスト"""

    def test_search_by_title(self, manager: ContentManager) -> None:
        manager.add_text(title="認証システムの設計", body="OAuth 2.0 を採用", category="specification")
        manager.add_text(title="データベース設計", body="PostgreSQL", category="specification")

        results = manager.search("認証")
        assert len(results) == 1
        assert results[0]["title"] == "認証システムの設計"

    def test_search_by_body(self, manager: ContentManager) -> None:
        manager.add_text(title="技術選定", body="FastAPI を採用する", category="decision")
        results = manager.search("FastAPI")
        assert len(results) == 1

    def test_no_results(self, manager: ContentManager) -> None:
        manager.add_text(title="テスト", body="内容", category="conversation")
        results = manager.search("存在しないキーワード")
        assert results == []


class TestStats:
    """統計テスト"""

    def test_empty_stats(self, manager: ContentManager) -> None:
        stats = manager.get_stats()
        assert stats["total"] == 0
        assert stats["text_count"] == 0
        assert stats["image_count"] == 0

    def test_stats_with_entries(self, manager: ContentManager) -> None:
        manager.add_text(title="A", body="a", category="conversation")
        manager.add_text(title="B", body="b", category="conversation")
        manager.add_text(title="C", body="c", category="decision")

        stats = manager.get_stats()
        assert stats["total"] == 3
        assert stats["text_count"] == 3
        assert stats["text_by_category"]["conversation"] == 2
        assert stats["text_by_category"]["decision"] == 1
