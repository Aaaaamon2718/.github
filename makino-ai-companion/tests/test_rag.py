"""RAGエンジンのテスト。"""

import tempfile
from pathlib import Path

import pytest

from src.chat.rag import KnowledgeChunk, KnowledgeLoader, SearchResult, SimpleRAG


@pytest.fixture
def knowledge_dir(tmp_path: Path) -> Path:
    """テスト用ナレッジディレクトリを作成する。"""
    # qa/sample.md
    qa_dir = tmp_path / "qa"
    qa_dir.mkdir()
    (qa_dir / "sample.md").write_text(
        """---
category: 法人保険
sub_category: 決算書分析
source: テスト
priority: high
tags: [断定, 論理的解説]
---

# 赤字決算の社長へのアプローチ

## ポイント
赤字の会社こそ保障が必要です。決算書のP/Lを見せてもらい、
赤字の原因を社長に聞くことから始めます。

## 退職金の話へ
そこから退職金の準備状況を確認します。
赤字の会社ほど退職金の準備ができていないのが実情です。
""",
        encoding="utf-8",
    )

    # seminars/test.md
    sem_dir = tmp_path / "seminars"
    sem_dir.mkdir()
    (sem_dir / "test.md").write_text(
        """---
category: 営業マインド
source: 牧野生保塾 Vol.1
priority: high
---

# 営業の心構え

プロなら言い訳はしない。結果を出すために何をするか、それだけを考えなさい。
誰にでもできることを、だれにも負けないほどやる。
""",
        encoding="utf-8",
    )

    return tmp_path


class TestKnowledgeLoader:
    """KnowledgeLoaderのテスト。"""

    def test_load_all(self, knowledge_dir: Path) -> None:
        """全ファイルを読み込めること。"""
        loader = KnowledgeLoader(knowledge_dir)
        chunks = loader.load_all()
        assert len(chunks) > 0

    def test_load_empty_dir(self, tmp_path: Path) -> None:
        """空ディレクトリでも例外が出ないこと。"""
        loader = KnowledgeLoader(tmp_path)
        chunks = loader.load_all()
        assert chunks == []

    def test_load_nonexistent_dir(self, tmp_path: Path) -> None:
        """存在しないディレクトリでも例外が出ないこと。"""
        loader = KnowledgeLoader(tmp_path / "nonexistent")
        chunks = loader.load_all()
        assert chunks == []

    def test_chunk_has_metadata(self, knowledge_dir: Path) -> None:
        """チャンクにメタデータが含まれること。"""
        loader = KnowledgeLoader(knowledge_dir)
        chunks = loader.load_all()
        qa_chunks = [c for c in chunks if "qa" in c.source_file]
        assert len(qa_chunks) > 0
        assert qa_chunks[0].metadata.get("category") == "法人保険"

    def test_chunk_size_limit(self, knowledge_dir: Path) -> None:
        """チャンクサイズが制限内であること。"""
        loader = KnowledgeLoader(knowledge_dir, chunk_size=100)
        chunks = loader.load_all()
        for chunk in chunks:
            # chunk_overlapの影響で少し超える場合があるが、2倍以内
            assert len(chunk.content) <= 200

    def test_category_inference(self, knowledge_dir: Path) -> None:
        """ディレクトリ名からカテゴリが推定されること。"""
        loader = KnowledgeLoader(knowledge_dir)
        chunks = loader.load_all()
        categories = {c.category for c in chunks}
        assert "Q&A" in categories or "牧野生保塾" in categories


class TestSimpleRAG:
    """SimpleRAGのテスト。"""

    @pytest.fixture
    def rag(self, knowledge_dir: Path) -> SimpleRAG:
        loader = KnowledgeLoader(knowledge_dir)
        return SimpleRAG(loader.load_all())

    def test_search_returns_results(self, rag: SimpleRAG) -> None:
        """関連キーワードで検索結果が返ること。"""
        results = rag.search("赤字 決算 社長")
        assert len(results) > 0
        assert results[0].score > 0

    def test_search_no_results(self, rag: SimpleRAG) -> None:
        """無関係なクエリで結果が空になること。"""
        results = rag.search("xyz無関係なクエリ12345")
        assert len(results) == 0

    def test_search_top_k(self, rag: SimpleRAG) -> None:
        """top_k制限が効くこと。"""
        results = rag.search("保険", top_k=1)
        assert len(results) <= 1

    def test_format_context(self, rag: SimpleRAG) -> None:
        """コンテキスト文字列が整形されること。"""
        results = rag.search("赤字 決算")
        context = rag.format_context(results)
        if results:
            assert "【参照1】" in context
        else:
            assert "見つかりませんでした" in context

    def test_format_context_empty(self, rag: SimpleRAG) -> None:
        """結果がない場合のフォーマット。"""
        context = rag.format_context([])
        assert "見つかりませんでした" in context

    def test_get_sources(self, rag: SimpleRAG) -> None:
        """出典リストに重複がないこと。"""
        results = rag.search("保険 決算")
        sources = rag.get_sources(results)
        assert len(sources) == len(set(sources))
