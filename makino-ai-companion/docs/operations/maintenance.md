# 保守運用ガイド

## 日常運用フロー

### 1. ログ確認

毎日、SQLiteデータベースのログを確認し、以下をチェックする:

- エスカレーションの発生有無
- 低確信度回答の有無
- Bad評価の有無
- システムエラーの有無

```bash
# KPI指標の確認
python cli.py logs metrics

# CSVエクスポート（GitHub監査用）
python cli.py logs export
```

### 2. ナレッジベース更新

新しいナレッジを追加する手順:

1. 追加するデータをMarkdown形式で作成（YAMLフロントマター付き）
2. `knowledge/` の該当サブディレクトリに配置
3. `python cli.py knowledge validate` でバリデーション
4. `python cli.py knowledge stats` で統計確認
5. git commit & push

### 3. プロンプト調整

回答品質に問題がある場合の調整手順:

1. 問題のある回答ログを特定
2. 原因分析（ナレッジ不足 / プロンプト問題 / RAG検索精度）
3. 該当箇所の修正
4. 修正前後の比較テスト

## トラブルシューティング

| 症状 | 原因候補 | 対処法 |
|------|---------|--------|
| AI伴走システムが応答しない | FastAPIサーバーダウン | `python app.py` で再起動、プロセス状態確認 |
| 回答が生成されない | APIキー期限切れ | `ANTHROPIC_API_KEY` の更新 |
| ログが記録されない | SQLite接続エラー | `data/conversations.db` のパスと権限を確認 |
| 回答精度が低下 | ナレッジベースの不足 | `knowledge/` のデータ拡充・検証 |
| 人格が崩壊する | プロンプト設定の不整合 | `src/prompts/system_prompts.py` の再確認 |

## サーバー管理

### サーバーの起動・停止

```bash
# 起動
python app.py
# → http://localhost:8000

# 開発モード（自動リロード）
python cli.py server start --reload

# 停止
Ctrl+C
```

### ナレッジベースの管理

```bash
# 統計情報
python cli.py knowledge stats

# バリデーション
python cli.py knowledge validate

# プロンプトテスト
python cli.py prompt test --pattern 1 --question "決算書の見方を教えて"
```

## 2年目以降の保守サポート範囲

### 基本サポート（含む）

- エラー対応（API連携エラー、サーバーダウン等）
- 技術的相談（Claude APIアップデート影響、操作方法）
- 軽微な修正（フレーズ微修正、パラメータ調整）

### オプション（別途相談）

- 定期的なナレッジ更新作業
- 月次レポート作成
- 大規模なプロンプト改修
- 新規Pattern追加
- Q&Aデータ詳細分析
