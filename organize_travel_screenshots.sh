#!/bin/bash
# =============================================================================
# organize_travel_screenshots.sh
# デスクトップのトラベルスクリーンショットを Gemini 一括アップロード用に整理する
# 対象: "スクリーンショット" かつ "2026-4-24" or "2026-04-24" を含むファイル
# =============================================================================

set -euo pipefail

# --- 設定 ---
DESKTOP="$HOME/Desktop"
TARGET_DATE_1="2026-4-24"
TARGET_DATE_2="2026-04-24"
KEYWORD="スクリーンショット"
TRAVEL_KEYWORD="トラベル"
OUTPUT_DIR="$DESKTOP/2026-04-24_トラベル_画像まとめ"
MANIFEST="$OUTPUT_DIR/画像リスト.txt"

# --- カラー出力 ---
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo "========================================"
echo " トラベルスクリーンショット 整理ツール"
echo "========================================"
echo ""

# デスクトップの存在確認
if [ ! -d "$DESKTOP" ]; then
    echo -e "${RED}エラー: デスクトップが見つかりません: $DESKTOP${NC}"
    exit 1
fi

# --- 対象ファイルを収集 ---
echo "対象ファイルを検索中..."
echo "  検索ディレクトリ: $DESKTOP"
echo "  フィルター条件  : \"$KEYWORD\" + (\"$TARGET_DATE_1\" or \"$TARGET_DATE_2\") + \"$TRAVEL_KEYWORD\""
echo ""

# 配列に収集（bash 3.x互換 - macOS Monterey以前対応）
mapfile -t CANDIDATES < <(find "$DESKTOP" -maxdepth 1 -type f \( -iname "*.png" -o -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.heic" -o -iname "*.webp" \) 2>/dev/null) || true

# fallback for macOS bash 3.x (no mapfile)
if ! declare -p CANDIDATES &>/dev/null 2>&1; then
    CANDIDATES=()
    while IFS= read -r line; do
        CANDIDATES+=("$line")
    done < <(find "$DESKTOP" -maxdepth 1 -type f \( -iname "*.png" -o -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.heic" -o -iname "*.webp" \))
fi

MATCHED=()
for f in "${CANDIDATES[@]}"; do
    filename=$(basename "$f")
    # スクリーンショット + 日付 + トラベル の3条件マッチ
    if [[ "$filename" == *"$KEYWORD"* ]] && \
       ([[ "$filename" == *"$TARGET_DATE_1"* ]] || [[ "$filename" == *"$TARGET_DATE_2"* ]]) && \
       [[ "$filename" == *"$TRAVEL_KEYWORD"* ]]; then
        MATCHED+=("$f")
    fi
done

# トラベルキーワードなしでも日付+スクリーンショットで拾う（フォールバック）
if [ ${#MATCHED[@]} -eq 0 ]; then
    echo -e "${YELLOW}「トラベル」を含むファイルが見つかりませんでした。${NC}"
    echo "「スクリーンショット + 日付」のみで再検索します..."
    echo ""
    for f in "${CANDIDATES[@]}"; do
        filename=$(basename "$f")
        if [[ "$filename" == *"$KEYWORD"* ]] && \
           ([[ "$filename" == *"$TARGET_DATE_1"* ]] || [[ "$filename" == *"$TARGET_DATE_2"* ]]); then
            MATCHED+=("$f")
        fi
    done
fi

# ファイルなし
if [ ${#MATCHED[@]} -eq 0 ]; then
    echo -e "${RED}対象ファイルが見つかりませんでした。${NC}"
    echo ""
    echo "ヒント:"
    echo "  - ファイル名に「$KEYWORD」「$TARGET_DATE_1」「$TRAVEL_KEYWORD」が含まれているか確認してください"
    echo "  - スクリプト内の TARGET_DATE_1 / TRAVEL_KEYWORD を実際のファイル名に合わせてください"
    echo ""
    echo "デスクトップ上の画像ファイル一覧:"
    find "$DESKTOP" -maxdepth 1 -type f \( -iname "*.png" -o -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.heic" \) -exec basename {} \; | sort
    exit 1
fi

echo -e "${GREEN}${#MATCHED[@]} 件のファイルが見つかりました${NC}"
echo ""

# --- 出力フォルダ作成 ---
mkdir -p "$OUTPUT_DIR"

# --- ファイルをコピー & リネーム ---
echo "ファイルを整理中..."
echo ""

COUNTER=1
> "$MANIFEST"  # マニフェスト初期化

{
    echo "# Gemini 一括アップロード用 画像リスト"
    echo "# 生成日時: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "# 元ディレクトリ: $DESKTOP"
    echo "# 総ファイル数: ${#MATCHED[@]}"
    echo "# ==========================================="
    echo ""
} >> "$MANIFEST"

for src in "${MATCHED[@]}"; do
    original=$(basename "$src")
    ext="${original##*.}"
    ext_lower=$(echo "$ext" | tr '[:upper:]' '[:lower:]')

    # ゼロパディングで連番 (001, 002, ...)
    padded=$(printf "%03d" "$COUNTER")
    new_name="画像_${padded}.${ext_lower}"
    dest="$OUTPUT_DIR/$new_name"

    cp "$src" "$dest"

    echo -e "  ${GREEN}✓${NC} $new_name  ←  $original"
    echo "$new_name  |  元ファイル: $original" >> "$MANIFEST"

    COUNTER=$((COUNTER + 1))
done

echo ""
echo "========================================"
echo -e "${GREEN}完了！${NC}"
echo "  出力フォルダ : $OUTPUT_DIR"
echo "  ファイル数   : $((COUNTER - 1)) 件"
echo "  マニフェスト : $MANIFEST"
echo "========================================"
echo ""
echo "Gemini へのアップロード手順:"
echo "  1. Google AI Studio (aistudio.google.com) を開く"
echo "  2. 「$OUTPUT_DIR」フォルダを Finder で開く"
echo "  3. 画像_001.* 〜 画像_$(printf "%03d" $((COUNTER - 1))).* を全選択してドラッグ&ドロップ"
echo "  4. プロンプト例: 「これらの旅行画像を分析して、場所・特徴・おすすめポイントをまとめてください」"
echo ""
