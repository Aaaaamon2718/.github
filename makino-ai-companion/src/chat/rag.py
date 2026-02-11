"""RAG（Retrieval-Augmented Generation）エンジン。

GitHubリポジトリ内のナレッジベース（Markdownファイル）を読み込み、
パターン別フィルタリング付きで関連情報を検索する。

ナレッジディレクトリ構造:
    knowledge/
    ├── general/      パターン1: 生保全般 Q&A
    ├── doctor/       パターン2: ドクターマーケット特化
    ├── corporate/    パターン3: 法人保険特化
    ├── mentoring/    パターン4: 励まし・メンタリング
    └── shared/       全パターン共通
"""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ディレクトリ名 → パターンID のマッピング
PATTERN_DIR_MAP: dict[str, list[int]] = {
    "general": [1],
    "doctor": [2],
    "corporate": [3],
    "mentoring": [4],
    "shared": [1, 2, 3, 4],
}

# ディレクトリ名 → カテゴリ表示名
DIR_TO_CATEGORY: dict[str, str] = {
    "general": "生保全般",
    "doctor": "ドクターマーケット",
    "corporate": "法人保険",
    "mentoring": "メンタリング",
    "shared": "共通",
}


@dataclass
class KnowledgeChunk:
    """ナレッジの1チャンクを表すデータクラス。"""

    content: str
    source_file: str
    category: str
    metadata: dict
    pattern_ids: list[int] = field(default_factory=list)


@dataclass
class SearchResult:
    """検索結果を表すデータクラス。"""

    chunk: KnowledgeChunk
    score: float


class KnowledgeLoader:
    """GitHubリポジトリ内のナレッジファイルを読み込み、チャンク分割する。"""

    def __init__(
        self,
        knowledge_dir: str | Path,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
    ) -> None:
        self.knowledge_dir = Path(knowledge_dir)
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def load_all(self) -> list[KnowledgeChunk]:
        """ナレッジディレクトリ内の全Markdownファイルを読み込む。"""
        chunks: list[KnowledgeChunk] = []

        if not self.knowledge_dir.exists():
            logger.warning(f"ナレッジディレクトリが存在しません: {self.knowledge_dir}")
            return chunks

        for md_file in self.knowledge_dir.rglob("*.md"):
            file_chunks = self._load_file(md_file)
            chunks.extend(file_chunks)

        logger.info(f"ナレッジ読み込み完了: {len(chunks)}チャンク")
        return chunks

    def _load_file(self, file_path: Path) -> list[KnowledgeChunk]:
        """1つのMarkdownファイルを読み込み、チャンク分割する。"""
        try:
            content = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            logger.warning(f"ファイル読み込みエラー: {file_path}: {e}")
            return []

        metadata = self._extract_metadata(content)
        category = self._infer_category(file_path)
        pattern_ids = self._infer_pattern_ids(file_path)

        sections = self._split_by_sections(content)
        chunks: list[KnowledgeChunk] = []

        for section in sections:
            text_chunks = self._chunk_text(section)
            for text in text_chunks:
                if text.strip():
                    chunks.append(KnowledgeChunk(
                        content=text.strip(),
                        source_file=str(file_path.relative_to(self.knowledge_dir)),
                        category=category,
                        metadata=metadata,
                        pattern_ids=pattern_ids,
                    ))

        return chunks

    def _split_by_sections(self, content: str) -> list[str]:
        """Markdown見出しでセクション分割する。"""
        sections = re.split(r'\n(?=#{1,3}\s)', content)
        return [s for s in sections if s.strip()]

    def _chunk_text(self, text: str) -> list[str]:
        """テキストを指定サイズでチャンク分割する。"""
        if len(text) <= self.chunk_size:
            return [text]

        chunks: list[str] = []
        start = 0
        while start < len(text):
            end = start + self.chunk_size
            if end < len(text):
                last_period = text.rfind("。", start, end)
                if last_period > start:
                    end = last_period + 1
            chunks.append(text[start:end])
            start = end - self.chunk_overlap
        return chunks

    def _extract_metadata(self, content: str) -> dict:
        """Markdownのフロントマター（YAML）からメタデータを抽出する。"""
        metadata: dict = {}
        match = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
        if match:
            for line in match.group(1).split('\n'):
                if ':' in line:
                    key, _, value = line.partition(':')
                    metadata[key.strip()] = value.strip()
        return metadata

    def _infer_category(self, file_path: Path) -> str:
        """ファイルパスからカテゴリを推定する。"""
        parts = file_path.relative_to(self.knowledge_dir).parts
        if parts:
            return DIR_TO_CATEGORY.get(parts[0], parts[0])
        return "未分類"

    def _infer_pattern_ids(self, file_path: Path) -> list[int]:
        """ファイルパスから対応するパターンIDリストを推定する。

        未知のディレクトリ配下のファイルは全パターンから参照可能とする。
        """
        parts = file_path.relative_to(self.knowledge_dir).parts
        if parts:
            return PATTERN_DIR_MAP.get(parts[0], [1, 2, 3, 4])
        return [1, 2, 3, 4]


class SimpleRAG:
    """シンプルなキーワードベースRAG。"""

    def __init__(self, chunks: list[KnowledgeChunk]) -> None:
        self.chunks = chunks

    def search(
        self,
        query: str,
        top_k: int = 5,
        pattern: Optional[int] = None,
    ) -> list[SearchResult]:
        """クエリに関連するチャンクを検索する。

        Args:
            query: 検索クエリ文字列
            top_k: 返却する最大件数
            pattern: パターン番号でフィルタ（Noneなら全検索）
        """
        if pattern is not None:
            search_chunks = [
                c for c in self.chunks if pattern in c.pattern_ids
            ]
        else:
            search_chunks = self.chunks

        scored: list[tuple[float, KnowledgeChunk]] = []
        query_terms = set(query.lower().split())

        for chunk in search_chunks:
            content_lower = chunk.content.lower()
            score = sum(1 for term in query_terms if term in content_lower)
            if score > 0:
                scored.append((score / len(query_terms), chunk))

        scored.sort(key=lambda x: x[0], reverse=True)

        return [
            SearchResult(chunk=chunk, score=score)
            for score, chunk in scored[:top_k]
        ]

    def format_context(self, results: list[SearchResult]) -> str:
        """検索結果をLLMに渡すコンテキスト文字列に整形する。"""
        if not results:
            return "（関連するナレッジが見つかりませんでした）"

        parts: list[str] = []
        for i, result in enumerate(results, 1):
            parts.append(
                f"【参照{i}】出典: {result.chunk.source_file}\n"
                f"{result.chunk.content}"
            )

        return "\n\n".join(parts)

    def get_sources(self, results: list[SearchResult]) -> list[str]:
        """検索結果から出典リストを生成する。"""
        seen: set[str] = set()
        sources: list[str] = []
        for result in results:
            src = result.chunk.source_file
            if src not in seen:
                seen.add(src)
                sources.append(src)
        return sources
