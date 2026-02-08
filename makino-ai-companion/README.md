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

## Requirements

- Python 3.10+
- Dify Platform（AI伴走システム基盤）
- Google Workspace（Sheets, Apps Script）
- 文字起こしAPI（Whisper等）

## Quick Start

```bash
# 1. リポジトリのクローン
git clone <repository-url>
cd makino-ai-companion

# 2. セットアップ
bash setup.sh

# 3. 設定ファイルの編集
cp config/settings.yaml.example config/settings.yaml
# settings.yaml を環境に合わせて編集

# 4. 依存関係のインストール
pip install -r requirements.txt
```

詳細は [SETUP.md](SETUP.md) を参照。

## Project Structure

```
makino-ai-companion/
├── README.md                    # 本ファイル
├── SETUP.md                     # 詳細セットアップ手順
├── requirements.txt             # Python依存関係
├── setup.sh                     # セットアップスクリプト
├── .gitignore                   # Git除外設定
│
├── config/                      # 設定ファイル
│   └── settings.yaml            # プロジェクト全体の設定
│
├── docs/                        # プロジェクトドキュメント
│   ├── project-overview.md      # プロジェクト全体像
│   ├── phases/                  # フェーズ別詳細ドキュメント
│   │   ├── phase1-requirements.md
│   │   ├── phase2-data-collection.md
│   │   ├── phase3-poc.md
│   │   ├── phase4-mvp.md
│   │   ├── phase5-pattern-expansion.md
│   │   └── phase6-production.md
│   ├── agents/                  # エージェントパターン定義
│   │   ├── pattern1-general-qa.md
│   │   ├── pattern2-doctor-market.md
│   │   ├── pattern3-corporate-insurance.md
│   │   └── pattern4-personality-mentoring.md
│   ├── data/                    # データ設計ドキュメント
│   │   ├── labeling-schema.md
│   │   ├── log-schema.md
│   │   └── data-flow.md
│   ├── kpi/                     # KPI・評価指標
│   │   └── evaluation-metrics.md
│   └── operations/              # 運用・保守ドキュメント
│       ├── monitoring.md
│       ├── escalation-flow.md
│       └── maintenance.md
│
├── src/                         # ソースコード（内部ロジック）
│   ├── __init__.py
│   ├── knowledge_base/          # ナレッジベース処理
│   │   ├── __init__.py
│   │   └── processor.py
│   ├── prompts/                 # プロンプト管理
│   │   ├── __init__.py
│   │   ├── system_prompts.py
│   │   └── persona_config.py
│   ├── logging/                 # ログ蓄積処理
│   │   ├── __init__.py
│   │   └── log_handler.py
│   └── webhook/                 # Webhook連携
│       ├── __init__.py
│       └── dify_webhook.py
│
├── templates/                   # テンプレートファイル
│   ├── knowledge_base_template.csv
│   ├── log_sheet_template.csv
│   ├── persona_definition_template.md
│   └── phrase_dictionary_template.csv
│
├── scripts/                     # ユーティリティスクリプト
│   ├── setup_knowledge_base.py
│   └── export_logs.py
│
└── tests/                       # テストコード
    └── test_knowledge_base.py
```

## Architecture

```
┌─────────────┐    質問    ┌──────────────────┐    RAG検索    ┌─────────────┐
│  受講生      │──────────→│  Dify Platform   │────────────→│ ナレッジ     │
│ (ユーザー)   │←──────────│  (LLM + Prompt)  │←────────────│  ベース      │
└─────────────┘    回答    └──────────────────┘    結果返却    └─────────────┘
                                   │
                              Webhook送信
                                   │
                                   ▼
                           ┌──────────────┐    書込    ┌──────────────┐
                           │ Google Apps   │──────────→│ スプレッド    │
                           │   Script     │           │  シート       │
                           └──────────────┘           └──────────────┘
                                                            │
                                                       定期レビュー
                                                            │
                                                            ▼
                                                    ┌──────────────┐
                                                    │ 改善サイクル   │
                                                    │ (月次)        │
                                                    └──────────────┘
```

## Schedule (12 Months)

| Phase | 期間 | 内容 |
|-------|------|------|
| Phase 1 | Month 1-2 | ヒアリング・要件定義 |
| Phase 2 | Month 3-4 | データ収集・整理・ラベリング |
| Phase 3 | Month 5-6 | PoC開発・技術検証 |
| Phase 4 | Month 7-8 | MVP開発 (Pattern 1) |
| Phase 5 | Month 9-10 | パターン展開 (Pattern 2-4) |
| Phase 6 | Month 11-12 | 本番運用・保守体制構築 |

## Configuration

`config/settings.yaml` にプロジェクトの全設定を集約。
詳細は [config/settings.yaml](config/settings.yaml) のコメントを参照。

## Agent Patterns

| Pattern | 名称 | 対象 |
|---------|------|------|
| Pattern 1 | 質問対応エージェント | 牧野生保塾 月額会員 |
| Pattern 2 | ドクターマーケット特化 | 開業医攻略研修 受講生 |
| Pattern 3 | 法人保険特化 | 法人財務スペシャリスト研修 受講生 |
| Pattern 4 | 人格エージェント | 全受講生・営業担当者 |

各パターンの詳細は `docs/agents/` 配下のドキュメントを参照。

## Troubleshooting

- Dify接続エラー: `config/settings.yaml` のAPI設定を確認
- ナレッジベース検索精度が低い: `docs/data/labeling-schema.md` のラベリングルールを再確認
- 人格再現度が低い: `src/prompts/persona_config.py` のプロンプトを調整

## CONFIDENTIAL

本プロジェクトの全資料は機密情報として取り扱うこと。
