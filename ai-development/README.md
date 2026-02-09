# AI開発

AI開発に関するナレッジベース。テキストと画像を構造的に管理する。

## Overview

Claude Code との会話・すり合わせを通じて得られた知見、意思決定、仕様、参考資料を蓄積し、検索・参照可能にするためのプロジェクト。

コンテンツは **テキスト** と **画像** の2種類を管理する。

## Features

- テキストエントリ: Markdown + YAML Front Matter 形式で会話内容・合意事項を保存
- 画像エントリ: 画像ファイル + メタデータ（.meta.yaml）でセットで管理
- カテゴリ・タグによる分類
- CLI でのエントリ追加・検索・一覧表示
- INDEX.md の自動生成

## Requirements

- Python 3.10+
- PyYAML

## Quick Start

```bash
# セットアップ
cd ai-development
pip install -r requirements.txt

# テキストエントリを追加
python main.py add-text \
  --title "Claude Codeとの初回すり合わせ" \
  --body "プロジェクト構成について議論し、以下の方針で合意した..." \
  --category conversation \
  --tags "初期設計,方針" \
  --source "Claude Code session"

# 画像を登録
python main.py add-image \
  --title "システム構成図 v1" \
  --path /path/to/architecture.png \
  --description "メインサービスの構成概要" \
  --category architecture \
  --tags "設計,v1"

# 一覧表示
python main.py list
python main.py list --type text
python main.py list --type images --category diagram

# 検索
python main.py search "認証"

# インデックス更新
python main.py index

# 統計
python main.py stats
```

## Usage

### テキストエントリの追加

```bash
python main.py add-text \
  --title "タイトル" \
  --body "本文をここに" \
  --category conversation \
  --tags "タグ1,タグ2" \
  --source "情報源"
```

ファイルから本文を読み込む場合:

```bash
python main.py add-text \
  --title "タイトル" \
  --file notes.md \
  --category decision
```

**テキストカテゴリ:**

| カテゴリ | 用途 |
|---------|------|
| `conversation` | 会話記録・すり合わせ内容 |
| `decision` | 意思決定・合意事項 |
| `insight` | 知見・学び |
| `specification` | 仕様・設計 |
| `reference` | 参考資料 |

### 画像エントリの追加

```bash
python main.py add-image \
  --title "タイトル" \
  --path /path/to/image.png \
  --description "画像の説明" \
  --category diagram \
  --tags "タグ1,タグ2"
```

**画像カテゴリ:**

| カテゴリ | 用途 |
|---------|------|
| `diagram` | 設計図・フロー図 |
| `screenshot` | スクリーンショット |
| `generated` | AI生成画像 |
| `reference` | 参考画像 |
| `architecture` | アーキテクチャ図 |

## Project Structure

```
ai-development/
├── main.py               # CLI エントリーポイント
├── src/
│   ├── __init__.py
│   ├── content_manager.py # コンテンツ統合管理
│   ├── text_handler.py    # テキストエントリ管理
│   └── image_handler.py   # 画像エントリ管理
├── config/
│   └── settings.yaml      # プロジェクト設定
├── content/
│   ├── text/              # テキストエントリ保存先
│   │   ├── conversation/  # 会話記録
│   │   ├── decision/      # 意思決定
│   │   ├── insight/       # 知見
│   │   ├── specification/ # 仕様
│   │   └── reference/     # 参考資料
│   ├── images/            # 画像エントリ保存先
│   │   ├── diagram/       # 設計図
│   │   ├── screenshot/    # スクリーンショット
│   │   ├── generated/     # AI生成画像
│   │   ├── reference/     # 参考画像
│   │   └── architecture/  # アーキテクチャ図
│   └── INDEX.md           # 自動生成インデックス
├── templates/             # エントリ作成テンプレート
├── tests/
├── requirements.txt
└── README.md
```

## Configuration

`config/settings.yaml` でカテゴリの追加やメタデータフィールドのカスタマイズが可能。

## Troubleshooting

**Q: `ModuleNotFoundError: No module named 'yaml'`**
A: `pip install -r requirements.txt` を実行する。

**Q: 画像の登録時に「サポートされていない画像形式」エラー**
A: `config/settings.yaml` の `allowed_extensions` に対象の拡張子を追加する。

## License

Private
