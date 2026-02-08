# CLAUDE.md — Philosophia プロジェクト指示書

このファイルはClaude Codeがこのリポジトリで作業する際の前提知識と作業指示を定義する。

---

## プロジェクトの目的

Philosophiaは、Amonの哲学的思考を体系化し、一冊の哲学書へと統合するためのナレッジリポジトリである。インプット（読書・参考資料）とアウトプット（断片メモ・対話記録・エッセイ）を蓄積し、最終的に統合層（synthesis）で哲学書として編纂する。

---

## リポジトリ構造

```
philosophia/
├── input/          # インプット層（他者の思想）
│   ├── books/      #   書籍ごとのディレクトリ（metadata.yaml + screenshots/ + ocr/ + notes.md）
│   └── references/ #   書籍以外の参考資料
├── output/         # アウトプット層（自分の思想）
│   ├── fragments/  #   断片メモ（日付ベース、高頻度）
│   ├── dialogues/  #   Claude対話からの思考記録（中頻度）
│   └── essays/     #   テーマ別エッセイ（低頻度、熟成後）
├── synthesis/      # 統合層（哲学書）
│   ├── outline.md  #   全体構成・目次
│   ├── chapters/   #   各章
│   └── appendix/   #   補遺・参考文献一覧
├── themes/         # テーマ索引（素材への参照リンク集）
├── templates/      # テンプレート（新規ファイル作成時に使用）
└── scripts/        # 自動化スクリプト
```

---

## 各ディレクトリの役割

### input/books/{book-slug}/
- `metadata.yaml` — 書誌情報（テンプレート: `templates/book-metadata.yaml`）
- `screenshots/` — 原本スクリーンショット（命名: `p{page}_{seq}.{ext}`）
- `ocr/` — OCR抽出テキスト（スクショからの派生物）
- `notes.md` — 読書メモ・要約・気づき

### output/fragments/
- 日々の哲学的な気づき・着想・問い
- テンプレート: `templates/fragment.md`
- 命名: `YYYY-MM-DD_slug.md`

### output/dialogues/
- Claudeとの哲学的対話から生まれた思考の記録
- テンプレート: `templates/dialogue.md`
- 命名: `YYYY-MM-DD_topic.md`

### output/essays/
- テーマごとにまとめた考察文
- テンプレート: `templates/essay.md`
- 命名: `on-{topic}.md` または自由命名

### synthesis/
- インプット・アウトプットを素材にした哲学書の編纂
- `outline.md` で全体構成を管理
- `chapters/` に各章を `{nn}-{title-slug}.md` 形式で配置

### themes/
- テーマ別の素材索引（`index.md` にリンク集）
- `_emerging/` は未分類・萌芽的テーマの一時格納先

---

## ファイル命名規則

| 対象 | 形式 | 例 |
|------|------|-----|
| 断片メモ | `YYYY-MM-DD_slug.md` | `2025-02-08_love-as-verb.md` |
| 対話記録 | `YYYY-MM-DD_topic.md` | `2025-02-08_fromm-and-stoicism.md` |
| エッセイ | `on-{topic}.md` | `on-loving-actively.md` |
| 書籍ディレクトリ | `{author}-{title-slug}/` | `fromm-art-of-loving/` |
| 章 | `{nn}-{title-slug}.md` | `01-what-is-love.md` |
| スクリーンショット | `p{page}_{seq}.{ext}` | `p042_01.png` |

---

## 素材のステータス管理

すべての素材ファイルのフロントマターに `status` フィールドを持つ：

```
raw       → 投入直後。未整理
refined   → テーマ分類・引用整理済み
integrated → 統合層（哲学書）に取り込み済み
```

---

## コミットメッセージ規約

接頭辞を使用する：

| 接頭辞 | 用途 | 例 |
|--------|------|-----|
| `input:` | インプット素材の追加 | `input: フロム「愛するということ」第3章スクショ追加` |
| `output:` | アウトプットの追加 | `output: 断片メモ「愛は動詞である」追加` |
| `synthesis:` | 統合作業 | `synthesis: 第1章ドラフト更新` |
| `meta:` | 構造・設定の変更 | `meta: テーマ索引更新` |

---

## Claude Codeの作業指示

### 素材投入時
1. スクリーンショットが追加されたら、OCR処理してテキストを `ocr/` に保存
2. 新規書籍の場合、`metadata.yaml` と `notes.md` を生成
3. 断片メモ・対話記録はテンプレートに基づいて作成

### 定期的な整理作業
1. テーマ索引（`themes/*/index.md`）の更新
2. `_emerging/` の素材を確認し、十分な密度があればテーマとして独立
3. `synthesis/outline.md` の構成見直し

### 統合作業
1. テーマに紐づく素材を集約し、章のドラフトを生成
2. 素材間の関連性・矛盾点を指摘
3. 統合済み素材の `status` を `integrated` に更新

---

## テーマ構造（現在）

| テーマ | ディレクトリ | 概要 |
|--------|------------|------|
| 愛の哲学 | `themes/love/` | フロム「愛するということ」を起点とした探求 |
| ストア哲学 | `themes/stoicism/` | マルクス・アウレリウス「自省録」中心 |
| フロム思想 | `themes/fromm/` | 「愛するということ」「自由からの逃走」等 |
| 創造性 | `themes/creativity/` | 音楽制作・DJとの接点 |
| 萌芽 | `themes/_emerging/` | 未分類テーマの一時格納先 |
