# 詳細セットアップ手順

## 前提条件

- Python 3.10+
- Git
- Anthropic API キー（Claude API用）

## 1. リポジトリのクローン

```bash
git clone <repository-url>
cd makino-ai-companion
```

## 2. セットアップスクリプトの実行

```bash
chmod +x setup.sh
bash setup.sh
```

## 3. 環境変数の設定

`.env` ファイルを作成し、以下の変数を設定する:

```bash
# Claude API (Anthropic)
ANTHROPIC_API_KEY=your-anthropic-api-key

# サーバー設定（オプション）
ALLOWED_ORIGIN=https://your-client-site.com

# エスカレーション通知（オプション）
ESCALATION_EMAIL_PRIMARY=admin@example.com
```

## 4. 設定ファイルの確認

`config/settings.yaml` の主要設定:

```yaml
claude:
  model: "claude-sonnet-4-5-20250929"  # 使用モデル
  max_tokens: 4096                      # 最大トークン数

database:
  sqlite:
    path: "data/conversations.db"       # SQLiteファイルの保存先

server:
  host: "0.0.0.0"
  port: 8000
```

必要に応じて `config/settings.yaml` を環境に合わせて編集する。

## 5. ナレッジベースの準備

ナレッジデータは `knowledge/` ディレクトリにMarkdown形式で格納する:

```bash
# ディレクトリ構成の確認
ls knowledge/

# サンプルデータの確認
cat knowledge/qa/sample.md

# バリデーション
python cli.py knowledge validate

# 統計情報の確認
python cli.py knowledge stats
```

各Markdownファイルの先頭にYAMLフロントマターでメタデータを記述:

```markdown
---
category: 法人保険
sub_category: 決算書分析
source: 牧野生保塾 Vol.5 (2024/05)
priority: high
tags: [断定, 論理的解説]
---

# タイトル

本文...
```

## 6. サーバー起動

```bash
# 仮想環境の有効化
source venv/bin/activate

# サーバー起動
python app.py
# → http://localhost:8000 でチャットUIにアクセス

# 開発モード（自動リロード）
python cli.py server start --reload
```

## 7. テストの実行

```bash
source venv/bin/activate
pytest tests/ -v
```

## ディレクトリ構成の確認

セットアップ後、以下のディレクトリが存在することを確認:

```
makino-ai-companion/
├── venv/           # 仮想環境（gitignore対象）
├── data/           # SQLiteデータベース格納（gitignore対象）
├── output/         # 出力ファイル（gitignore対象）
├── reports/        # レポート出力（gitignore対象）
├── cache/          # キャッシュ（gitignore対象）
├── logs/exports/   # ログエクスポート（GitHub監査用）
└── .env            # 環境変数（gitignore対象）
```

## トラブルシューティング

### pip install でエラーが発生する場合

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### Claude API 接続エラー

- `ANTHROPIC_API_KEY` 環境変数が正しく設定されているか確認
- APIキーの有効性を [Anthropic Console](https://console.anthropic.com/) で確認

### サーバーが起動しない

- `python -m pip install -r requirements.txt` を再実行
- ポート8000が他のプロセスで使用されていないか確認

### ナレッジ検索精度が低い

- `knowledge/` 内のMarkdownファイルを拡充
- YAMLフロントマターのカテゴリ・タグが正しいか確認
- `python cli.py knowledge validate` でバリデーション

### 人格再現度が低い

- `src/prompts/persona_config.py` のプロンプトを調整
- `src/prompts/system_prompts.py` のPattern別プロンプトを確認
