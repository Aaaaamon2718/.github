"""FAISS ベクトル検索 RAG のテスト。

sentence-transformers / faiss-cpu がインストールされていない環境でも
テストがスキップされるようにしている。
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.chat.rag import KnowledgeChunk, SearchResult


@pytest.fixture
def sample_chunks() -> list[KnowledgeChunk]:
    """テスト用チャンクデータ。"""
    return [
        KnowledgeChunk(
            content="赤字決算の社長へのアプローチ。赤字の会社こそ保障が必要です。",
            source_file="corporate/financial.md",
            category="法人保険",
            metadata={"category": "法人保険"},
            pattern_ids=[3],
        ),
        KnowledgeChunk(
            content="ドクターマーケットの開拓方法。医師には信頼関係が何より大事。",
            source_file="doctor/approach.md",
            category="ドクターマーケット",
            metadata={"category": "ドクターマーケット"},
            pattern_ids=[2],
        ),
        KnowledgeChunk(
            content="営業の心構え。誰にでもできることを、だれにも負けないほどやる。",
            source_file="shared/quotes.md",
            category="共通",
            metadata={"category": "営業マインド"},
            pattern_ids=[1, 2, 3, 4],
        ),
    ]


@pytest.fixture
def mock_embedding():
    """EmbeddingModelのモック。768次元の決定的ベクトルを返す。

    全ベクトルが正のコサイン類似度を持つように基底ベクトルに
    小さな差分を加える方式。
    """
    model = MagicMock()
    model.dimension = 768

    _counter = [0]

    def _make_vec() -> np.ndarray:
        vec = np.ones(768, dtype=np.float32)
        idx = _counter[0] % 768
        vec[idx] += 1.0
        vec /= np.linalg.norm(vec)
        _counter[0] += 1
        return vec

    def _encode_query(query: str) -> np.ndarray:
        return _make_vec()

    def _encode_passages(passages: list[str]) -> np.ndarray:
        return np.array([_make_vec() for _ in passages], dtype=np.float32)

    model.encode_query = _encode_query
    model.encode_passages = _encode_passages
    return model


faiss = pytest.importorskip("faiss", reason="faiss-cpu が未インストール")


class TestVectorRAG:
    """VectorRAG のテスト。"""

    def test_build_index(
        self, sample_chunks: list[KnowledgeChunk], mock_embedding: MagicMock
    ) -> None:
        """インデックスが正しく構築されること。"""
        from src.chat.vector_rag import VectorRAG

        rag = VectorRAG(
            chunks=sample_chunks,
            embedding_model=mock_embedding,
            similarity_threshold=0.0,
        )
        assert rag.index is not None
        assert rag.index.ntotal == 3

    def test_search_returns_results(
        self, sample_chunks: list[KnowledgeChunk], mock_embedding: MagicMock
    ) -> None:
        """検索が結果を返すこと。"""
        from src.chat.vector_rag import VectorRAG

        rag = VectorRAG(
            chunks=sample_chunks,
            embedding_model=mock_embedding,
            similarity_threshold=0.0,
        )
        results = rag.search("赤字決算", top_k=3)
        assert len(results) > 0
        assert all(isinstance(r, SearchResult) for r in results)

    def test_search_top_k_limit(
        self, sample_chunks: list[KnowledgeChunk], mock_embedding: MagicMock
    ) -> None:
        """top_k制限が効くこと。"""
        from src.chat.vector_rag import VectorRAG

        rag = VectorRAG(
            chunks=sample_chunks,
            embedding_model=mock_embedding,
            similarity_threshold=0.0,
        )
        results = rag.search("保険", top_k=1)
        assert len(results) <= 1

    def test_search_empty_index(self, mock_embedding: MagicMock) -> None:
        """空インデックスで空リストが返ること。"""
        from src.chat.vector_rag import VectorRAG

        rag = VectorRAG(
            chunks=[],
            embedding_model=mock_embedding,
            similarity_threshold=0.0,
        )
        results = rag.search("テスト")
        assert results == []

    def test_similarity_threshold_filter(
        self, sample_chunks: list[KnowledgeChunk], mock_embedding: MagicMock
    ) -> None:
        """類似度閾値でフィルタされること。"""
        from src.chat.vector_rag import VectorRAG

        rag = VectorRAG(
            chunks=sample_chunks,
            embedding_model=mock_embedding,
            similarity_threshold=1.0,
        )
        results = rag.search("全く関係ないクエリ12345")
        assert len(results) == 0

    def test_format_context(
        self, sample_chunks: list[KnowledgeChunk], mock_embedding: MagicMock
    ) -> None:
        """コンテキスト文字列が整形されること。"""
        from src.chat.vector_rag import VectorRAG

        rag = VectorRAG(
            chunks=sample_chunks,
            embedding_model=mock_embedding,
            similarity_threshold=0.0,
        )
        results = rag.search("赤字決算")
        context = rag.format_context(results)
        if results:
            assert "【参照1】" in context
            assert "類似度:" in context

    def test_format_context_empty(
        self, mock_embedding: MagicMock
    ) -> None:
        """結果なしのフォーマット。"""
        from src.chat.vector_rag import VectorRAG

        rag = VectorRAG(
            chunks=[],
            embedding_model=mock_embedding,
        )
        context = rag.format_context([])
        assert "見つかりませんでした" in context

    def test_get_sources_unique(
        self, sample_chunks: list[KnowledgeChunk], mock_embedding: MagicMock
    ) -> None:
        """出典リストに重複がないこと。"""
        from src.chat.vector_rag import VectorRAG

        rag = VectorRAG(
            chunks=sample_chunks,
            embedding_model=mock_embedding,
            similarity_threshold=0.0,
        )
        results = rag.search("保険")
        sources = rag.get_sources(results)
        assert len(sources) == len(set(sources))

    def test_save_and_load_index(
        self,
        sample_chunks: list[KnowledgeChunk],
        mock_embedding: MagicMock,
        tmp_path: Path,
    ) -> None:
        """インデックスの保存と読み込みが正しく動くこと。"""
        from src.chat.vector_rag import VectorRAG

        index_path = tmp_path / "test_index"

        rag1 = VectorRAG(
            chunks=sample_chunks,
            embedding_model=mock_embedding,
            index_path=index_path,
            similarity_threshold=0.0,
        )
        assert (index_path / "index.faiss").exists()
        assert (index_path / "chunks.json").exists()

        rag2 = VectorRAG(
            chunks=[],
            embedding_model=mock_embedding,
            index_path=index_path,
            similarity_threshold=0.0,
        )
        assert rag2.index.ntotal == 3
        assert len(rag2.chunks) == 3

    def test_rebuild_index(
        self, sample_chunks: list[KnowledgeChunk], mock_embedding: MagicMock
    ) -> None:
        """rebuild_indexでインデックスが再構築されること。"""
        from src.chat.vector_rag import VectorRAG

        rag = VectorRAG(
            chunks=sample_chunks,
            embedding_model=mock_embedding,
            similarity_threshold=0.0,
        )
        assert rag.index.ntotal == 3

        rag.chunks = sample_chunks[:1]
        rag.rebuild_index()
        assert rag.index.ntotal == 1

    def test_search_pattern_filter(
        self, sample_chunks: list[KnowledgeChunk], mock_embedding: MagicMock
    ) -> None:
        """パターン指定で正しくフィルタされること。"""
        from src.chat.vector_rag import VectorRAG

        rag = VectorRAG(
            chunks=sample_chunks,
            embedding_model=mock_embedding,
            similarity_threshold=0.0,
        )
        # パターン3（法人保険）で検索 → corporate + shared のみ
        results = rag.search("保険", top_k=5, pattern=3)
        for r in results:
            assert 3 in r.chunk.pattern_ids

    def test_search_pattern_excludes_other(
        self, sample_chunks: list[KnowledgeChunk], mock_embedding: MagicMock
    ) -> None:
        """パターン指定で他パターン専用チャンクが除外されること。"""
        from src.chat.vector_rag import VectorRAG

        rag = VectorRAG(
            chunks=sample_chunks,
            embedding_model=mock_embedding,
            similarity_threshold=0.0,
        )
        # パターン1で検索 → doctor(pattern=2), corporate(pattern=3) は除外
        results = rag.search("保険", top_k=5, pattern=1)
        for r in results:
            assert "doctor" not in r.chunk.source_file
            assert "corporate" not in r.chunk.source_file

    def test_search_no_pattern_returns_all(
        self, sample_chunks: list[KnowledgeChunk], mock_embedding: MagicMock
    ) -> None:
        """パターンなしで全チャンクが返ること。"""
        from src.chat.vector_rag import VectorRAG

        rag = VectorRAG(
            chunks=sample_chunks,
            embedding_model=mock_embedding,
            similarity_threshold=0.0,
        )
        results = rag.search("保険", top_k=5)
        assert len(results) == 3  # 全3チャンク

    def test_save_load_preserves_pattern_ids(
        self,
        sample_chunks: list[KnowledgeChunk],
        mock_embedding: MagicMock,
        tmp_path: Path,
    ) -> None:
        """保存・読み込みでpattern_idsが保持されること。"""
        from src.chat.vector_rag import VectorRAG

        index_path = tmp_path / "test_index"
        VectorRAG(
            chunks=sample_chunks,
            embedding_model=mock_embedding,
            index_path=index_path,
            similarity_threshold=0.0,
        )

        rag2 = VectorRAG(
            chunks=[],
            embedding_model=mock_embedding,
            index_path=index_path,
            similarity_threshold=0.0,
        )
        assert rag2.chunks[0].pattern_ids == [3]
        assert rag2.chunks[1].pattern_ids == [2]
        assert rag2.chunks[2].pattern_ids == [1, 2, 3, 4]


class TestCreateRag:
    """create_rag ファクトリ関数のテスト。"""

    def test_fallback_to_simple_rag(
        self, sample_chunks: list[KnowledgeChunk]
    ) -> None:
        """use_vector=Falseの場合SimpleRAGにフォールバックすること。"""
        from src.chat.rag import SimpleRAG
        from src.chat.vector_rag import create_rag

        rag = create_rag(chunks=sample_chunks, use_vector=False)
        assert isinstance(rag, SimpleRAG)

    def test_create_vector_rag(
        self,
        sample_chunks: list[KnowledgeChunk],
        mock_embedding: MagicMock,
    ) -> None:
        """VectorRAGが作成されること（モック使用）。"""
        from src.chat.vector_rag import VectorRAG, create_rag

        with patch(
            "src.chat.vector_rag.EmbeddingModel", return_value=mock_embedding
        ):
            rag = create_rag(chunks=sample_chunks, use_vector=True)
            assert isinstance(rag, VectorRAG)
