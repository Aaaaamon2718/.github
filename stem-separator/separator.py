#!/usr/bin/env python3
"""
Stem Separator Pro - 2段階分離アーキテクチャ
Stage 1: Demucs v4 (6ステム粗分離)
Stage 2: ドラム精密分離 (Kick, Snare, HiHat, Toms, Ride, Crash)
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List

import yaml
import numpy as np
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()

# Default settings
DEFAULT_MODEL = "htdemucs_6s"  # 6-stem model
DEFAULT_OUTPUT_DIR = Path.home() / "Music" / "Stems"
SUPPORTED_FORMATS = {".mp3", ".wav", ".m4a", ".flac", ".aiff", ".ogg"}

# Stem names for each model
STEM_NAMES = {
    "htdemucs_6s": ["vocals", "drums", "bass", "guitar", "piano", "other"],
    "htdemucs": ["vocals", "drums", "bass", "other"],
}

# ドラム精密分離のターゲット
DRUM_PARTS = ["kick", "snare", "hihat", "toms", "ride", "crash"]


def load_config() -> dict:
    """Load configuration from settings.yaml"""
    config_path = Path(__file__).parent / "config" / "settings.yaml"
    if config_path.exists():
        with open(config_path) as f:
            return yaml.safe_load(f)
    return {}


def get_device() -> str:
    """Detect best available device"""
    try:
        import torch
        if torch.backends.mps.is_available():
            return "mps"
        elif torch.cuda.is_available():
            return "cuda"
    except ImportError:
        pass
    return "cpu"


def separate_track(
    input_path: str,
    output_dir: Optional[str] = None,
    model: str = DEFAULT_MODEL,
    device: Optional[str] = None,
    open_finder: bool = True,
) -> Optional[Path]:
    """
    Separate audio track into stems using Demucs.

    Args:
        input_path: Path to input audio file
        output_dir: Output directory (default: ~/Music/Stems)
        model: Demucs model name
        device: Device to use (auto, mps, cuda, cpu)
        open_finder: Open Finder after completion

    Returns:
        Path to output directory or None if failed
    """
    input_path = Path(input_path).resolve()

    # Validate input
    if not input_path.exists():
        console.print(f"[red]File not found: {input_path}[/red]")
        return None

    if input_path.suffix.lower() not in SUPPORTED_FORMATS:
        console.print(f"[red]Unsupported format: {input_path.suffix}[/red]")
        console.print(f"Supported formats: {', '.join(SUPPORTED_FORMATS)}")
        return None

    # Setup output directory
    if output_dir:
        base_output = Path(output_dir).expanduser()
    else:
        base_output = DEFAULT_OUTPUT_DIR

    base_output.mkdir(parents=True, exist_ok=True)

    # Create dated output folder
    date_str = datetime.now().strftime("%Y-%m-%d")
    track_name = input_path.stem
    final_output_dir = base_output / f"{date_str}_{track_name}"

    # Detect device
    if device is None or device == "auto":
        device = get_device()

    # Print info
    console.print(Panel.fit(
        "[bold cyan]Stem Separator[/bold cyan]\n"
        "[dim]Powered by Demucs v4[/dim]",
        border_style="cyan"
    ))

    console.print(f"\nInput: [bold]{input_path.name}[/bold]")
    console.print(f"Path: {input_path}")

    if device == "mps":
        console.print("[green]Apple Silicon MPS (GPU) enabled[/green]")
    elif device == "cuda":
        console.print("[green]NVIDIA CUDA (GPU) enabled[/green]")
    else:
        console.print("[yellow]Using CPU mode[/yellow]")

    console.print(f"\nModel: [cyan]{model}[/cyan]")
    console.print(f"Output: [cyan]{final_output_dir}[/cyan]")
    console.print(f"Stems: [cyan]{', '.join(STEM_NAMES.get(model, ['unknown']))}[/cyan]")

    console.print("\n" + "=" * 50)
    console.print("[bold]Starting separation...[/bold]")
    console.print("=" * 50 + "\n")

    # Build Demucs command
    python_path = sys.executable
    cmd = [
        python_path, "-m", "demucs",
        "--name", model,
        "--device", device,
        "--jobs", "2",
        "--shifts", "1",
        "--overlap", "0.25",
        "--out", str(base_output),
        str(input_path)
    ]

    console.print(f"[dim]Command: {' '.join(cmd)}[/dim]\n")

    # Run Demucs
    try:
        result = subprocess.run(
            cmd,
            capture_output=False,
            text=True,
            check=True
        )
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Separation failed: {e}[/red]")
        return None
    except FileNotFoundError:
        console.print("[red]Demucs not found. Please run setup.sh first.[/red]")
        return None

    # Reorganize output files
    console.print("\n[dim]Reorganizing output files...[/dim]")

    # Demucs outputs to: base_output/model_name/track_name/
    demucs_output = base_output / model / track_name

    if not demucs_output.exists():
        console.print(f"[red]Separation output not found: {demucs_output}[/red]")
        return None

    # Create final output directory
    final_output_dir.mkdir(parents=True, exist_ok=True)

    # Move stem files
    stem_files = list(demucs_output.glob("*.wav"))
    if not stem_files:
        console.print(f"[red]No stem files found in {demucs_output}[/red]")
        return None

    for stem_file in stem_files:
        dest = final_output_dir / stem_file.name
        shutil.move(str(stem_file), str(dest))
        console.print(f"  [green]{stem_file.name}[/green]")

    # Cleanup Demucs temp directory
    try:
        shutil.rmtree(base_output / model)
    except Exception:
        pass

    console.print(f"\n[bold green]Separation complete![/bold green]")
    console.print(f"Output: {final_output_dir}")

    # Open Finder
    if open_finder:
        try:
            subprocess.run(["open", str(final_output_dir)], check=False)
        except Exception:
            pass

    return final_output_dir


def main():
    """CLI entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Separate audio into stems using Demucs"
    )
    parser.add_argument("input", help="Input audio file")
    parser.add_argument(
        "-o", "--output",
        help="Output directory (default: ~/Music/Stems)"
    )
    parser.add_argument(
        "-m", "--model",
        default=DEFAULT_MODEL,
        choices=["htdemucs_6s", "htdemucs"],
        help="Demucs model (default: htdemucs_6s)"
    )
    parser.add_argument(
        "-d", "--device",
        choices=["auto", "mps", "cuda", "cpu"],
        default="auto",
        help="Device to use (default: auto)"
    )
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="Don't open Finder after completion"
    )

    args = parser.parse_args()

    result = separate_track(
        input_path=args.input,
        output_dir=args.output,
        model=args.model,
        device=args.device,
        open_finder=not args.no_open
    )

    if result is None:
        sys.exit(1)


