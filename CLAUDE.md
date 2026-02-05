# CLAUDE.md - プロジェクト設計ガイドライン

このファイルはClaude Codeが自動的に読み込み、プロジェクト作成時の前提条件として使用します。

---

## 1. プロジェクト構造の標準テンプレート

```
project-name/
├── main.py               # エントリーポイント（ユーザーが最初に実行）
├── [機能名].py           # 単機能モジュール（直接実行可能）
│
├── src/                  # 内部ロジック（直接実行しない）
│   ├── __init__.py
│   └── [モジュール].py
│
├── config/               # 設定ファイル（コードと分離）
│   └── settings.yaml
│
├── tests/                # テストコード
│   └── test_[モジュール].py
│
├── docs/                 # 追加ドキュメント（必要時のみ）
│
├── setup.sh              # セットアップスクリプト
├── requirements.txt      # Python依存関係
├── .gitignore            # Git除外設定
├── README.md             # プロジェクト説明・使い方
└── SETUP.md              # 詳細セットアップ手順
```

---

## 2. 設計原則

### 2.1 関心の分離
- **ルートディレクトリ**: ユーザーが直接実行するファイル
- **src/**: 内部ロジック（インポートして使用）
- **config/**: 設定ファイル（コードから分離）

### 2.2 単一責任の原則
- 1ファイル = 1機能
- ファイル名 = そのファイルの責務を表す
- 例: `separator.py`は分離のみ、`analyzer.py`は分析のみ

### 2.3 設定の外部化
- ハードコードを避け、`config/settings.yaml`に集約
- 環境変数は`${ENV_VAR}`形式で参照

### 2.4 ドキュメント同梱
- README.md: 概要、クイックスタート、使い方
- SETUP.md: 詳細なセットアップ手順
- コード内コメント: Why（なぜ）を書く、What（何）は書かない

---

## 3. ファイル命名規則

| 種類 | 命名規則 | 例 |
|------|----------|-----|
| Pythonモジュール | snake_case | `audio_analyzer.py` |
| クラス | PascalCase | `AudioAnalyzer` |
| 関数・変数 | snake_case | `extract_features()` |
| 定数 | UPPER_SNAKE | `MAX_RETRY_COUNT` |
| 設定ファイル | snake_case | `settings.yaml` |

---

## 4. README.mdの標準構成

```markdown
# プロジェクト名

[1行説明]

## Overview
[プロジェクトの目的と概要]

## Features
- 機能1
- 機能2

## Requirements
- 必要な環境

## Quick Start
[最小手順でのセットアップ]

## Usage
[基本的な使い方]

## Project Structure
[ファイル構造の説明]

## Configuration
[設定方法]

## Troubleshooting
[よくある問題と解決策]

## License
[ライセンス]
```

---

## 5. Git運用ルール

### 5.1 ブランチ戦略
- `main`: 安定版（常に動作する状態）
- `feature/[機能名]`: 機能開発
- `fix/[修正内容]`: バグ修正

### 5.2 コミットメッセージ
```
[タイプ]: [概要]

[詳細説明（任意）]

[関連URL]
```

タイプ:
- `Add`: 新機能追加
- `Fix`: バグ修正
- `Update`: 既存機能の更新
- `Remove`: 機能・ファイル削除
- `Refactor`: リファクタリング
- `Docs`: ドキュメント更新

### 5.3 .gitignore標準内容
```
# Python
__pycache__/
*.py[cod]
venv/
.env

# IDE
.vscode/
.idea/

# OS
.DS_Store
Thumbs.db

# Project specific
*.log
output/
cache/
```

---

## 6. 新規プロジェクト作成チェックリスト

1. [ ] プロジェクトディレクトリ作成
2. [ ] 基本ファイル構造作成（src/, config/）
3. [ ] README.md作成
4. [ ] requirements.txt作成
5. [ ] .gitignore作成
6. [ ] setup.sh作成（必要な場合）
7. [ ] config/settings.yaml作成
8. [ ] main.py（エントリーポイント）作成
9. [ ] 機能モジュール作成
10. [ ] Gitリポジトリ初期化 & 初回コミット

---

## 7. コード品質基準

### 7.1 必須
- 全ての公開関数にdocstring
- 型ヒント使用（Python 3.10+）
- エラーハンドリング（try/except）

### 7.2 推奨
- 関数は50行以内
- ネストは3階層以内
- マジックナンバー禁止（定数化）

---

## 8. プロジェクトタイプ別テンプレート

### 8.1 CLIツール
```
tool-name/
├── main.py           # CLIエントリーポイント（argparse/click）
├── core.py           # コアロジック
├── src/
├── config/
└── ...
```

### 8.2 Webアプリ（Streamlit）
```
app-name/
├── app.py            # Streamlitエントリーポイント
├── pages/            # マルチページ
├── components/       # UIコンポーネント
├── src/              # ビジネスロジック
├── config/
└── ...
```

### 8.3 APIサーバー（FastAPI）
```
api-name/
├── main.py           # FastAPIエントリーポイント
├── routers/          # エンドポイント定義
├── models/           # Pydanticモデル
├── services/         # ビジネスロジック
├── config/
└── ...
```

---

## 9. 依存関係管理

### requirements.txt形式
```
# Core
package-name==1.2.3

# Optional
optional-package==1.0.0  # 説明

# Development
pytest>=7.0.0
```

バージョン指定:
- `==`: 本番環境（厳密固定）
- `>=`: 開発環境（最低バージョン）

---

## 10. このガイドラインの適用

Claude Codeに新規プロジェクト作成を依頼する際:

```
新規プロジェクトを作成してください。
CLAUDE.mdのガイドラインに従って構造化してください。
```

既存プロジェクトの整理を依頼する際:

```
このプロジェクトをCLAUDE.mdのガイドラインに従って
リファクタリングしてください。
```
