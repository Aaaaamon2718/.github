# PDF Upload System

Claude CodeにPDF読み取り機能を追加するMCPサーバー。

## Overview

Claude Code CLIは標準ではPDFファイルの直接添付をサポートしていない。
本システムはMCP (Model Context Protocol) サーバーとして動作し、
Claude Codeに以下のPDF操作ツールを追加する:

- **read_pdf**: PDFの全テキストまたは指定ページを読み取る
- **get_pdf_info**: メタデータ（ページ数、タイトル、著者等）を取得
- **search_pdf**: PDF内のテキスト検索
- **convert_pdf_to_markdown**: PDF全体をMarkdown形式に変換
- **list_pdfs**: ディレクトリ内のPDFファイル一覧

## Requirements

- Python 3.10+
- Claude Code CLI

## Quick Start

```bash
# 1. 依存関係をインストール
cd pdf-upload-system
pip install -r requirements.txt

# 2. Claude CodeにMCPサーバーを登録
claude mcp add pdf-reader python3 /path/to/pdf-upload-system/main.py

# 3. Claude Codeを起動して使う
claude
```

## Usage

MCPサーバー登録後、Claude Codeの会話内で自然にPDFを参照できる:

```
> このPDFの内容を教えて: /path/to/document.pdf
> PDFの3ページ目だけ読んで
> PDF内で「売上」を検索して
> PDFをMarkdownに変換して
```

Claude Codeが自動的に適切なツール（`read_pdf`, `search_pdf`等）を選択して実行する。

## Project Structure

```
pdf-upload-system/
├── main.py               # MCPサーバーエントリーポイント
├── src/
│   ├── __init__.py
│   └── pdf_processor.py  # PDF処理コアロジック
├── config/
│   └── settings.yaml     # 設定ファイル
├── requirements.txt      # Python依存関係
├── setup.sh              # 自動セットアップスクリプト
├── .gitignore
└── README.md
```

## Configuration

### MCP登録方法

**プロジェクトスコープ**（推奨 - このリポジトリでのみ有効）:

```bash
claude mcp add --scope project pdf-reader python3 /absolute/path/to/main.py
```

**ユーザースコープ**（全プロジェクトで有効）:

```bash
claude mcp add --scope user pdf-reader python3 /absolute/path/to/main.py
```

### 登録確認

```bash
claude mcp list
```

### 登録解除

```bash
claude mcp remove pdf-reader
```

## Troubleshooting

| 問題 | 解決策 |
|------|--------|
| `ModuleNotFoundError: fitz` | `pip install PyMuPDF` を実行 |
| `ModuleNotFoundError: mcp` | `pip install mcp` を実行 |
| ツールが表示されない | `claude mcp list` で登録状況を確認 |
| PDFが読めない | ファイルパスが絶対パスか確認。相対パスも可だがCWD依存 |
| スキャンPDFのテキストが空 | 画像ベースPDFはOCRが必要（現バージョン未対応） |

## License

MIT
