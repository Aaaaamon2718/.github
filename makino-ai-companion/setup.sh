#!/bin/bash
# =============================================================================
# 牧野生保塾 AI伴走システム - セットアップスクリプト
# =============================================================================

set -e

echo "=== 牧野生保塾 AI伴走システム セットアップ ==="
echo ""

# Python バージョン確認
python3 --version || {
    echo "Error: Python 3.10+ が必要です"
    exit 1
}

# 仮想環境の作成
if [ ! -d "venv" ]; then
    echo "仮想環境を作成中..."
    python3 -m venv venv
    echo "仮想環境を作成しました"
fi

# 仮想環境の有効化
echo "仮想環境を有効化中..."
source venv/bin/activate

# 依存関係のインストール
echo "依存関係をインストール中..."
pip install -r requirements.txt

# 設定ファイルのコピー
if [ ! -f "config/settings.yaml" ]; then
    echo "設定ファイルが見つかりません"
    echo "config/settings.yaml を環境に合わせて編集してください"
fi

# データディレクトリの作成
mkdir -p data
mkdir -p output
mkdir -p reports
mkdir -p cache

echo ""
echo "=== セットアップ完了 ==="
echo ""
echo "次のステップ:"
echo "  1. config/settings.yaml を環境に合わせて編集"
echo "  2. 環境変数を設定（.env ファイルまたはexport）"
echo "  3. source venv/bin/activate で仮想環境を有効化"
echo ""
