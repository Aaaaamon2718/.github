# reel-research

Instagramリール競合分析の蓄積データベース。詳細な分析基準は `CLAUDE.md` を参照。

## セットアップ手順

1. このフォルダをローカルの作業ディレクトリに配置し、Claude Codeで開く
2. 以下の初期化プロンプトをそのままClaude Codeに投げる
3. `git init` 及び初回commitまで完了させる（pushは任意・失敗しても問題ない運用）

初期化プロンプト（Claude Codeにそのまま貼り付け）

```
このフォルダをgitリポジトリとして初期化してください。
CLAUDE.mdの内容を読み込んだ上で、以下を実行してください。

1. git init し、.gitignoreを作成（.DS_Store, *.tmp 等の一般的な除外設定）
2. 現在のフォルダ構成（templates/, insights/, index.md, README.md, CLAUDE.md）で
   初回コミットを作成（コミットメッセージ: "chore: 初期セットアップ"）
3. accounts/ フォルダはまだ作らず、新しいアカウントを分析する際に
   その都度 profile-template.md を使って作成する運用とする

準備ができたら、最初の分析対象アカウント名を教えてほしいと私に確認してください。

```

## 通常の分析フロー

1. リール動画を場面ごとにスクリーンショットで保存
2. Claude Codeに「〇〇（アカウント名）の分析をしたい」と伝え、スクショを渡す
3. Claude CodeがCLAUDE.mdの基準に沿って `templates/report-template.md` を元にレポート作成
4. 参考資料は `accounts/{アカウント名}/references/{日付}_{連番}/` に配置（手動でスクショをコピー）
5. 内容を確認し、問題なければ「gitに格納して」と指示 → commit（push指示があればpushも）
6. `index.md` への行追加もあわせて依頼する

## 資産活用フロー（分析が溜まってきたら）

* 「傾向をまとめて」→ `insights/patterns.md` を更新
* 「撮影シートを作って」→ `templates/shotlist-template.md` を元に、蓄積データから生成
* 「投稿案を考えて」→ 各レポートの「8. 自分への転用ポイント」を横断参照して提案
