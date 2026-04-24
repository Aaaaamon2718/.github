#!/bin/bash
# run.sh
# 使い方: ./run.sh         → 今日のデータ
#         ./run.sh 2026-04-21 → 指定日のデータ

DATE=${1:-today}
DIR="$(cd "$(dirname "$0")" && pwd)"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚗 Uber配達レポート自動生成"
echo "   対象日: $DATE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Step 1: スクレイピング
echo "\n[1/3] データ収集中..."
node "$DIR/scripts/scraper.js" --date "$DATE"
if [ $? -ne 0 ]; then
  echo "❌ スクレイピング失敗。処理を中断します。"
  exit 1
fi

# Step 2: レポート生成
echo "\n[2/3] レポート生成中..."
node "$DIR/scripts/parser.js" --date "$DATE"
if [ $? -ne 0 ]; then
  echo "❌ レポート生成失敗。"
  exit 1
fi

# Step 3: GitHub push
echo "\n[3/3] GitHubにpush中..."
cd "$DIR"
git add data/
ACTUAL_DATE=$([ "$DATE" = "today" ] && date '+%Y-%m-%d' || echo "$DATE")
git commit -m "data: add delivery report $ACTUAL_DATE"
git push

echo "\n✅ 完了！GitHubにレポートが格納されました。"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
