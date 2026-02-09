# ナレッジベース

このディレクトリにAI伴走システムの学習データを格納する。
全データはGitHubで管理され、変更履歴の追跡・ロールバックが可能。

## ディレクトリ構成

```
knowledge/
├── seminars/       # 牧野生保塾 過去講義の文字起こし
├── trainings/      # 各種研修データ（ドクター研修、法人研修等）
├── qa/             # 過去の質問・回答ペア
├── articles/       # メルマガ・ニュースレター・書籍
└── sales_tools/    # 営業トーク集・プレゼン資料
```

## ファイル形式

全てMarkdown（`.md`）形式で作成する。

### フロントマター（メタデータ）

各ファイルの先頭にYAML形式のメタデータを記述する:

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

## データ追加の手順

1. 該当するサブディレクトリにMarkdownファイルを作成
2. フロントマターにメタデータを記述
3. `python cli.py knowledge validate` でバリデーション
4. `python cli.py knowledge stats` で統計確認
5. git commit & push
