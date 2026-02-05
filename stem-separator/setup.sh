#!/bin/bash

# ==============================================
#    Stem Separator - Setup
#    Apple Silicon Optimized
# ==============================================

set -e

echo "=============================================="
echo "   Stem Separator - Setup"
echo "   Apple Silicon Optimized"
echo "=============================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; }
info() { echo -e "[INFO] $1"; }
warn() { echo -e "${YELLOW}[WARNING]${NC} $1"; }

# Check system
info "Checking system environment..."

# Check Apple Silicon
if [[ $(uname -m) == "arm64" ]]; then
    success "Apple Silicon detected: MPS (GPU) optimization enabled"
    DEVICE="mps"
else
    warn "Intel Mac detected: Using CPU mode"
    DEVICE="cpu"
fi

# Check Homebrew
if command -v brew &> /dev/null; then
    success "Homebrew detected"
else
    error "Homebrew not found. Please install from https://brew.sh"
    exit 1
fi

# Check Python
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
    success "Python detected: $PYTHON_VERSION"
else
    error "Python3 not found. Please install Python 3.10+"
    exit 1
fi

# Check ffmpeg
info "Checking system dependencies..."
if command -v ffmpeg &> /dev/null; then
    success "ffmpeg detected"
else
    info "Installing ffmpeg..."
    brew install ffmpeg
    success "ffmpeg installed"
fi

# Create virtual environment
info "Creating Python virtual environment..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/venv"

if [ -d "$VENV_DIR" ]; then
    warn "Virtual environment already exists. Recreating..."
    rm -rf "$VENV_DIR"
fi

python3 -m venv "$VENV_DIR"
success "Virtual environment created: $VENV_DIR"

# Activate virtual environment
source "$VENV_DIR/bin/activate"
success "Virtual environment activated"

# Upgrade pip
info "Upgrading pip..."
pip install --upgrade pip > /dev/null 2>&1

# Install packages
info "Installing Python packages..."
info "(This may take a few minutes on first run)"

if [ -f "$SCRIPT_DIR/requirements.txt" ]; then
    pip install -r "$SCRIPT_DIR/requirements.txt"
    success "All packages installed"
else
    error "requirements.txt not found"
    exit 1
fi

# Create output directory
OUTPUT_DIR="$HOME/Music/Stems"
mkdir -p "$OUTPUT_DIR"
success "Output directory created: $OUTPUT_DIR"

# Download Demucs models (optional)
info "Pre-downloading Demucs models..."
python -c "import demucs.pretrained; demucs.pretrained.get_model('htdemucs_6s')" 2>/dev/null || warn "Model download skipped (will download on first use)"

echo ""
echo "=============================================="
echo "   Setup Complete!"
echo "=============================================="
echo ""
echo "To start using:"
echo "  source venv/bin/activate"
echo "  python main.py process your_track.mp3"
echo ""
echo "Or try interactive mode:"
echo "  python main.py interactive"
echo ""
