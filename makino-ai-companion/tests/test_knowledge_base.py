"""ナレッジベース処理のテスト。"""

import csv
import tempfile
from pathlib import Path

import pytest

from src.knowledge_base.processor import (
    VALID_CATEGORIES,
    VALID_PRIORITIES,
    KnowledgeEntry,
    generate_stats,
    get_entries_by_category,
    load_knowledge_csv,
    validate_entry,
    validate_knowledge_base,
)


@pytest.fixture
def sample_entry() -> KnowledgeEntry:
    """テスト用のサンプルエントリ。"""
    return KnowledgeEntry(
        entry_id="QA_001",
        category="法人保険",
        sub_category="決算書分析",
        question_topic="赤字決算の社長へのアプローチ方法は？",
        answer_content="赤字決算の場合は...",
        source="牧野生保塾 Vol.5 (2024/05)",
        expression_tags=["断定", "論理的"],
        emotion_tag="論理的解説",
        priority="高",
    )


@pytest.fixture
def sample_csv(tmp_path: Path) -> Path:
    """テスト用のCSVファイルを作成する。"""
    csv_path = tmp_path / "test_kb.csv"
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "ID", "カテゴリ", "サブカテゴリ", "質問/トピック",
            "回答/内容", "出典", "言い回しタグ", "感情タグ", "優先度",
        ])
        writer.writerow([
            "QA_001", "法人保険", "決算書分析", "テスト質問1",
            "テスト回答1", "テスト出典1", "断定", "論理的解説", "高",
        ])
        writer.writerow([
            "QA_002", "ドクターマーケット", "アプローチ", "テスト質問2",
            "テスト回答2", "テスト出典2", "比喩表現", "励まし", "中",
        ])
    return csv_path


class TestKnowledgeEntry:
    """KnowledgeEntryのテスト。"""

    def test_valid_entry(self, sample_entry: KnowledgeEntry) -> None:
        """正常なエントリのバリデーション。"""
        errors = validate_entry(sample_entry)
        assert errors == []

    def test_empty_id(self, sample_entry: KnowledgeEntry) -> None:
        """空のIDはエラーとなること。"""
        sample_entry.entry_id = ""
        errors = validate_entry(sample_entry)
        assert "IDが空です" in errors

    def test_invalid_category(self, sample_entry: KnowledgeEntry) -> None:
        """無効なカテゴリはエラーとなること。"""
        sample_entry.category = "無効カテゴリ"
        errors = validate_entry(sample_entry)
        assert any("無効なカテゴリ" in e for e in errors)

    def test_invalid_priority(self, sample_entry: KnowledgeEntry) -> None:
        """無効な優先度はエラーとなること。"""
        sample_entry.priority = "最高"
        errors = validate_entry(sample_entry)
        assert any("無効な優先度" in e for e in errors)


class TestLoadKnowledgeCsv:
    """CSV読み込みのテスト。"""

    def test_load_valid_csv(self, sample_csv: Path) -> None:
        """正常なCSVの読み込み。"""
        entries = load_knowledge_csv(sample_csv)
        assert len(entries) == 2
        assert entries[0].entry_id == "QA_001"
        assert entries[1].entry_id == "QA_002"

    def test_file_not_found(self) -> None:
        """存在しないファイルでFileNotFoundErrorが発生すること。"""
        with pytest.raises(FileNotFoundError):
            load_knowledge_csv("/nonexistent/path.csv")


class TestGenerateStats:
    """統計情報生成のテスト。"""

    def test_stats(self, sample_csv: Path) -> None:
        """統計情報が正しく算出されること。"""
        entries = load_knowledge_csv(sample_csv)
        stats = generate_stats(entries)
        assert stats["total"] == 2
        assert stats["priority_high"] == 1
        assert stats["priority_medium"] == 1
        assert stats["category_法人保険"] == 1
        assert stats["category_ドクターマーケット"] == 1


class TestGetEntriesByCategory:
    """カテゴリフィルタのテスト。"""

    def test_filter_by_category(self, sample_csv: Path) -> None:
        """カテゴリでフィルタできること。"""
        entries = load_knowledge_csv(sample_csv)
        filtered = get_entries_by_category(entries, "法人保険")
        assert len(filtered) == 1
        assert filtered[0].category == "法人保険"

    def test_filter_by_priority(self, sample_csv: Path) -> None:
        """カテゴリと優先度でフィルタできること。"""
        entries = load_knowledge_csv(sample_csv)
        filtered = get_entries_by_category(entries, "法人保険", priority="高")
        assert len(filtered) == 1
