#!/usr/bin/env python3
"""PDF Upload System - MCP Server for Claude Code

Claude CodeにPDF読み取り機能を追加するMCPサーバー。
以下のツールをClaude Codeに提供する:

- read_pdf: PDFの全テキストまたは指定ページを読み取る
- get_pdf_info: PDFのメタデータ（ページ数、タイトル等）を取得
- search_pdf: PDF内のテキスト検索
- convert_pdf_to_markdown: PDFをMarkdown形式に変換
- list_pdfs: 指定ディレクトリ内のPDFファイル一覧

使い方:
    claude mcp add pdf-reader python3 /path/to/pdf-upload-system/main.py
"""

from __future__ import annotations

import os
import glob
import json
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

# src/ を import path に追加
sys.path.insert(0, str(Path(__file__).parent))
from src.pdf_processor import PdfProcessor

mcp = FastMCP(
    "pdf-reader",
    version="1.0.0",
)


@mcp.tool()
def read_pdf(
    file_path: str,
    start_page: int = 1,
    end_page: int | None = None,
) -> str:
    """PDFファイルのテキスト内容を読み取る。

    全ページまたは指定範囲のページのテキストを抽出して返す。
    大きなPDFの場合はstart_page/end_pageで範囲を指定すること。

    Args:
        file_path: PDFファイルへの絶対パスまたは相対パス
        start_page: 開始ページ番号（1始まり、デフォルト: 1）
        end_page: 終了ページ番号（省略時: 最終ページ）
    """
    try:
        with PdfProcessor(file_path) as pdf:
            if start_page == 1 and end_page is None and pdf.page_count <= 50:
                return pdf.extract_all_text()

            pages = pdf.extract_pages(start_page, end_page)
            parts: list[str] = []
            for p in pages:
                parts.append(f"--- Page {p.page_number} ---")
                parts.append(p.text)
                if p.image_count > 0:
                    parts.append(f"[{p.image_count} image(s) on this page]")
            return "\n".join(parts)
    except FileNotFoundError:
        return f"Error: File not found: {file_path}"
    except ValueError as e:
        return f"Error: {e}"


@mcp.tool()
def get_pdf_info(file_path: str) -> str:
    """PDFファイルのメタデータを取得する。

    ページ数、タイトル、著者、ファイルサイズなどの情報を返す。
    PDFを読む前に、まずこのツールで概要を確認すると効率的。

    Args:
        file_path: PDFファイルへの絶対パスまたは相対パス
    """
    try:
        with PdfProcessor(file_path) as pdf:
            info = pdf.get_info()
            result = {
                "path": info.path,
                "page_count": info.page_count,
                "file_size": f"{info.file_size_bytes / 1024:.1f} KB",
            }
            if info.title:
                result["title"] = info.title
            if info.author:
                result["author"] = info.author
            if info.subject:
                result["subject"] = info.subject
            if info.keywords:
                result["keywords"] = info.keywords
            return json.dumps(result, ensure_ascii=False, indent=2)
    except FileNotFoundError:
        return f"Error: File not found: {file_path}"
    except ValueError as e:
        return f"Error: {e}"


@mcp.tool()
def search_pdf(
    file_path: str,
    query: str,
    max_results: int = 20,
) -> str:
    """PDF内でテキスト検索を行う。

    指定した文字列を含むページとその周辺テキストを返す。
    大量ページのPDFで特定の情報を探す場合に有効。

    Args:
        file_path: PDFファイルへの絶対パスまたは相対パス
        query: 検索する文字列
        max_results: 最大結果数（デフォルト: 20）
    """
    try:
        with PdfProcessor(file_path) as pdf:
            results = pdf.search(query, max_results)
            if not results:
                return f"No matches found for '{query}'"

            parts: list[str] = []
            total_matches = sum(r.match_count for r in results)
            parts.append(
                f"Found {total_matches} match(es) across {len(results)} page(s):"
            )
            parts.append("")

            for r in results:
                parts.append(
                    f"[Page {r.page_number}] ({r.match_count} match(es))"
                )
                parts.append(f"  {r.text_snippet}")
                parts.append("")

            return "\n".join(parts)
    except FileNotFoundError:
        return f"Error: File not found: {file_path}"
    except ValueError as e:
        return f"Error: {e}"


@mcp.tool()
def convert_pdf_to_markdown(file_path: str) -> str:
    """PDFの全内容をMarkdown形式に変換する。

    タイトル、著者などのメタデータをヘッダーに、
    各ページの内容をセクションとして構造化したMarkdownを返す。

    Args:
        file_path: PDFファイルへの絶対パスまたは相対パス
    """
    try:
        with PdfProcessor(file_path) as pdf:
            return pdf.to_markdown()
    except FileNotFoundError:
        return f"Error: File not found: {file_path}"
    except ValueError as e:
        return f"Error: {e}"


@mcp.tool()
def list_pdfs(directory: str = ".") -> str:
    """指定ディレクトリ内のPDFファイルを一覧表示する。

    ディレクトリを再帰的に探索し、見つかったPDFファイルの
    パス、サイズ、ページ数を一覧で返す。

    Args:
        directory: 検索するディレクトリパス（デフォルト: カレントディレクトリ）
    """
    directory = os.path.abspath(directory)
    if not os.path.isdir(directory):
        return f"Error: Directory not found: {directory}"

    pdf_files = glob.glob(os.path.join(directory, "**", "*.pdf"), recursive=True)
    pdf_files.sort()

    if not pdf_files:
        return f"No PDF files found in {directory}"

    parts: list[str] = [f"Found {len(pdf_files)} PDF file(s) in {directory}:"]
    parts.append("")

    for pdf_path in pdf_files:
        size = os.path.getsize(pdf_path)
        size_str = f"{size / 1024:.1f} KB" if size < 1024 * 1024 else f"{size / (1024 * 1024):.1f} MB"
        try:
            with PdfProcessor(pdf_path) as pdf:
                pages = pdf.page_count
            parts.append(f"  {pdf_path}  ({size_str}, {pages} pages)")
        except (ValueError, Exception):
            parts.append(f"  {pdf_path}  ({size_str}, unable to read)")

    return "\n".join(parts)


if __name__ == "__main__":
    mcp.run(transport="stdio")
