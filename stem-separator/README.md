# Stem Separator

AI-Powered Stem Separation & Sound Analysis for Logic Pro

## Overview

Logic ProとAIを連携させた音響分析システム。Demucs v4による高精度な音源分離と、Claude AIによる音作りアドバイスを提供。

## Features

- **6ステム分離**: ボーカル、ドラム、ベース、ギター、ピアノ、その他に高精度分離（Demucs v4）
- **音響分析**: BPM、キー、スペクトル特徴量の自動検出
- **ノート検出**: MIDI変換、コード進行検出、フィルイン検出
- **Logic Pro連携**: 類似音源マッチング、自動インポート
- **AIアドバイス**: Claude APIによる音作りアドバイス生成
- **Apple Silicon最適化**: MPS（GPU）による高速処理

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Your Mac                             │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌─────────────┐    ┌──────────────┐    ┌───────────┐  │
│  │ Input Audio │───▶│  Demucs v4   │───▶│ 6 Stems   │  │
│  │ (WAV/MP3)   │    │  Separator   │    │ (WAV)     │  │
│  └─────────────┘    └──────────────┘    └───────────┘  │
│                            │                     │      │
│                            ▼                     ▼      │
│                     ┌──────────────┐    ┌───────────┐  │
│                     │ Audio        │    │ Logic Pro │  │
│                     │ Analyzer     │    │ Import    │  │
│                     └──────────────┘    └───────────┘  │
│                            │                           │
│                            ▼                           │
│                     ┌──────────────┐                   │
│                     │ Claude API   │                   │
│                     │ Advisor      │                   │
│                     └──────────────┘                   │
│                                                         │
└─────────────────────────────────────────────────────────┘
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
└── 2024-02-04_Track Name/
    ├── vocals.wav      # Vocals
    ├── drums.wav       # Drums
    ├── bass.wav        # Bass
    ├── guitar.wav      # Guitar
    ├── piano.wav       # Piano
    ├── other.wav       # Other (synths, etc.)
    ├── bass.mid        # MIDI files
    ├── piano.mid
    └── *_analysis.json # Analysis reports
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
