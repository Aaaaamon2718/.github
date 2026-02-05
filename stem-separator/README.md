# Stem Separator Pro

AI-Powered Stem Separation & Sound Analysis for Logic Pro

## Overview

Logic ProとAIを連携させた精密音響分析システム。**2段階分離アーキテクチャ**により、ドラムをKick/Snare/HiHat等に精密分離。Audio Spectrogram Transformerベースの音色マッチングでLogic Pro音源を自動提案。

## Features

### 音源分離（2段階アーキテクチャ）
- **Stage 1 - 粗分離**: Demucs v4で6ステム（vocals, drums, bass, guitar, piano, other）
- **Stage 2 - 精密分離**: ドラムをKick, Snare, HiHat, Toms, Ride, Crashに分離

### 音響分析
- **BPM/キー検出**: テンポ・調の自動判定
- **Timbre Embedding**: Audio Spectrogram Transformerで768次元の音色特徴量
- **スペクトル分析**: MFCC、Spectral Centroid等

### Logic Pro音色マッチング
- **プリセットカタログ**: Logic Pro全音源の特徴量DB
- **コサイン類似度検索**: 分離ステムに最も近いプリセットをTop-N提案
- **ドラム専用マッチャー**: Drum Kit Designer/Drum Machine Designerに特化

### MIDI変換 & AIアドバイス
- **ポリフォニック対応**: 和音も正確に検出
- **Claude AI連携**: 音作りガイド、推奨エフェクト設定

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    STEM SEPARATOR PRO v2                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  [入力: 楽曲ファイル]                                                    │
│         │                                                               │
│         ▼                                                               │
│  ┌──────────────────┐                                                   │
│  │ STAGE 1: 粗分離  │  Demucs v4 / htdemucs_6s                         │
│  │ 6ステム出力      │  vocals, drums, bass, guitar, piano, other       │
│  └────────┬─────────┘                                                   │
│           │                                                             │
│     ┌─────┴─────┬─────────┬──────────┬──────────┬──────────┐           │
│     ▼           ▼         ▼          ▼          ▼          ▼           │
│  [vocals]   [drums]    [bass]    [guitar]   [piano]    [other]         │
│                 │                                                       │
│                 ▼                                                       │
│  ┌──────────────────────────────────────────────────────────┐          │
│  │ STAGE 2: ドラム精密分離                                   │          │
│  │ → Kick, Snare, HiHat, Toms, Ride, Crash                  │          │
│  └──────────────────────────────────────────────────────────┘          │
│                    │                                                    │
│                    ▼                                                    │
│  ┌──────────────────────────────────────────────────────────┐          │
│  │ STAGE 3: 音響分析 + MIDI変換                             │          │
│  │ • Timbre Embedding (AST 768次元)                         │          │
│  │ • BPM/Key検出、MFCC、スペクトル分析                       │          │
│  │ • ポリフォニックMIDI変換                                  │          │
│  └──────────────────────────────────────────────────────────┘          │
│                    │                                                    │
│                    ▼                                                    │
│  ┌──────────────────────────────────────────────────────────┐          │
│  │ STAGE 4: Logic Pro音色マッチング                         │          │
│  │ • プリセットカタログDBとコサイン類似度計算                │          │
│  │ • Top-N類似プリセット提案                                 │          │
│  │ • EQ/エフェクト調整ヒント生成                             │          │
│  └──────────────────────────────────────────────────────────┘          │
│                    │                                                    │
│                    ▼                                                    │
│  ┌──────────────────────────────────────────────────────────┐          │
│  │ STAGE 5: 出力                                            │          │
│  │ • 分離WAV (各ステム + ドラムパーツ)                       │          │
│  │ • MIDIファイル                                           │          │
│  │ • Claude AIアドバイス                                     │          │
│  └──────────────────────────────────────────────────────────┘          │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## Requirements

- macOS (Apple Silicon recommended)
- Python 3.10+
- Homebrew
- ffmpeg

## Quick Start

```bash
# 1. Clone repository
git clone https://github.com/Aaaaamon2718/stem-separator.git
cd stem-separator

# 2. Run setup
chmod +x setup.sh
./setup.sh

# 3. Activate environment
source venv/bin/activate

# 4. Process audio
python main.py process your_track.mp3
```

## Usage

### CLI (Terminal)

```bash
# Full processing (separation + analysis + MIDI + advice)
python main.py process track.mp3

# Separation only
python separator.py track.mp3

# Batch processing
python file_manager.py ./folder/ -r

# Watch mode (auto-process new files)
python file_manager.py --watch ./incoming/

# Interactive mode
python main.py interactive

# Check status
python main.py status
```

### Web UI

```bash
streamlit run web_ui.py
# Open http://localhost:8501
```

### Logic Pro Import

```bash
python logic_import.py ~/Music/Stems/2024-02-04_Track/
```

## Output Structure

```
~/Music/Stems/
└── 2024-02-04_Track_Name/
    ├── stage1/                 # Stage 1: 粗分離
    │   ├── vocals.wav
    │   ├── drums.wav
    │   ├── bass.wav
    │   ├── guitar.wav
    │   ├── piano.wav
    │   └── other.wav
    │
    ├── stage2/                 # Stage 2: ドラム精密分離
    │   └── drums/
    │       ├── kick.wav
    │       ├── snare.wav
    │       ├── hihat.wav
    │       ├── toms.wav
    │       ├── ride.wav
    │       └── crash.wav
    │
    ├── midi/                   # MIDI変換結果
    │   ├── bass.mid
    │   ├── piano.mid
    │   ├── kick.mid
    │   └── ...
    │
    ├── analysis/               # 分析レポート
    │   ├── combined.json
    │   └── *_analysis.json
    │
    └── advice/                 # AIアドバイス
        └── production_guide.md
```

## Project Structure

```
stem-separator/
├── main.py               # Unified CLI
├── separator.py          # Demucs separation core
├── file_manager.py       # Batch processing & watch mode
├── logic_import.py       # Logic Pro auto-import
├── web_ui.py             # Streamlit Web UI
├── setup.sh              # Setup script
├── requirements.txt      # Dependencies
├── config/
│   └── settings.yaml     # Configuration
└── src/
    ├── __init__.py
    ├── audio_analyzer.py  # Audio feature extraction
    ├── note_detector.py   # Note detection & MIDI
    ├── catalog_builder.py # Logic Pro sound catalog
    ├── matcher.py         # Similarity matching
    ├── claude_advisor.py  # Claude API integration
    └── prompt_builder.py  # Prompt construction
```

## Configuration

Edit `config/settings.yaml`:

```yaml
output:
  base_dir: "~/Music/Stems"
  format: "wav"
  naming: "date_title"  # date_title, title, flat

separation:
  model: "htdemucs_6s"  # htdemucs_6s (6-stem) or htdemucs (4-stem)
  device: "auto"        # auto, mps, cuda, cpu

analysis:
  extract_midi: true
  detect_chords: true
  detect_fills: true

claude:
  api_key: "${ANTHROPIC_API_KEY}"
  model: "claude-sonnet-4-20250514"
```

## Claude API Setup (Optional)

```bash
export ANTHROPIC_API_KEY="your-api-key-here"
```

Without API key, the system runs in offline mode with template-based advice.

## Troubleshooting

### Silent output files
```bash
pip uninstall torchcodec -y
pip install soundfile
```

### MPS (GPU) issues
```bash
python main.py process track.mp3 --device cpu
```

## License

MIT License - Personal use only.

## Author

Amon - AI Engineer & EDM Producer
