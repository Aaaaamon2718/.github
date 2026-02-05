#!/usr/bin/env python3
"""
Stem Separator - Core Demucs Separation Module
Powered by Demucs v4 (Meta)
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional

import yaml
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


if __name__ == "__main__":
    main()
