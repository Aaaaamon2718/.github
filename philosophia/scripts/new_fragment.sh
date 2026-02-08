#!/bin/bash
# 断片メモの新規作成スクリプト
#
# Usage:
#   bash scripts/new_fragment.sh "slug"
#   bash scripts/new_fragment.sh "love-as-verb"
#
# 結果:
#   output/fragments/YYYY-MM-DD_slug.md が作成される

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
FRAGMENTS_DIR="$PROJECT_DIR/output/fragments"
TEMPLATE="$PROJECT_DIR/templates/fragment.md"

if [ $# -lt 1 ]; then
    echo "Usage: $0 <slug>"
    echo "Example: $0 love-as-verb"
    exit 1
fi

SLUG="$1"
DATE="$(date +%Y-%m-%d)"
FILENAME="${DATE}_${SLUG}.md"
FILEPATH="$FRAGMENTS_DIR/$FILENAME"

if [ -f "$FILEPATH" ]; then
    echo "Error: ファイルが既に存在します: $FILEPATH"
    exit 1
fi

# テンプレートをコピーして日付を設定
sed "s/date: YYYY-MM-DD/date: $DATE/" "$TEMPLATE" > "$FILEPATH"

echo "作成しました: $FILEPATH"
