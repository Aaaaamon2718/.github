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

# クエリ範囲: 対象日 〜 対象日+2日（ピンポイント取得）
# 理由: 週全体をクエリするとページ数が増えbotブロックのリスクが上がる
#       +2日のバッファでタイムゾーン境界・翌日recognized処理を吸収
QUERY_FROM=$TARGET
QUERY_TO=$(date -j -v+2d -f "%Y-%m-%d" "$TARGET" "+%Y-%m-%d" 2>/dev/null || date -d "$TARGET +2 days" "+%Y-%m-%d")

echo "   クエリ範囲: $QUERY_FROM 〜 $QUERY_TO"
echo ""

# Step 1: スクレイピング
echo "[1/3] データ取得中..."
node scripts/scraper.js --date "$TARGET" --from "$QUERY_FROM" --to "$QUERY_TO"
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
# リモートに新しいコミットがある場合に備えてrebase後にpush
git pull --rebase origin main
git push
if [ $? -ne 0 ]; then
  echo "❌ push失敗"
  exit 1
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ 完了！$TARGET のレポートをGitHubに格納しました"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
