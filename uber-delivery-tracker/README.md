# Uber Eats 配達データ自動収集・レポート化システム

Uber ドライバーポータルの内部 API から配達データを直接取得し、Markdown/JSON レポートとして GitHub に蓄積するシステム。

## Overview

Playwright でセッション（Cookie）を維持しつつ、Uber の内部 API を呼び出してデータを取得。日次・週次・月次のレポートを自動生成し、GitHub Pages のダッシュボードで可視化する。

## Features

- Uber 内部 API 直接呼び出し（Playwright によるセッション維持）
- 対象日を含む週全体を取得し、日付で絞り込む正確な抽出
- 日次・週次・月次の集計レポート（Markdown + JSON）
- `daily.sh` による一発実行（取得 → レポート生成 → git push）
- GitHub Actions による自動実行（毎日 23:00 JST）
- GitHub Pages によるインタラクティブダッシュボード
- セッション切れ時の明確なエラー通知

## Requirements

- Node.js 18 以上
- npm
- Google Chrome（`/Applications/Google Chrome.app` にインストール済み）
- GitHub アカウント

## Quick Start

```bash
# 1. リポジトリをクローン
git clone https://github.com/Aaaaamon2718/.github
cd .github/uber-delivery-tracker

# 2. 依存関係をインストール
npm install
npx playwright install chromium

# 3. 初回ログイン（手動）→ Cookie を保存
node scripts/auth/save-session.js

# 4. 昨日の配達データを取得・レポート生成・push
./daily.sh

# 特定日を指定する場合
./daily.sh 2026-04-23
```

## Usage

### daily.sh（推奨）

毎日の運用はこれ一本で完結する。

```bash
./daily.sh              # 昨日のデータ
./daily.sh 2026-04-23   # 特定日のデータ
```

内部処理：
1. 対象日を含む週（月〜日）を自動計算
2. `scraper.js` で API からデータ取得
3. `parser.js` でレポート生成
4. `git push` で GitHub に格納

### 個別実行

```bash
# スクレイピングのみ
node scripts/scraper.js --date 2026-04-23

# 週範囲を明示する場合
node scripts/scraper.js --date 2026-04-23 --from 2026-04-21 --to 2026-04-27

# レポート生成のみ
node scripts/parser.js --date 2026-04-23

# 週次・月次サマリー
node scripts/report-generator.js --weekly
node scripts/report-generator.js --monthly
```

### セッション更新

Cookie は通常 2 週間〜1 ヶ月で失効する。切れたら再実行：

```bash
node scripts/auth/save-session.js
```

## Project Structure

```
uber-delivery-tracker/
├── daily.sh                    # 一発実行スクリプト（推奨）
├── run.sh                      # 手動実行用スクリプト
├── package.json
├── data/
│   ├── raw/                    # 生データ JSON（YYYY-MM-DD.json）
│   └── reports/                # 生成レポート（Markdown + JSON + index.json）
├── scripts/
│   ├── auth/
│   │   └── save-session.js     # 初回ログイン・Cookie 保存
│   ├── scraper.js              # Uber API 直接呼び出し
│   ├── parser.js               # JSON → Markdown/JSON レポート変換
│   └── report-generator.js    # 週次・月次サマリー生成
├── dashboard/
│   └── index.html              # GitHub Pages ダッシュボード
├── session/                    # セッションファイル（gitignore 済み）
└── .github/
    └── workflows/
        └── daily-scrape.yml    # GitHub Actions 設定
```

## データ構造

### data/raw/YYYY-MM-DD.json

```json
{
  "date": "2026-04-23",
  "scrapedAt": "2026-04-23T14:00:00.000Z",
  "totalCount": 12,
  "successCount": 12,
  "deliveries": [
    {
      "no": 1,
      "earnings": 840,
      "duration": "27:34",
      "durationSec": 1654,
      "distance": 3.2,
      "datetime": "2026年4月23日 午後7時16分",
      "storeName": "...",
      "destAddress": "...",
      "tip": 0,
      "uuid": "..."
    }
  ]
}
```

### data/reports/YYYY-MM-DD.md / .json

- `.md` ：全体サマリー・配達明細・時間帯別・エリア別・店舗別・効率ランキング
- `.json`：ダッシュボード・集計用の構造化データ

## Troubleshooting

**セッション切れ（`❌ セッション期限切れ`）**
→ `node scripts/auth/save-session.js` を再実行。

**配達件数が 0 件**
→ `--from` / `--to` で週範囲を明示して再実行。Uber の API レスポンス構造が変わった可能性もあるため、`data/debug/` のダンプを確認。

**`data/debug/` ディレクトリ**
→ `.gitignore` で除外済み。デバッグ用の中間ファイルが保存される。

## License

Private use only.
