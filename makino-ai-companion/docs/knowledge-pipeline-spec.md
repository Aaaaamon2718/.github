# ナレッジパイプライン要件定義書

## 1. 概要

牧野生保塾 AI伴走システムのナレッジベースに、テキスト・動画・画像を含む大量データを
高精度で投入するための自動パイプラインシステム。

**目標**: 生の教材ファイルを `intake/` に置くだけで、自動的にラベリング・構造化・検証を経て
`knowledge/` に格納される。

## 2. 対応入力フォーマット

| 種別 | 拡張子 | 処理方法 |
|------|--------|---------|
| テキスト（プレーン） | `.txt` | 直接読み込み |
| Markdown | `.md` | フロントマターを保持して読み込み |
| PDF | `.pdf` | PyMuPDF でテキスト+画像を抽出 |
| Word文書 | `.docx` | python-docx でテキスト+画像を抽出 |
| 動画 | `.mp4`, `.mov`, `.avi`, `.mkv` | ffmpeg→音声抽出→Whisper文字起こし |
| 音声 | `.mp3`, `.wav`, `.m4a`, `.aac` | Whisper文字起こし |
| 画像 | `.png`, `.jpg`, `.jpeg`, `.gif`, `.webp` | Claude Vision で内容記述 |
| CSV | `.csv` | 既存processor.pyで処理 |

## 3. パイプラインアーキテクチャ

```
intake/                          ← ユーザーがファイルを置く
  ├── raw/                       ← 未処理ファイル
  ├── processing/                ← 処理中（ロック）
  ├── completed/                 ← 処理完了（アーカイブ）
  └── failed/                    ← 処理失敗（要確認）

    ↓ Stage 1: ファイル検出・ルーティング

    ↓ Stage 2: メディア変換
       ├→ PDF/DOCX → テキスト抽出 + 埋め込み画像抽出
       ├→ 動画/音声 → Whisper文字起こし
       └→ 画像 → Claude Vision記述

    ↓ Stage 3: Claude分析（並列）
       ├→ カテゴリ自動分類
       ├→ サブカテゴリ推定
       ├→ 優先度判定
       ├→ 感情タグ・言い回しタグ検出
       ├→ Q&Aペア抽出
       └→ セクション分割・要約

    ↓ Stage 4: Markdown生成
       ├→ YAMLフロントマター付きMarkdown生成
       ├→ ID自動採番（labeling-schema準拠）
       └→ ファイル名生成

    ↓ Stage 5: 検証・格納
       ├→ labeling-schema バリデーション
       ├→ 重複チェック（既存ナレッジとの類似度）
       ├→ knowledge/ に配置
       └→ 処理レポート出力
```

## 4. 並列処理設計

### 4.1 ワーカー構成

```python
asyncio.gather(
    worker_text(files_text),      # テキスト系ファイル群
    worker_media(files_media),    # 動画・音声ファイル群
    worker_image(files_image),    # 画像ファイル群
)
```

- 各ワーカーは独立して動作し、Claude API呼び出しを並列化
- APIレート制限を考慮した `asyncio.Semaphore` で同時実行数を制御
- デフォルト同時実行数: 5（設定変更可能）

### 4.2 処理フロー詳細

| ステージ | 入力 | 出力 | 並列度 |
|---------|------|------|--------|
| Stage 1: 検出 | intake/raw/ のファイル | ファイルタイプ別リスト | 1（シーケンシャル） |
| Stage 2: 変換 | 生ファイル | プレーンテキスト | ファイル数分（制限あり） |
| Stage 3: 分析 | プレーンテキスト | 構造化JSON | max_concurrent（デフォルト5） |
| Stage 4: 生成 | 構造化JSON | Markdownファイル | ファイル数分 |
| Stage 5: 検証 | Markdownファイル | knowledge/に配置 | 1（シーケンシャル） |

## 5. Claude分析プロンプト設計

### 5.1 分類プロンプト（Stage 3）

Claudeに以下を一括で推定させる:

```
入力: 抽出されたテキスト（最大8000文字）
出力JSON:
{
  "id_prefix": "VID|AUD|QA|ML|BK|TL|NL|PR",
  "category": "法人保険|ドクターマーケット|相続|営業マインド|営業スキル|コンプライアンス",
  "sub_category": "決算書分析|退職金設計|...",
  "priority": "高|中|低",
  "emotion_tags": ["励まし", "論理的解説", ...],
  "expression_tags": ["断定", "比喩表現", ...],
  "title": "推定タイトル",
  "summary": "内容の要約（50文字以内）",
  "qa_pairs": [
    {"question": "抽出されたQ", "answer": "対応するA"},
    ...
  ],
  "sections": [
    {"heading": "セクション見出し", "content": "セクション本文"},
    ...
  ],
  "knowledge_dir": "seminars|trainings|qa|articles|sales_tools",
  "confidence": 0.0〜1.0
}
```

### 5.2 画像記述プロンプト

```
この画像は生命保険営業の教材の一部です。
画像の内容を日本語で詳細に記述してください。
- 図表がある場合: データを可能な限り正確にテキスト化
- スライドの場合: 箇条書きで構造を再現
- 写真の場合: 文脈を推測して記述
```

### 5.3 動画文字起こし後処理プロンプト

```
以下はセミナー動画の文字起こしテキストです。
1. 話者の発言を整理し、読みやすい段落に分割してください
2. 「えー」「あのー」などのフィラーを除去してください
3. 専門用語の表記を統一してください
4. 重要なポイントにはマーカー（**太字**）をつけてください
```

