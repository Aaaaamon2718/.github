# desktop-organizer

デスクトップに散乱したスクリーンショットを日付別フォルダに自動整理するツール。

## Overview

macOSのデスクトップに溜まった「スクリーンショット 2026-01-17...」のようなファイルを、
`Screenshots/2026-01/` のような日付別フォルダに自動分類する。

## Features

- スクリーンショットファイルを日付（年-月）別に自動分類
- 日本語・英語のスクリーンショット名に対応
- ドライランモードで事前に移動計画を確認可能
- YAML設定ファイルによるカスタマイズ

## Requirements

- Python 3.10+
- PyYAML

## Quick Start

```bash
cd desktop-organizer

# 依存関係インストール
pip install -r requirements.txt

# まずドライランで確認
python main.py --dry-run

# 実行
python main.py
```

## Usage

```bash
# ドライランモード（移動計画のみ表示）
python main.py --dry-run

# デスクトップパスを直接指定
python main.py --desktop ~/Desktop

# 設定ファイルを指定
python main.py --config path/to/settings.yaml
```

## Project Structure

```
desktop-organizer/
├── main.py                # エントリーポイント
├── src/
│   ├── __init__.py
│   ├── organizer.py       # 整理ロジック（スキャン・移動）
│   └── config_loader.py   # 設定ファイル読み込み
├── config/
│   └── settings.yaml      # 整理ルール設定
├── requirements.txt
├── .gitignore
└── README.md
```

## Configuration

`config/settings.yaml` で以下を設定可能:

| 設定項目 | 説明 | デフォルト |
|---------|------|-----------|
| `desktop_path` | デスクトップのパス | `~/Desktop` |
| `organized_folder` | 整理先フォルダ名 | `Screenshots` |
| `group_by_date` | 日付別フォルダ作成 | `true` |
| `date_folder_format` | 日付フォルダ形式 | `%Y-%m` |
| `dry_run` | ドライランモード | `false` |

## 整理後のフォルダ構成

```
~/Desktop/
├── Screenshots/
│   ├── 2026-01/
│   │   ├── スクリーンショット 2026-01-17 22.42.10.png
│   │   ├── スクリーンショット 2026-01-18 14.30.00.png
│   │   └── ...
│   ├── 2026-02/
│   │   └── ...
│   └── other/           # 日付が取得できなかったファイル
├── video-to-chunks/     # 既存フォルダはそのまま
├── makino-ai-roadmap/   # 既存フォルダはそのまま
└── I Love EDM .../      # 既存フォルダはそのまま
```
