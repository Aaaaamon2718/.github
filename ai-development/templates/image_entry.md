# 画像エントリー テンプレート

画像を登録する際のガイドライン。

## メタデータ（.meta.yaml）の構成

```yaml
title: "画像タイトル"
category: "diagram"  # diagram / screenshot / generated / reference / architecture
created_at: "YYYY-MM-DD HH:MM:SS"
image_file: "実際のファイル名.png"
original_path: "元ファイルのパス"
description: |
  この画像が何を表しているか、
  どのような文脈で作成されたかを記述する。
tags:
  - "タグ1"
  - "タグ2"
source: "情報源（Claude Codeセッション、URL等）"
status: "draft"  # draft / confirmed / archived
```

## カテゴリ別の用途

| カテゴリ | 用途 | 例 |
|---------|------|-----|
| diagram | 設計図・フロー図 | システム構成図、処理フロー |
| screenshot | スクリーンショット | UI画面、エラー画面 |
| generated | AI生成画像 | DALL-E / Midjourney 出力 |
| reference | 参考画像 | 外部資料の図表 |
| architecture | アーキテクチャ図 | インフラ構成、データフロー |

## CLI での登録方法

```bash
python main.py add-image \
  --title "システム構成図" \
  --path /path/to/image.png \
  --description "メインサービスのアーキテクチャ概要" \
  --category architecture \
  --tags "設計,v1.0" \
  --source "Claude Code セッション"
```
