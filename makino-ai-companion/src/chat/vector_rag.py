"""FAISS ベクトル検索による RAG エンジン。

SimpleRAG のキーワードマッチングを置き換え、
意味的類似度に基づく高精度なナレッジ検索を実現する。

埋め込みモデル: sentence-transformers (multilingual-e5)
インデックス: FAISS IndexFlatIP (正規化済みコサイン類似度)
"""

import json
import logging
from pathlib import Path
from typing import Optional

import numpy as np

from src.chat.rag import KnowledgeChunk, SearchResult

logger = logging.getLogger(__name__)


class EmbeddingModel:
    """テキスト埋め込みモデル。sentence-transformers ラッパー。

    E5 モデルは query/passage プレフィックスを使い分けることで
    検索精度を向上させる設計になっている。
    """

    def __init__(
        self,
        model_name: str = "intfloat/multilingual-e5-base",
    ) -> None:
        from sentence_transformers import SentenceTransformer

        self.model_name = model_name
        self.model = SentenceTransformer(model_name)
        self.dimension = self.model.get_sentence_embedding_dimension()
        logger.info(
            f"埋め込みモデル読み込み完了: {model_name} (dim={self.dimension})"
        )

    def encode_query(self, query: str) -> np.ndarray:
        """クエリテキストを埋め込みベクトルに変換する。"""
        prefixed = f"query: {query}"
        vec = self.model.encode(
            [prefixed],
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return vec[0]

    def encode_passages(self, passages: list[str]) -> np.ndarray:
        """パッセージ（ナレッジチャンク）群を埋め込みベクトルに変換する。"""
        prefixed = [f"passage: {p}" for p in passages]
        return self.model.encode(
            prefixed,
            normalize_embeddings=True,
            show_progress_bar=len(prefixed) > 100,
            batch_size=64,
        )


class VectorRAG:
    """FAISS ベクトル検索 RAG エンジン。

    KnowledgeLoader で取得したチャンク群を埋め込みベクトル化し、
    FAISS の IndexFlatIP でコサイン類似度検索を行う。
    インデックスはディスクに保存/読み込み可能。
    """

    def __init__(
        self,
        chunks: list[KnowledgeChunk],
        embedding_model: Optional[EmbeddingModel] = None,
        index_path: Optional[str | Path] = None,
        similarity_threshold: float = 0.3,
    ) -> None:
        import faiss

        self.chunks = chunks
        self.similarity_threshold = similarity_threshold
        self.index_path = Path(index_path) if index_path else None

        self.embedding = embedding_model or EmbeddingModel()
        self.dimension = self.embedding.dimension

        self.index: Optional[faiss.Index] = None

        if self.index_path and self._load_index():
            logger.info("既存FAISSインデックスを読み込みました")
        else:
            self._build_index()

    def _build_index(self) -> None:
        """チャンクからFAISSインデックスを構築する。"""
        import faiss

        if not self.chunks:
            self.index = faiss.IndexFlatIP(self.dimension)
            logger.warning("チャンクが空のためインデックスは空です")
            return

        texts = [c.content for c in self.chunks]
        embeddings = self.embedding.encode_passages(texts)

        self.index = faiss.IndexFlatIP(self.dimension)
        self.index.add(embeddings.astype(np.float32))

        logger.info(f"FAISSインデックス構築完了: {self.index.ntotal}ベクトル")

        if self.index_path:
            self._save_index()

    def _save_index(self) -> None:
        """インデックスとチャンクメタデータをディスクに保存する。"""
        import faiss

        if self.index is None or self.index_path is None:
            return

        self.index_path.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self.index, str(self.index_path / "index.faiss"))

        meta = []
        for c in self.chunks:
            meta.append({
                "content": c.content,
                "source_file": c.source_file,
                "category": c.category,
                "metadata": c.metadata,
                "pattern_ids": c.pattern_ids,
            })
        with open(self.index_path / "chunks.json", "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

        logger.info(f"インデックス保存: {self.index_path}")

    def _load_index(self) -> bool:
        """ディスクからインデックスを読み込む。"""
        import faiss

        if self.index_path is None:
            return False

        index_file = self.index_path / "index.faiss"
        chunks_file = self.index_path / "chunks.json"

        if not index_file.exists() or not chunks_file.exists():
            return False

        try:
            self.index = faiss.read_index(str(index_file))
            with open(chunks_file, encoding="utf-8") as f:
                meta = json.load(f)

            self.chunks = [KnowledgeChunk(**m) for m in meta]

            if self.index.ntotal != len(self.chunks):
                logger.warning(
                    "インデックスとチャンクの数が不一致。再構築します。"
                )
                return False

            return True
        except Exception as e:
            logger.warning(f"インデックス読み込みエラー: {e}")
            return False

    def search(
        self,
        query: str,
        top_k: int = 5,
        pattern: Optional[int] = None,
    ) -> list[SearchResult]:
        """ベクトル類似度でチャンクを検索する。

        Args:
            query: 検索クエリ文字列
            top_k: 返却する最大件数
            pattern: パターン番号でフィルタ（Noneなら全検索）

        Returns:
            類似度降順にソートされた SearchResult リスト
        """
        if self.index is None or self.index.ntotal == 0:
            return []

        query_vec = self.embedding.encode_query(query)
        query_vec = np.array([query_vec], dtype=np.float32)

        # パターンフィルタ時は多めに取得してからフィルタ
        fetch_k = top_k * 3 if pattern is not None else top_k
        k = min(fetch_k, self.index.ntotal)
        scores, indices = self.index.search(query_vec, k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:
                continue
            if score < self.similarity_threshold:
                continue
            chunk = self.chunks[idx]
            if pattern is not None and pattern not in chunk.pattern_ids:
                continue
            results.append(SearchResult(
                chunk=chunk,
                score=float(score),
            ))

        return results[:top_k]

    def format_context(self, results: list[SearchResult]) -> str:
        """検索結果をLLMに渡すコンテキスト文字列に整形する。"""
        if not results:
            return "（関連するナレッジが見つかりませんでした）"

        parts: list[str] = []
        for i, result in enumerate(results, 1):
            parts.append(
                f"【参照{i}】出典: {result.chunk.source_file} "
                f"(類似度: {result.score:.2f})\n"
                f"{result.chunk.content}"
            )

        return "\n\n".join(parts)

    def get_sources(self, results: list[SearchResult]) -> list[str]:
        """検索結果から重複なしの出典リストを生成する。"""
        seen: set[str] = set()
        sources: list[str] = []
        for result in results:
            src = result.chunk.source_file
            if src not in seen:
                seen.add(src)
                sources.append(src)
        return sources

    def rebuild_index(self) -> None:
        """インデックスを再構築する（ナレッジ更新時に呼び出す）。"""
        self._build_index()


def create_rag(
    chunks: list[KnowledgeChunk],
    index_path: Optional[str | Path] = None,
    embedding_model_name: str = "intfloat/multilingual-e5-base",
    similarity_threshold: float = 0.3,
    use_vector: bool = True,
):
    """RAGエンジンのファクトリ関数。

    FAISS + sentence-transformers が利用可能ならVectorRAGを、
    そうでなければSimpleRAGにフォールバックする。

    Returns:
        VectorRAG or SimpleRAG インスタンス
    """
    if use_vector:
        try:
            import faiss  # noqa: F401

            embedding = EmbeddingModel(embedding_model_name)
            return VectorRAG(
                chunks=chunks,
                embedding_model=embedding,
                index_path=index_path,
                similarity_threshold=similarity_threshold,
            )
        except ImportError:
            logger.warning(
                "faiss-cpu または sentence-transformers が未インストール。"
                "SimpleRAG にフォールバックします。"
            )

    from src.chat.rag import SimpleRAG
    return SimpleRAG(chunks)
