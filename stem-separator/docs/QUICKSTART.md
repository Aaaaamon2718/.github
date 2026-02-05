# Stem Separator Pro - 完全マニュアル（0→100）

このドキュメントでは、Stem Separator Proを**ゼロから完全に動作させるまで**の全手順を解説します。

---

## 目次

1. [前提条件の確認](#1-前提条件の確認)
2. [環境構築](#2-環境構築)
3. [初回セットアップ](#3-初回セットアップ)
4. [基本的な使い方](#4-基本的な使い方)
5. [5段階パイプライン詳細](#5-5段階パイプライン詳細)
6. [Web UIの使用](#6-web-uiの使用)
7. [GitHub同期の設定](#7-github同期の設定)
8. [トラブルシューティング](#8-トラブルシューティング)

---

## 1. 前提条件の確認

### 必要なもの

| 項目 | 要件 | 確認コマンド |
|------|------|--------------|
| macOS | Ventura以降推奨 | `sw_vers` |
| Python | 3.10以上 | `python3 --version` |
| Homebrew | 最新版 | `brew --version` |
| Git | 最新版 | `git --version` |
| 空き容量 | 10GB以上 | `df -h` |

### ハードウェア推奨

- **CPU**: Apple Silicon (M1/M2/M3)
- **RAM**: 16GB以上
- **Storage**: SSD

> **Note**: Apple Siliconの場合、MPS（Metal Performance Shaders）による高速処理が可能です。

---

## 2. 環境構築

### Step 2.1: Homebrewのインストール（未インストールの場合）

```bash
# Homebrewインストール
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# パスを通す（Apple Silicon Macの場合）
echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
eval "$(/opt/homebrew/bin/brew shellenv)"
```

### Step 2.2: 必須ツールのインストール

```bash
# ffmpeg（音声コーデック処理に必須）
brew install ffmpeg

# 確認
ffmpeg -version
```

### Step 2.3: Pythonの確認/インストール

```bash
# Python 3.10以上か確認
python3 --version

# 古い場合はpyenvでインストール
brew install pyenv
pyenv install 3.11.7
pyenv global 3.11.7
```

---

## 3. 初回セットアップ

### Step 3.1: リポジトリのクローン

```bash
# ホームディレクトリに移動
cd ~

# リポジトリをクローン
git clone https://github.com/Aaaaamon2718/.github.git

# プロジェクトディレクトリに移動
cd ~/.github/stem-separator
```

### Step 3.2: 仮想環境の作成

```bash
# 仮想環境を作成
python3 -m venv venv

# 仮想環境を有効化
source venv/bin/activate

# (venv)が表示されていることを確認
```

### Step 3.3: 依存パッケージのインストール

```bash
# pipをアップグレード
pip install --upgrade pip

# 依存パッケージをインストール（5-10分かかります）
pip install -r requirements.txt
```

### Step 3.4: インストール確認

```bash
# システム状態を確認
python main.py status
```

期待される出力:
```
┌─────────────┬────────┬──────────────────────────┐
│ Component   │ Status │ Details                  │
├─────────────┼────────┼──────────────────────────┤
│ Python      │ OK     │ v3.11.7                  │
│ PyTorch     │ OK     │ v2.x.x (MPS)             │
│ Demucs      │ OK     │ Stem separation ready    │
│ librosa     │ OK     │ Audio analysis ready     │
│ basic-pitch │ OK     │ Note detection ready     │
│ ffmpeg      │ OK     │ Audio codec support      │
└─────────────┴────────┴──────────────────────────┘
```

### Step 3.5: 出力ディレクトリの作成

```bash
# 出力先ディレクトリを作成
mkdir -p ~/Music/Stems
```

---

## 4. 基本的な使い方

### 4.1: 最もシンプルな使い方

```bash
# 仮想環境を有効化（毎回必要）
cd ~/.github/stem-separator
source venv/bin/activate

# 楽曲を処理（フルパイプライン）
python main.py process ~/Downloads/your_track.mp3
```

これだけで、以下が自動実行されます:
1. 6ステム分離（vocals, drums, bass, guitar, piano, other）
2. ドラム精密分離（kick, snare, hihat, toms, ride, crash）
3. 音響分析 + MIDI変換
4. Logic Pro音色マッチング
5. AIアドバイス生成

### 4.2: オプション付き実行

```bash
# ドラム精密分離をスキップ
python main.py process track.mp3 --no-drums

# 分析のみスキップ
python main.py process track.mp3 --no-analyze

# AIアドバイスをスキップ
python main.py process track.mp3 --no-advice

# CPUで実行（GPU問題時）
python main.py process track.mp3 --device cpu
```

### 4.3: 個別機能の実行

```bash
# 分離のみ
python main.py separate track.mp3

# 分析のみ（既存ステムフォルダに対して）
python main.py analyze ~/Music/Stems/2024-02-04_Track/stage1/

# MIDI変換のみ
python main.py midi ~/Music/Stems/2024-02-04_Track/stage1/
```

---

## 5. 5段階パイプライン詳細

### Stage 1: 粗分離（Demucs）

```bash
# Stage 1のみ実行
python separator.py track.mp3
```

出力:
```
~/Music/Stems/YYYY-MM-DD_TrackName/
└── stage1/
    ├── vocals.wav
    ├── drums.wav
    ├── bass.wav
    ├── guitar.wav
    ├── piano.wav
    └── other.wav
```

### Stage 2: ドラム精密分離

```bash
# 2段階分離を実行
python main.py process track.mp3
```

出力:
```
~/Music/Stems/YYYY-MM-DD_TrackName/
├── stage1/
│   └── (6ステム)
└── stage2/
    └── drums/
        ├── kick.wav
        ├── snare.wav
        ├── hihat.wav
        ├── toms.wav
        ├── ride.wav
        └── crash.wav
```

### Stage 3: 音響分析 + MIDI

分析結果:
```
~/Music/Stems/YYYY-MM-DD_TrackName/
├── analysis/
│   ├── combined.json      # 全体サマリー
│   ├── vocals_analysis.json
│   ├── bass_analysis.json
│   └── ...
└── midi/
    ├── bass.mid
    ├── piano.mid
    └── ...
```

### Stage 4: Logic Pro音色マッチング

コンソール出力:
```
Matching main stems...
  bass: Fingerstyle Bass (87%)
  piano: Grand Piano (92%)
  guitar: Clean Electric (78%)

Recommended Kit: SoCal Kit
```

### Stage 5: AIアドバイス

```
~/Music/Stems/YYYY-MM-DD_TrackName/
└── advice/
    └── production_guide.md
```

---

## 6. Web UIの使用

### 起動

```bash
cd ~/.github/stem-separator
source venv/bin/activate
streamlit run web_ui.py
```

ブラウザで `http://localhost:8501` が自動で開きます。

### 機能

1. **ファイルアップロード**: ドラッグ&ドロップで楽曲をアップロード
2. **リアルタイム進捗**: 処理状況をプログレスバーで表示
3. **結果プレビュー**: 分離ステムを波形表示・試聴
4. **ダウンロード**: 個別/一括でダウンロード

---

## 7. GitHub同期の設定

### Claude API設定（オプション）

```bash
# .envファイルを作成
echo 'ANTHROPIC_API_KEY=your-api-key-here' > ~/.github/stem-separator/.env
```

### GitHub同期の有効化

```bash
# 分析結果をGitHubに自動同期
python main.py process track.mp3 --sync-github

# または設定ファイルで有効化
# config/settings.yaml
github:
  auto_sync: true
  branch: "analysis-results"
```

同期される内容:
- `analysis/*.json` - 分析データ
- `advice/*.md` - AIアドバイス
- メタデータ（BPM、キー、処理日時）

---

## 8. トラブルシューティング

### 問題: 出力ファイルが無音

```bash
# torchcodecの問題を解決
pip uninstall torchcodec -y
pip install soundfile
```

### 問題: MPS (GPU) エラー

```bash
# CPUモードで実行
python main.py process track.mp3 --device cpu
```

### 問題: メモリ不足

```bash
# 長い楽曲（10分以上）の場合
# 分割して処理するか、swap領域を増やす
sudo sysctl -w vm.swapusage
```

### 問題: ffmpegが見つからない

```bash
# パスを確認
which ffmpeg

# 再インストール
brew reinstall ffmpeg
```

### 問題: Demucsモデルのダウンロード失敗

```bash
# キャッシュをクリアして再ダウンロード
rm -rf ~/.cache/torch/hub/checkpoints/htdemucs*
python -c "import demucs.pretrained; demucs.pretrained.get_model('htdemucs_6s')"
```

---

## クイックリファレンス

### 毎回の起動手順

```bash
cd ~/.github/stem-separator
source venv/bin/activate
python main.py process YOUR_TRACK.mp3
```

### よく使うコマンド

| コマンド | 説明 |
|----------|------|
| `python main.py process FILE` | フル処理 |
| `python main.py separate FILE` | 分離のみ |
| `python main.py status` | システム確認 |
| `python main.py interactive` | 対話モード |
| `streamlit run web_ui.py` | Web UI起動 |

### 出力先

```
~/Music/Stems/YYYY-MM-DD_TrackName/
├── stage1/          # 6ステム
├── stage2/drums/    # ドラムパーツ
├── midi/            # MIDIファイル
├── analysis/        # 分析JSON
└── advice/          # AIアドバイス
```

---

## 次のステップ

1. **Logic Pro連携**: `python logic_import.py OUTPUT_DIR` で自動インポート
2. **バッチ処理**: `python main.py batch ./folder/ -r` で複数ファイル処理
3. **監視モード**: `python main.py batch --watch ./incoming/` で自動処理

---

**Author**: Amon
**Last Updated**: 2024-02-05
