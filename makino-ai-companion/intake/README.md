# intake/ — ナレッジ投入用ステージングディレクトリ

## 使い方

1. `raw/` に教材ファイルを置く
2. `python scripts/knowledge_pipeline.py` を実行
3. 処理結果が `knowledge/` に格納される

## ディレクトリ構成

```
intake/
├── raw/          ← ここにファイルを置く
├── processing/   ← 処理中（自動管理）
├── completed/    ← 処理完了（アーカイブ）
├── failed/       ← 処理失敗（要確認）
└── README.md     ← このファイル
```

## 対応フォーマット

| 種別 | 拡張子 |
|------|--------|
| テキスト | `.txt`, `.md`, `.csv` |
| PDF | `.pdf` |
| Word | `.docx` |
| 動画 | `.mp4`, `.mov`, `.avi`, `.mkv` |
| 音声 | `.mp3`, `.wav`, `.m4a`, `.aac` |
| 画像 | `.png`, `.jpg`, `.jpeg`, `.gif`, `.webp` |

## 注意

- `raw/` 以外のディレクトリはパイプラインが自動管理する
- 処理済みファイルは `completed/` に移動される
- 失敗したファイルは `failed/` に移動される
- このディレクトリ内のファイル（README.md以外）は `.gitignore` で除外されている