class DrumSeparator:
    """
    ドラム精密分離エンジン
    ドラムステムをKick, Snare, HiHat, Toms, Ride, Crashに分離
    """

    def __init__(self):
        self._librosa = None
        self._scipy = None

    @property
    def librosa(self):
        if self._librosa is None:
            import librosa
            self._librosa = librosa
        return self._librosa

    @property
    def scipy(self):
        if self._scipy is None:
            import scipy.signal
            self._scipy = scipy.signal
        return self._scipy

    def separate(
        self,
        drums_path: str,
        output_dir: str
    ) -> Dict[str, Path]:
        """
        ドラムステムを各パーツに分離

        Args:
            drums_path: drums.wavのパス
            output_dir: 出力ディレクトリ

        Returns:
            パーツ名 -> ファイルパスの辞書
        """
        drums_path = Path(drums_path)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        console.print("\n[bold cyan]Stage 2: Drum Fine Separation[/bold cyan]")

        # ドラムを読み込み
        y, sr = self.librosa.load(str(drums_path), sr=44100, mono=False)
        if y.ndim == 1:
            y = np.array([y, y])  # モノラルをステレオに

        results = {}

        # 周波数帯域ベースの分離
        console.print("  [dim]Separating by frequency bands...[/dim]")

        # Kick (20-150Hz)
        kick = self._bandpass_filter(y, sr, 20, 150)
        results["kick"] = self._save_stem(kick, sr, output_dir / "kick.wav")

        # Snare (150-500Hz + トランジェント)
        snare = self._extract_snare(y, sr)
        results["snare"] = self._save_stem(snare, sr, output_dir / "snare.wav")

        # HiHat (5000-15000Hz)
        hihat = self._bandpass_filter(y, sr, 5000, 15000)
        results["hihat"] = self._save_stem(hihat, sr, output_dir / "hihat.wav")

        # Toms (80-400Hz, kick除外)
        toms = self._extract_toms(y, sr)
        results["toms"] = self._save_stem(toms, sr, output_dir / "toms.wav")

        # Ride/Crash (2000-10000Hz, hihat除外)
        cymbals = self._bandpass_filter(y, sr, 2000, 10000)
        # RideとCrashの分離（サステインの長さで判別）
        ride, crash = self._separate_cymbals(cymbals, sr)
        results["ride"] = self._save_stem(ride, sr, output_dir / "ride.wav")
        results["crash"] = self._save_stem(crash, sr, output_dir / "crash.wav")

        for part, path in results.items():
            console.print(f"  [green]{part}.wav[/green]")

        return results

    def _bandpass_filter(
        self,
        y: np.ndarray,
        sr: int,
        low: float,
        high: float
    ) -> np.ndarray:
        """バンドパスフィルター適用"""
        nyq = sr / 2
        low_norm = low / nyq
        high_norm = min(high / nyq, 0.99)

        b, a = self.scipy.butter(4, [low_norm, high_norm], btype='band')
        if y.ndim == 2:
            return np.array([self.scipy.filtfilt(b, a, ch) for ch in y])
        return self.scipy.filtfilt(b, a, y)

    def _extract_snare(self, y: np.ndarray, sr: int) -> np.ndarray:
        """スネアの抽出（中域 + トランジェント検出）"""
        # 中域フィルター
        mid = self._bandpass_filter(y, sr, 150, 500)

        # トランジェント強調
        y_mono = np.mean(y, axis=0) if y.ndim == 2 else y
        onset_env = self.librosa.onset.onset_strength(y=y_mono, sr=sr)

        # 強いトランジェントのみ抽出
        threshold = np.percentile(onset_env, 90)
        mask = onset_env > threshold

        # マスクをオーディオ長に拡張
        hop_length = 512
        mask_expanded = np.repeat(mask, hop_length)[:y.shape[-1]]

        if y.ndim == 2:
            return mid * mask_expanded
        return mid * mask_expanded

    def _extract_toms(self, y: np.ndarray, sr: int) -> np.ndarray:
        """タムの抽出（低中域、キック除外）"""
        # 80-400Hzの帯域
        toms_band = self._bandpass_filter(y, sr, 80, 400)

        # キック帯域を減算
        kick_band = self._bandpass_filter(y, sr, 20, 80)
        toms_band = toms_band - kick_band * 0.5

        return toms_band

    def _separate_cymbals(
        self,
        cymbals: np.ndarray,
        sr: int
    ) -> tuple:
        """RideとCrashの分離（サステイン特性で判別）"""
        # シンプルな実装: 短いサステイン=Ride, 長いサステイン=Crash
        y_mono = np.mean(cymbals, axis=0) if cymbals.ndim == 2 else cymbals

        # エンベロープ追跡
        envelope = np.abs(self.scipy.hilbert(y_mono))
        envelope_smooth = self.scipy.savgol_filter(envelope, 1001, 3)

        # サステインの長さでマスク生成
        threshold = np.max(envelope_smooth) * 0.3
        sustained = envelope_smooth > threshold

        # Crashは長いサステイン部分
        crash_mask = sustained.astype(float)
        ride_mask = 1 - crash_mask

        if cymbals.ndim == 2:
            ride = cymbals * ride_mask
            crash = cymbals * crash_mask
        else:
            ride = cymbals * ride_mask
            crash = cymbals * crash_mask

        return ride, crash

    def _save_stem(
        self,
        y: np.ndarray,
        sr: int,
        path: Path
    ) -> Path:
        """ステムをWAVファイルとして保存"""
        import soundfile as sf

        # 正規化
        max_val = np.max(np.abs(y))
        if max_val > 0:
            y = y / max_val * 0.9

        if y.ndim == 2:
            y = y.T  # (channels, samples) -> (samples, channels)

        sf.write(str(path), y, sr)
        return path