## 6. ID自動採番ルール

| データ種別 | 検出条件 | ID形式 | 例 |
|-----------|---------|--------|-----|
| 動画文字起こし | `.mp4`,`.mov` etc. | `VID_{YYYYMM}_{連番}_{チャプター}` | VID_202602_01_01 |
| 音声文字起こし | `.mp3`,`.wav` etc. | `AUD_{YYYYMM}_{連番}_{チャプター}` | AUD_202602_01_01 |
| Q&A | QAペアとして抽出 | `QA_{連番3桁}` | QA_042 |
| PDF/書籍 | `.pdf` | `BK_{連番}_{ページ}` | BK_003_P001_020 |
| プレゼン | `.pptx` (将来対応) | `PR_{連番}` | PR_015 |
| テキスト記事 | `.txt`,`.md`,`.docx` | `ML_{YYYYMM}_{連番}` | ML_202602_001 |

連番は既存のknowledge/内の最大番号+1から自動採番する。

## 7. 検証ルール

### 7.1 必須フィールド検証
- [ ] category が VALID_CATEGORIES に含まれる
- [ ] sub_category が空でない
- [ ] priority が 高/中/低 のいずれか
- [ ] source（出典）が空でない
- [ ] content が最低50文字以上

### 7.2 重複検証
- 既存ナレッジとのタイトル類似度チェック（閾値: 0.8）
- 重複の場合: 警告を出力し、ユーザー確認待ちにする

### 7.3 品質検証
- Claude分析のconfidenceが0.6未満の場合: 手動レビュー対象にマーク
- 感情タグが未検出の場合: 警告（必須ではないが推奨）

## 8. 出力レポート

パイプライン実行後に `logs/pipeline/` にJSONレポートを出力:

```json
{
  "run_id": "20260209_143000",
  "started_at": "2026-02-09T14:30:00",
  "completed_at": "2026-02-09T14:35:22",
  "input_files": 25,
  "results": {
    "success": 22,
    "failed": 1,
    "skipped_duplicate": 2
  },
  "files_created": [
    {
      "source": "intake/raw/seminar_vol5.mp4",
      "output": "knowledge/seminars/VID_202602_01_01.md",
      "category": "法人保険",
      "confidence": 0.92
    }
  ],
  "errors": [
    {
      "source": "intake/raw/broken.pdf",
      "error": "PDF読み込みエラー: encrypted file",
      "moved_to": "intake/failed/broken.pdf"
    }
  ],
  "manual_review": [
    {
      "source": "intake/raw/ambiguous_doc.txt",
      "output": "knowledge/articles/ML_202602_001.md",
      "reason": "confidence=0.45, カテゴリ判定が曖昧"
    }
  ],
  "stats": {
    "by_category": {"法人保険": 8, "ドクターマーケット": 5, ...},
    "by_type": {"VID": 3, "QA": 10, "ML": 9},
    "total_tokens_used": 125000,
    "processing_time_seconds": 322
  }
}
```

## 9. CLI インターフェース

```bash
# 基本実行（intake/raw/ 内の全ファイルを処理）
python scripts/knowledge_pipeline.py

# ドライラン（処理せず、対象ファイルと推定結果を表示）
python scripts/knowledge_pipeline.py --dry-run

# 特定ディレクトリを指定
python scripts/knowledge_pipeline.py --input /path/to/files

# 並列度を指定
python scripts/knowledge_pipeline.py --workers 3

# 特定ファイルタイプのみ処理
python scripts/knowledge_pipeline.py --type video
python scripts/knowledge_pipeline.py --type text
python scripts/knowledge_pipeline.py --type image

# 手動レビュー対象のみ再処理
python scripts/knowledge_pipeline.py --reprocess-review

# 処理レポートを表示
python scripts/knowledge_pipeline.py --report latest
```

## 10. 依存ライブラリ

| ライブラリ | 用途 | 必須/任意 |
|-----------|------|----------|
| `anthropic` | Claude API（分析・画像記述） | 必須 |
| `PyMuPDF (fitz)` | PDF テキスト+画像抽出 | 必須 |
| `python-docx` | Word文書テキスト+画像抽出 | 必須 |
| `openai-whisper` | 音声→テキスト文字起こし | 動画/音声処理時に必須 |
| `ffmpeg-python` | 動画→音声抽出 | 動画処理時に必須 |
| `Pillow` | 画像処理 | 必須 |
| `pyyaml` | YAML生成 | 必須（既存） |

**システム依存**: `ffmpeg` がシステムにインストールされていること（動画処理時）

## 11. エラーハンドリング

| エラー種別 | 対処 |
|-----------|------|
| ファイル読み込みエラー | `intake/failed/` に移動、ログ記録 |
| Claude API エラー | 3回リトライ（指数バックオフ）、失敗時は `failed/` |
| Whisper 文字起こしエラー | `failed/` に移動、音声品質の問題を記録 |
| バリデーションエラー | `knowledge/` に配置せず、レポートに記録 |
| 重複検出 | `intake/completed/` に移動（上書きせず） |
| APIレート制限 | 自動待機+リトライ |

## 12. セキュリティ考慮

- APIキーは環境変数 `ANTHROPIC_API_KEY` から読み込み（ハードコードしない）
- intake/ 内のファイルは処理後に completed/ または failed/ に移動（raw/ を空にする）
- 個人情報を含む可能性のあるファイルは .gitignore に追加済み
- intake/ ディレクトリ全体を .gitignore に追加
