"""PDF処理コアモジュール

PDFファイルからテキスト抽出、ページ情報取得、検索機能を提供する。
PyMuPDF (fitz) をバックエンドとして使用。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import fitz  # PyMuPDF


@dataclass
class PageContent:
    """1ページ分の抽出結果"""
    page_number: int
    text: str
    image_count: int = 0


@dataclass
class PdfInfo:
    """PDFメタデータ"""
    path: str
    page_count: int
    title: str = ""
    author: str = ""
    subject: str = ""
    file_size_bytes: int = 0
    keywords: str = ""


@dataclass
class SearchResult:
    """PDF内テキスト検索結果"""
    page_number: int
    text_snippet: str
    match_count: int = 0


class PdfProcessor:
    """PDF処理のメインクラス"""

    def __init__(self, file_path: str) -> None:
        """PDFファイルを開く。

        Args:
            file_path: PDFファイルへのパス

        Raises:
            FileNotFoundError: ファイルが存在しない場合
            ValueError: PDFとして読み込めない場合
        """
        self.file_path = os.path.abspath(file_path)

        if not os.path.exists(self.file_path):
            raise FileNotFoundError(f"PDF not found: {self.file_path}")

        try:
            self._doc = fitz.open(self.file_path)
        except Exception as e:
            raise ValueError(f"Cannot open as PDF: {self.file_path} ({e})")

    def close(self) -> None:
        """ドキュメントを閉じる"""
        if self._doc:
            self._doc.close()

    def __enter__(self) -> "PdfProcessor":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    @property
    def page_count(self) -> int:
        return self._doc.page_count

    def get_info(self) -> PdfInfo:
        """PDFメタデータを取得する"""
        metadata = self._doc.metadata or {}
        file_size = os.path.getsize(self.file_path)

        return PdfInfo(
            path=self.file_path,
            page_count=self._doc.page_count,
            title=metadata.get("title", "") or "",
            author=metadata.get("author", "") or "",
            subject=metadata.get("subject", "") or "",
            keywords=metadata.get("keywords", "") or "",
            file_size_bytes=file_size,
        )

    def extract_page(self, page_number: int) -> PageContent:
        """指定ページのテキストを抽出する。

        Args:
            page_number: 1始まりのページ番号

        Raises:
            IndexError: ページ番号が範囲外の場合
        """
        if page_number < 1 or page_number > self._doc.page_count:
            raise IndexError(
                f"Page {page_number} out of range (1-{self._doc.page_count})"
            )

        page = self._doc[page_number - 1]
        text = page.get_text("text")
        images = page.get_images(full=True)

        return PageContent(
            page_number=page_number,
            text=text,
            image_count=len(images),
        )

    def extract_pages(
        self,
        start: int = 1,
        end: Optional[int] = None,
    ) -> list[PageContent]:
        """指定範囲のページテキストを抽出する。

        Args:
            start: 開始ページ番号（1始まり、含む）
            end: 終了ページ番号（含む）。Noneなら最終ページまで
        """
        if end is None:
            end = self._doc.page_count

        start = max(1, start)
        end = min(end, self._doc.page_count)

        return [self.extract_page(i) for i in range(start, end + 1)]

    def extract_all_text(self) -> str:
        """全ページのテキストを結合して返す"""
        pages = self.extract_pages()
        parts: list[str] = []
        for p in pages:
            parts.append(f"--- Page {p.page_number} ---")
            parts.append(p.text)
        return "\n".join(parts)

    def search(self, query: str, max_results: int = 20) -> list[SearchResult]:
        """PDF内でテキスト検索を行う。

        Args:
            query: 検索文字列
            max_results: 最大結果数
        """
        results: list[SearchResult] = []
        query_lower = query.lower()

        for page_idx in range(self._doc.page_count):
            page = self._doc[page_idx]
            text = page.get_text("text")

            if query_lower not in text.lower():
                continue

            # マッチ箇所周辺のスニペットを生成
            text_lower = text.lower()
            match_count = text_lower.count(query_lower)
            pos = text_lower.find(query_lower)

            snippet_start = max(0, pos - 80)
            snippet_end = min(len(text), pos + len(query) + 80)
            snippet = text[snippet_start:snippet_end].strip()

            if snippet_start > 0:
                snippet = "..." + snippet
            if snippet_end < len(text):
                snippet = snippet + "..."

            results.append(SearchResult(
                page_number=page_idx + 1,
                text_snippet=snippet,
                match_count=match_count,
            ))

            if len(results) >= max_results:
                break

        return results

    def to_markdown(self) -> str:
        """PDF全体をMarkdown形式に変換する"""
        info = self.get_info()
        parts: list[str] = []

        # ヘッダー
        title = info.title or Path(self.file_path).stem
        parts.append(f"# {title}")
        parts.append("")

        if info.author:
            parts.append(f"**Author**: {info.author}")
        if info.subject:
            parts.append(f"**Subject**: {info.subject}")
        parts.append(f"**Pages**: {info.page_count}")
        parts.append("")
        parts.append("---")
        parts.append("")

        # ページ内容
        for page_idx in range(self._doc.page_count):
            page = self._doc[page_idx]
            text = page.get_text("text")

            parts.append(f"## Page {page_idx + 1}")
            parts.append("")
            parts.append(text.strip())
            parts.append("")

        return "\n".join(parts)