def separate_two_stage(
    input_path: str,
    output_dir: Optional[str] = None,
    device: Optional[str] = None,
    open_finder: bool = True
) -> Optional[Dict[str, Path]]:
    """
    2段階分離の実行

    Args:
        input_path: 入力音声ファイル
        output_dir: 出力ディレクトリ
        device: デバイス指定
        open_finder: 完了後Finderを開く

    Returns:
        全ステムのパス辞書
    """
    # Stage 1: Demucs粗分離
    console.print(Panel.fit(
        "[bold cyan]STEM SEPARATOR PRO v2[/bold cyan]\n"
        "[dim]2-Stage Separation Architecture[/dim]",
        border_style="cyan"
    ))

    console.print("\n[bold]STAGE 1: Primary Separation (Demucs v4)[/bold]")
    stage1_output = separate_track(
        input_path=input_path,
        output_dir=output_dir,
        model=DEFAULT_MODEL,
        device=device,
        open_finder=False
    )

    if stage1_output is None:
        return None

    # 出力ディレクトリを整理
    final_output = stage1_output.parent / f"{stage1_output.name}_pro"
    stage1_dir = final_output / "stage1"
    stage2_dir = final_output / "stage2" / "drums"

    stage1_dir.mkdir(parents=True, exist_ok=True)

    # Stage1の結果を移動
    for wav_file in stage1_output.glob("*.wav"):
        shutil.move(str(wav_file), str(stage1_dir / wav_file.name))

    # 元のディレクトリを削除
    try:
        stage1_output.rmdir()
    except Exception:
        pass

    # Stage 2: ドラム精密分離
    drums_path = stage1_dir / "drums.wav"
    if drums_path.exists():
        console.print("\n[bold]STAGE 2: Drum Fine Separation[/bold]")
        drum_separator = DrumSeparator()
        drum_results = drum_separator.separate(str(drums_path), str(stage2_dir))
    else:
        console.print("[yellow]drums.wav not found, skipping Stage 2[/yellow]")
        drum_results = {}

    # 結果を集約
    all_stems = {}
    for wav_file in stage1_dir.glob("*.wav"):
        all_stems[wav_file.stem] = wav_file
    all_stems.update(drum_results)

    console.print(f"\n[bold green]2-Stage Separation Complete![/bold green]")
    console.print(f"Output: {final_output}")

    if open_finder:
        try:
            subprocess.run(["open", str(final_output)], check=False)
        except Exception:
            pass

    return all_stems


if __name__ == "__main__":
    main()
