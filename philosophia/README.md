# Philosophia

Amonの哲学的思考を体系化し、一冊の哲学書へと統合するためのナレッジリポジトリ。

## Overview

日々の読書・対話・思索から生まれる哲学的素材を一箇所に集約し、テーマ別に整理・統合していくことで、最終的に体系的な哲学書を編纂するための「知的倉庫＋ワークスペース」。

## Features

- **インプット管理**: 書籍のスクリーンショット・OCRテキスト・読書メモを書籍ごとに構造化
- **アウトプット蓄積**: 断片メモ・対話記録・エッセイを日付・テーマで管理
- **テーマ索引**: 素材をテーマ横断で参照できる索引システム
- **統合編纂**: 素材を章立てに統合し、哲学書として段階的に構築
- **Claude Code駆動**: 構造化・整理・統合作業をClaude Codeで実行

## Requirements

- Git / GitHub
- Claude Code
- Python 3.x（OCRスクリプト用）
- Tesseract OCR（スクリーンショットからのテキスト抽出）

## Quick Start

```bash
# リポジトリをクローン
git clone <repository-url>
cd philosophia

# 断片メモを作成
bash scripts/new_fragment.sh "love-as-verb"

# テーマ索引を更新
python scripts/build_index.py
```

## Usage

### 素材の投入

1. **書籍スクリーンショット**: `input/books/{book}/screenshots/` に画像を配置
2. **OCR処理**: `python scripts/ocr_extract.py input/books/{book}/screenshots/`
3. **断片メモ**: `bash scripts/new_fragment.sh "slug"` でテンプレートから作成
4. **対話記録**: `templates/dialogue.md` をコピーして `output/dialogues/` に配置

### 統合作業

1. `themes/*/index.md` でテーマ別の素材を確認
2. 十分な素材が溜まったテーマについて `output/essays/` にエッセイを執筆
3. エッセイを素材に `synthesis/chapters/` の章ドラフトを更新
4. `synthesis/outline.md` で全体構成を見直し

## Project Structure

```
philosophia/
├── input/              # インプット層（読書・参考資料）
│   ├── books/          #   書籍ごと（metadata + screenshots + ocr + notes）
│   └── references/     #   その他の参考資料
├── output/             # アウトプット層（自分の思想）
│   ├── fragments/      #   断片メモ（日次の気づき）
│   ├── dialogues/      #   対話記録（Claude対話）
│   └── essays/         #   テーマ別エッセイ
├── synthesis/          # 統合層（哲学書の編纂）
│   ├── outline.md      #   目次・全体構成
│   ├── chapters/       #   各章
│   └── appendix/       #   補遺
├── themes/             # テーマ索引
├── templates/          # ファイルテンプレート
└── scripts/            # 自動化スクリプト
```

## Configuration

### テーマの追加

1. `themes/` に新しいディレクトリを作成
2. `index.md` を作成し、関連する素材へのリンクを記載
3. 既存素材のフロントマターにテーマタグを追加

### 書籍の追加

1. `input/books/{author}-{title-slug}/` ディレクトリを作成
2. `templates/book-metadata.yaml` をコピーして `metadata.yaml` を編集
3. `notes.md` を作成して読書メモを記録

## 素材ステータス

| ステータス | 意味 |
|-----------|------|
| `raw` | 投入直後。未整理 |
| `refined` | テーマ分類・引用整理済み |
| `integrated` | 哲学書に取り込み済み |

## Troubleshooting

### OCRが正しく動作しない
- Tesseract OCRがインストールされているか確認: `tesseract --version`
- 日本語の場合は `tesseract-ocr-jpn` パッケージが必要

### テンプレートが見つからない
- `templates/` ディレクトリ内のファイルを確認
- 利用可能なテンプレート: `fragment.md`, `dialogue.md`, `essay.md`, `book-metadata.yaml`, `chapter.md`

## License

Private repository. All rights reserved.
