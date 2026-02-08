#!/bin/bash
# PDF Upload System - セットアップスクリプト
#
# 使い方:
#   chmod +x setup.sh
#   ./setup.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== PDF Upload System セットアップ ==="
echo ""

# Python バージョン確認
if ! command -v python3 &> /dev/null; then
    echo "Error: python3 が見つかりません。Python 3.10+ をインストールしてください。"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "Python version: $PYTHON_VERSION"

# 依存関係インストール
echo ""
echo "1. 依存関係をインストール中..."
pip install -r "$SCRIPT_DIR/requirements.txt"

# Claude Code MCP 登録
echo ""
echo "2. Claude Code に MCP サーバーを登録中..."
MAIN_PY="$SCRIPT_DIR/main.py"

if command -v claude &> /dev/null; then
    claude mcp add pdf-reader python3 "$MAIN_PY"
    echo "   登録完了: pdf-reader -> $MAIN_PY"
else
    echo "   Warning: claude コマンドが見つかりません。"
    echo "   手動で以下を実行してください:"
    echo ""
    echo "   claude mcp add pdf-reader python3 $MAIN_PY"
fi

echo ""
echo "=== セットアップ完了 ==="
echo ""
echo "使い方:"
echo "  1. claude を起動"
echo "  2. 会話内でPDFファイルのパスを指定して読み取りを依頼"
echo ""
echo "例:"
echo '  > /path/to/document.pdf の内容を要約して'
echo '  > PDFの5ページ目を読んで'
echo '  > PDF内で「キーワード」を検索して'
