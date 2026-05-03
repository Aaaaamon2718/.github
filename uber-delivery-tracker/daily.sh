#!/bin/bash
# daily.sh - 毎日の配達データ取得・レポート生成・GitHub格納
# 昨日の日付を自動計算（JST）
YESTERDAY=$(date -v-1d '+%Y-%m-%d' 2>/dev/null || date -d 'yesterday' '+%Y-%m-%d')
# 引数で日付を上書き可能
TARGET=${1:-$YESTERDAY}
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚗 Uber配達レポート自動生成"
echo "   対象日: $TARGET"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 対象日の週の月曜〜日曜を計算（macOS対応）
DAY_OF_WEEK=$(date -j -f "%Y-%m-%d" "$TARGET" "+%u" 2>/dev/null || date -d "$TARGET" "+%u")
DAYS_TO_MONDAY=$((DAY_OF_WEEK - 1))
DAYS_TO_SUNDAY=$((7 - DAY_OF_WEEK))

WEEK_FROM=$(date -j -v-${DAYS_TO_MONDAY}d -f "%Y-%m-%d" "$TARGET" "+%Y-%m-%d" 2>/dev/null || date -d "$TARGET -${DAYS_TO_MONDAY} days" "+%Y-%m-%d")

# WEEK_TO は日曜 +1日（月曜）まで延長する
# 理由: Uberは週末の配達を翌月曜朝にrecognized処理するため、
#       日曜当日をend_dateにすると日曜分がAPIレスポンスに含まれないケースがある
WEEK_TO_DAYS=$((DAYS_TO_SUNDAY + 1))
WEEK_TO=$(date -j -v+${WEEK_TO_DAYS}d -f "%Y-%m-%d" "$TARGET" "+%Y-%m-%d" 2>/dev/null || date -d "$TARGET +${WEEK_TO_DAYS} days" "+%Y-%m-%d")

echo "   週範囲: $WEEK_FROM 〜 $WEEK_TO (翌日バッファ込み)"
echo ""

# Step 1: スクレイピング
echo "[1/3] データ取得中..."
node scripts/scraper.js --date "$TARGET" --from "$WEEK_FROM" --to "$WEEK_TO"
if [ $? -ne 0 ]; then
  echo "❌ データ取得失敗"
  exit 1
fi

# Step 2: レポート生成
echo ""
echo "[2/3] レポート生成中..."
node scripts/parser.js --date "$TARGET"
if [ $? -ne 0 ]; then
  echo "❌ レポート生成失敗"
  exit 1
fi

# Step 3: GitHub push
echo ""
echo "[3/3] GitHubにpush中..."
git add data/
git commit -m "data: add report $TARGET"
git push
if [ $? -ne 0 ]; then
  echo "❌ push失敗"
  exit 1
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ 完了！$TARGET のレポートをGitHubに格納しました"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
