# Stem Separator セットアップガイド

## クイックスタート

### 1. リポジトリをクローン

```bash
git clone https://github.com/Aaaaamon2718/.github.git
cd .github/stem-separator
```

### 2. セットアップ実行

```bash
chmod +x setup.sh
./setup.sh
```

### 3. 仮想環境をアクティベート

```bash
source venv/bin/activate
```

### 4. 動作確認

```bash
python main.py status
```

全て ✓ が出れば成功。

---

## 使い方

### 基本的な処理

```bash
# フル処理（分離 → 分析 → MIDI → アドバイス）
python main.py process ~/Music/track.mp3

# 分離のみ
python separator.py ~/Music/track.mp3

# インタラクティブモード
python main.py interactive
```

### バッチ処理

```bash
# フォルダ内の全音源を処理
python file_manager.py ~/Music/ToProcess/

# 監視モード（新規ファイル自動処理）
python file_manager.py --watch ~/Music/Incoming/
```

### Web UI

```bash
streamlit run web_ui.py
# ブラウザで http://localhost:8501 を開く
```

### Logic Pro連携

```bash
python logic_import.py ~/Music/Stems/2024-02-04_Track/
```

---

## 出力結果

処理後、以下の場所にファイルが出力されます：

```
~/Music/Stems/
└── 2024-02-04_TrackName/
    ├── vocals.wav      # ボーカル
    ├── drums.wav       # ドラム
    ├── bass.wav        # ベース
    ├── guitar.wav      # ギター
    ├── piano.wav       # ピアノ
    ├── other.wav       # その他（シンセ等）
    ├── bass.mid        # MIDIファイル
    ├── piano.mid
    └── *_analysis.json # 分析レポート
```

---

## トラブルシューティング

### 無音ファイルが出力される

```bash
pip uninstall torchcodec -y
pip install soundfile
```

### GPUエラー

```bash
python main.py process track.mp3 --device cpu
```

### Claude APIキーの設定

```bash
export ANTHROPIC_API_KEY="your-api-key-here"
```

APIキーがなくてもオフラインモードで動作します。
