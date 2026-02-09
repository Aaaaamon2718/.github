# 牧野生保塾 AI伴走システム

生命保険営業の生産性向上と知見継承を実現する AI 伴走システム

## Overview

本プロジェクトは、牧野生保塾が蓄積してきた生命保険営業の知見・哲学・ノウハウを、
AIエージェントとして体系化し、受講生に24時間365日のサポートを提供するシステムを構築する。

牧野克彦氏の人格・思考プロセス・価値観をAIに再現し、
単なるFAQボットではなく「牧野氏と対話しているような体験」を実現する。

## Features

- **Pattern 1**: 牧野生保塾 質問対応エージェント（汎用Q&A、24時間即時回答）
- **Pattern 2**: ドクターマーケット特化エージェント（医療法人・開業医向け）
- **Pattern 3**: 法人保険特化エージェント（決算書分析・財務改善提案）
- **Pattern 4**: 人格エージェント（励まし・メンタリング・精神的サポート）

## Tech Stack

| レイヤー | 技術 |
|---------|------|
| LLM | **Claude API** (Anthropic SDK) |
| バックエンド | **FastAPI** (Python) |
| フロントエンド | チャットUI (HTML/CSS/JS) → チャットウィジェット化対応 |
| データベース | **SQLite** (会話ログ蓄積) |
| ナレッジ管理 | **GitHub** (Markdown, バージョン管理) |
| RAG | キーワード検索 → FAISS (ベクトル検索) |
| 開発ツール | **Claude Code** + GitHub連携 + CLI |

## Quick Start

```bash
# 1. リポジトリのクローン
git clone <repository-url>
cd makino-ai-companion

# 2. セットアップ
bash setup.sh

# 3. 環境変数の設定
export ANTHROPIC_API_KEY="your-api-key"

# 4. サーバー起動
python app.py
# → http://localhost:8000 でチャットUIにアクセス
```

詳細は [SETUP.md](SETUP.md) を参照。

## Project Structure

```
makino-ai-companion/
├── app.py                       # FastAPIエントリーポイント
├── cli.py                       # 開発者向けCLIツール
├── README.md / SETUP.md         # ドキュメント
├── requirements.txt             # Python依存関係
├── setup.sh                     # セットアップスクリプト
│
├── config/
│   └── settings.yaml            # 全設定（Claude API, DB, サーバー等）
│
├── knowledge/                   # ナレッジベース（GitHub管理）
│   ├── seminars/                #   過去講義の文字起こし
│   ├── trainings/               #   研修データ
│   ├── qa/                      #   Q&Aペア
│   ├── articles/                #   メルマガ・書籍
│   └── sales_tools/             #   営業ツール
│
├── src/                         # ソースコード
│   ├── api/                     #   FastAPIルーティング
│   │   └── routes.py
│   ├── chat/                    #   チャットエンジン
│   │   ├── engine.py            #     Claude API連携
│   │   └── rag.py               #     RAG検索エンジン
│   ├── database/                #   SQLiteデータベース
│   │   ├── models.py            #     スキーマ定義
│   │   └── operations.py        #     CRUD操作
│   ├── prompts/                 #   プロンプト管理
│   │   ├── system_prompts.py    #     Pattern 1-4のシステムプロンプト
│   │   └── persona_config.py    #     人格設定
│   ├── knowledge_base/          #   ナレッジ処理ユーティリティ
│   └── logging/                 #   ログ処理ユーティリティ
│
├── static/                      # フロントエンド静的ファイル
│   ├── css/style.css
│   └── js/chat.js
│
├── templates/                   # HTMLテンプレート & データテンプレート
│   ├── index.html               #   メインチャットUI
│   ├── widget.html              #   埋め込みウィジェット版
│   └── *.csv, *.md              #   データテンプレート
│
├── docs/                        # プロジェクトドキュメント
├── scripts/                     # ユーティリティスクリプト
├── tests/                       # テストコード
└── logs/exports/                # ログエクスポート（GitHub監査用）
```

## Architecture

```
┌─────────────┐    質問     ┌──────────────────────────────────────┐
│  受講生      │───────────→│           FastAPI Server              │
│ (ブラウザ)   │←───────────│                                      │
└─────────────┘    回答     │  ┌────────────┐   ┌───────────────┐  │
                            │  │ Claude API │   │ RAG Engine    │  │
                            │  │ (Anthropic)│←──│ (知識検索)     │  │
                            │  └────────────┘   └───────┬───────┘  │
                            └───────────┬───────────────┘──────────┘
                                        │               │
                                        ▼               ▼
                                ┌──────────────┐ ┌──────────────┐
                                │   SQLite     │ │   GitHub     │
                                │ (会話ログ)    │ │ (ナレッジ)    │
                                └──────┬───────┘ └──────────────┘
                                       │
                                  定期エクスポート
                                       │
                                       ▼
                               ┌──────────────┐
                               │ logs/exports │
                               │ (GitHub監査) │
                               └──────────────┘

開発者側:
┌──────────┐    CLI     ┌──────────────┐    git     ┌──────────┐
│Claude Code│──────────→│   cli.py     │──────────→│  GitHub  │
│  (開発)   │           │ (管理ツール)  │           │  (履歴)  │
└──────────┘            └──────────────┘           └──────────┘
```

## CLI Usage（開発者向け）

```bash
# ナレッジベース管理
python cli.py knowledge stats          # 統計情報
python cli.py knowledge validate       # バリデーション

# ログ管理
python cli.py logs metrics             # KPI指標表示
python cli.py logs export              # CSV出力（GitHub監査用）

# プロンプトテスト
python cli.py prompt test --pattern 1 --question "決算書の見方を教えて"
python cli.py prompt test --pattern 4  # 対話モード

# サーバー起動
python cli.py server start --reload    # 開発モード
```

## Schedule (12 Months)

| Phase | 期間 | 内容 |
|-------|------|------|
| Phase 1 | Month 1-2 | ヒアリング・要件定義 |
| Phase 2 | Month 3-4 | データ収集・整理（GitHub上にナレッジ構築） |
| Phase 3 | Month 5-6 | PoC開発・技術検証 |
| Phase 4 | Month 7-8 | MVP開発 (Pattern 1) |
| Phase 5 | Month 9-10 | パターン展開 (Pattern 2-4) |
| Phase 6 | Month 11-12 | 本番運用・保守体制構築 |

## Troubleshooting

- Claude API接続エラー: `ANTHROPIC_API_KEY` 環境変数を確認
- ナレッジ検索精度が低い: `knowledge/` 内のMarkdownファイルを拡充
- 人格再現度が低い: `src/prompts/persona_config.py` のプロンプトを調整
- サーバーが起動しない: `python -m pip install -r requirements.txt` を再実行

## CONFIDENTIAL

本プロジェクトの全資料は機密情報として取り扱うこと。
