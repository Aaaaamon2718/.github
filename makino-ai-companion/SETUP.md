# 詳細セットアップ手順

## 前提条件

- Python 3.10+
- Git
- Google Cloud Platform アカウント（Sheets API用）
- Dify Platform アカウント

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
# Dify Platform
DIFY_BASE_URL=https://api.dify.ai/v1
DIFY_API_KEY=your-dify-api-key

# Google Sheets
GOOGLE_SPREADSHEET_ID=your-spreadsheet-id
GOOGLE_CREDENTIALS_PATH=./credentials.json

# Webhook
WEBHOOK_ENDPOINT=https://script.google.com/macros/s/your-gas-endpoint/exec

# Escalation
ESCALATION_EMAIL_PRIMARY=admin@example.com
```

## 4. Google Sheets API の設定

1. [Google Cloud Console](https://console.cloud.google.com/) でプロジェクトを作成
2. Google Sheets API を有効化
3. サービスアカウントを作成し、認証情報（JSON）をダウンロード
4. ダウンロードしたJSONを `credentials.json` としてプロジェクトルートに配置
5. 対象のスプレッドシートにサービスアカウントのメールアドレスを共有設定で追加

## 5. Dify Platform の設定

1. [Dify](https://dify.ai/) にログイン
2. 新しいアプリケーションを作成（Pattern数分）
3. 各アプリケーションのAPIキーを取得
4. `config/settings.yaml` にアプリケーションIDを記入

## 6. ナレッジベースの準備

```bash
# テンプレートを確認
cat templates/knowledge_base_template.csv

# データを準備（templates/ のテンプレートを参考に作成）
# data/knowledge_base.csv にデータファイルを配置

# バリデーション実行
python scripts/setup_knowledge_base.py --input data/knowledge_base.csv --validate-only

# セットアップ実行
python scripts/setup_knowledge_base.py --input data/knowledge_base.csv
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
├── data/           # 実データ格納（gitignore対象）
├── output/         # 出力ファイル（gitignore対象）
├── reports/        # レポート出力（gitignore対象）
├── cache/          # キャッシュ（gitignore対象）
├── credentials.json # Google認証情報（gitignore対象）
└── .env            # 環境変数（gitignore対象）
```

## トラブルシューティング

### pip install でエラーが発生する場合

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### Google Sheets API 認証エラー

- `credentials.json` のパスが正しいか確認
- サービスアカウントにスプレッドシートの編集権限があるか確認

### Dify API 接続エラー

- APIキーが正しいか確認
- Difyのサーバーステータスを確認
