# Uber Eats 配達データ自動収集・レポート化システム

Uberドライバーポータルから配達データを自動取得し、Markdown/JSONレポートとしてGitHubに蓄積するシステム。

## Overview

Playwrightによるブラウザ自動操作でデータを収集し、日次・週次・月次のレポートを自動生成。GitHub Pagesにダッシュボードを公開する。

## Features
- Playwright によるブラウザ自動操作（Cookie永続化方式）
- 日次・週次・月次の集計レポート（Markdown）
- GitHub Actions による自動実行（毎日23:00 JST）
- GitHub Pages によるインタラクティブダッシュボード
- セッション切れ時の明確なエラー通知

## Requirements
- Node.js 18以上
- npm
- GitHub アカウント（Actionsを使用する場合）

## Quick Start

```bash
# 1. リポジトリをクローン
git clone https://github.com/YOUR_USERNAME/uber-delivery-tracker
cd uber-delivery-tracker

# 2. 依存関係をインストール
npm install
npx playwright install chromium

# 3. 初回ログイン（手動） → Cookieを保存
node scripts/auth/save-session.js

# 4. 今日の配達データを取得・レポート生成
npm run daily
```

## Usage

### 日次実行

```bash
# 今日のデータ
node scripts/scraper.js --date today
node scripts/parser.js --date today
node scripts/report-generator.js --date today

# 特定日のデータ
node scripts/scraper.js --date 2026-04-24
node scripts/parser.js --date 2026-04-24
```

### 週次・月次レポート

```bash
# 週次サマリー（当日を含む週）
node scripts/report-generator.js --date today --type weekly

# 月次サマリー（当月）
node scripts/report-generator.js --date today --type monthly
```

### git push（データ保存）

```bash
git add data/
git commit -m "chore: add delivery data $(date +%Y-%m-%d)"
git push
```

### cron自動化

```cron
# 毎日23:00に実行
0 23 * * * cd /path/to/uber-delivery-tracker && npm run daily && git add data/ && git commit -m "auto: $(date +%Y-%m-%d)" && git push
```

## Project Structure

```
uber-delivery-tracker/
├── data/
│   ├── raw/                # 生データJSON（YYYY-MM-DD.json）
│   └── reports/            # 生成レポート（Markdown + index.json）
├── scripts/
│   ├── auth/
│   │   └── save-session.js # 初回ログイン・Cookie保存
│   ├── scraper.js          # メインスクレイパー
│   ├── parser.js           # JSONをMarkdownに変換
│   └── report-generator.js # 週次・月次サマリー生成
├── dashboard/
│   └── index.html          # GitHub Pagesダッシュボード
├── session/                # セッションファイル置き場（gitignore済み）
└── .github/
    └── workflows/
        └── daily-scrape.yml # GitHub Actions設定
```

## Configuration

### GitHub Secrets（Actions使用時）

| Secret名 | 内容 |
|---|---|
| `UBER_SESSION` | `session.json` の内容をbase64エンコードしたもの |

```bash
# Secretの値を生成するコマンド
base64 -w 0 session/session.json
```

### セッション更新

Cookieは通常2週間〜1ヶ月で失効する。期限切れ時は以下を再実行：

```bash
node scripts/auth/save-session.js
# GitHub Actionsを使う場合はSecretも更新する
```

## Troubleshooting

**`ERROR: SESSION_EXPIRED` が出る**
→ `node scripts/auth/save-session.js` を再実行してセッションを更新。

**配達データが0件になる**
→ Uberがページ構造を変更した可能性がある。`scripts/scraper.js` のCSSセレクターを確認・調整すること。

**ブラウザが起動しない（Linux）**
→ `npx playwright install chromium --with-deps` を再実行。

## License

Private use only.
