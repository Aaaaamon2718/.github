#!/usr/bin/env python3
"""
Stem Separator Pro - Main CLI
Unified interface for all features
2-Stage Separation Architecture
"""

import os
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm

console = Console()

# ASCII Art Banner
BANNER = """
  [cyan]
  ╔═╗╔╦╗╔═╗╔╦╗  ╔═╗╔═╗╔═╗╔═╗╦═╗╔═╗╔╦╗╔═╗╦═╗  ╔═╗╦═╗╔═╗
  ╚═╗ ║ ║╣ ║║║  ╚═╗║╣ ╠═╝╠═╣╠╦╝╠═╣ ║ ║ ║╠╦╝  ╠═╝╠╦╝║ ║
  ╚═╝ ╩ ╚═╝╩ ╩  ╚═╝╚═╝╩  ╩ ╩╩╚═╩ ╩ ╩ ╚═╝╩╚═  ╩  ╩╚═╚═╝
  [/cyan]
  [dim]2-Stage Separation | Drum Fine Separation | Logic Pro Matching[/dim]
"""


def print_banner():
    console.print(BANNER)


@click.group()
def cli():
    """Stem Separator - AI-Powered Audio Analysis Tool"""
    pass


@cli.command()
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", help="Output directory")
@click.option("--device", "-d", default="auto",
              type=click.Choice(["auto", "mps", "cuda", "cpu"]))
@click.option("--no-drums", is_flag=True, help="Skip drum fine separation (Stage 2)")
@click.option("--no-analyze", is_flag=True, help="Skip audio analysis")
@click.option("--no-midi", is_flag=True, help="Skip MIDI conversion")
@click.option("--no-match", is_flag=True, help="Skip Logic Pro sound matching")
@click.option("--no-advice", is_flag=True, help="Skip AI advice")
def process(input_file, output, device, no_drums, no_analyze, no_midi, no_match, no_advice):
    """
    Full 5-stage processing pipeline (Pro v2)

    Stage 1: Demucs 6-stem separation
    Stage 2: Drum fine separation (kick, snare, hihat, etc.)
    Stage 3: Audio analysis + MIDI conversion
    Stage 4: Logic Pro sound matching
    Stage 5: AI advice generation
    """
    print_banner()

    input_path = Path(input_file).resolve()

    console.print(Panel.fit(
        f"[bold]STEM SEPARATOR PRO v2[/bold]\n\n"
        f"Input: [cyan]{input_path.name}[/cyan]\n"
        f"Pipeline: Stage1(Demucs)"
        f"{' -> Stage2(DrumSplit)' if not no_drums else ''}"
        f"{' -> Stage3(Analysis)' if not no_analyze else ''}"
        f"{' -> Stage4(Matching)' if not no_match else ''}"
        f"{' -> Stage5(Advice)' if not no_advice else ''}",
        title="5-Stage Processing",
        border_style="cyan"
    ))

    # Stage 1 & 2: Two-Stage Separation
    console.print("\n" + "=" * 60)
    console.print("[bold]STAGE 1 & 2: Stem Separation[/bold]")
    console.print("=" * 60)

    if no_drums:
        # Stage 1 only (basic separation)
        from separator import separate_track
        output_dir = separate_track(
            input_path=str(input_path),
            output_dir=output,
            model="htdemucs_6s",
            device=device,
            open_finder=False
        )
    else:
        # Full 2-stage separation
        from separator import separate_two_stage
        stems = separate_two_stage(
            input_path=str(input_path),
            output_dir=output,
            device=device,
            open_finder=False
        )
        if stems:
            # Get the output directory from one of the stems
            output_dir = list(stems.values())[0].parent.parent
        else:
            output_dir = None

    if not output_dir:
        console.print("[red]Separation failed. Aborting.[/red]")
        sys.exit(1)

    # Stage 3: Audio Analysis + MIDI
    if not no_analyze:
        console.print("\n" + "=" * 60)
        console.print("[bold]STAGE 3: Audio Analysis + MIDI[/bold]")
        console.print("=" * 60)

        # Analyze all stems (stage1 + stage2)
        try:
            from src.audio_analyzer import analyze_stems
            stage1_dir = output_dir / "stage1"
            if stage1_dir.exists():
                analyze_stems(stage1_dir)

            stage2_drums = output_dir / "stage2" / "drums"
            if stage2_drums.exists():
                analyze_stems(stage2_drums)
        except ImportError:
            console.print("[yellow]Audio analyzer not available[/yellow]")
        except Exception as e:
            console.print(f"[yellow]Analysis error: {e}[/yellow]")

        # MIDI conversion
        if not no_midi:
            try:
                from src.note_detector import process_all_stems
                stage1_dir = output_dir / "stage1"
                midi_dir = output_dir / "midi"
                midi_dir.mkdir(exist_ok=True)

                if stage1_dir.exists():
                    process_all_stems(stage1_dir, midi_dir)
            except ImportError:
                console.print("[yellow]Note detector not available[/yellow]")
            except Exception as e:
                console.print(f"[yellow]MIDI conversion error: {e}[/yellow]")

    # Stage 4: Logic Pro Sound Matching
    if not no_match:
        console.print("\n" + "=" * 60)
        console.print("[bold]STAGE 4: Logic Pro Sound Matching[/bold]")
        console.print("=" * 60)

        try:
            from src.matcher import SoundMatcher, DrumSoundMatcher

            # Match regular stems
            matcher = SoundMatcher()
            stage1_dir = output_dir / "stage1"

            if stage1_dir.exists():
                console.print("\n[cyan]Matching main stems...[/cyan]")
                for stem_file in stage1_dir.glob("*.wav"):
                    if stem_file.stem != "drums":  # drums handled separately
                        result = matcher.match_stem(str(stem_file), top_k=3)
                        if result["matches"]:
                            top = result["matches"][0]
                            console.print(
                                f"  {stem_file.stem}: [green]{top['name']}[/green] "
                                f"({top['similarity']*100:.0f}%)"
                            )

            # Match drum parts
            stage2_drums = output_dir / "stage2" / "drums"
            if stage2_drums.exists():
                drum_matcher = DrumSoundMatcher()
                drum_results = drum_matcher.match_all_drum_stems(str(stage2_drums))

                # Generate kit suggestion
                suggestion = drum_matcher.generate_kit_suggestion(drum_results)
                if suggestion["recommended_kit"]:
                    console.print(
                        f"\n[bold]Recommended Kit:[/bold] {suggestion['recommended_kit']}"
                    )

        except ImportError:
            console.print("[yellow]Matcher not available[/yellow]")
        except Exception as e:
            console.print(f"[yellow]Matching error: {e}[/yellow]")

    # Stage 5: AI Advice
    if not no_advice:
        console.print("\n" + "=" * 60)
        console.print("[bold]STAGE 5: AI Production Advice[/bold]")
        console.print("=" * 60)

        try:
            from src.claude_advisor import generate_advice_for_stems
            advice_dir = output_dir / "advice"
            advice_dir.mkdir(exist_ok=True)

            stage1_dir = output_dir / "stage1"
            if stage1_dir.exists():
                generate_advice_for_stems(stage1_dir, advice_dir)
        except ImportError:
            console.print("[yellow]Claude advisor not available[/yellow]")
        except Exception as e:
            console.print(f"[yellow]AI advice error: {e}[/yellow]")

    # Final summary
    console.print("\n" + "=" * 60)
    console.print("[bold green]5-STAGE PROCESSING COMPLETE![/bold green]")
    console.print("=" * 60)
    console.print(f"\nOutput: [cyan]{output_dir}[/cyan]")

    # List output structure
    def list_dir_recursive(path, prefix=""):
        items = sorted(path.iterdir())
        for item in items:
            if item.is_dir():
                console.print(f"{prefix}[cyan]{item.name}/[/cyan]")
                list_dir_recursive(item, prefix + "  ")
            else:
                size = item.stat().st_size
                size_str = f"{size / 1024:.0f}KB" if size < 1024*1024 else f"{size/1024/1024:.1f}MB"
                console.print(f"{prefix}{item.name} [dim]({size_str})[/dim]")

    console.print("\n[bold]Output Structure:[/bold]")
    list_dir_recursive(output_dir)

    # Open Finder
    try:
        import subprocess
        subprocess.run(["open", str(output_dir)], check=False)
    except Exception:
        pass


@cli.command()
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", help="Output directory")
@click.option("--model", "-m", default="htdemucs_6s")
@click.option("--device", "-d", default="auto")
def separate(input_file, output, model, device):
    """Separate audio into stems only"""
    print_banner()

    from separator import separate_track
    separate_track(
        input_path=input_file,
        output_dir=output,
        model=model,
        device=device
    )


@cli.command()
@click.argument("directory", type=click.Path(exists=True))
@click.option("--output", "-o", help="Output directory")
def analyze(directory, output):
    """Analyze stems in directory"""
    print_banner()

    try:
        from src.audio_analyzer import analyze_stems
        analyze_stems(Path(directory))
    except ImportError as e:
        console.print(f"[red]Import error: {e}[/red]")
    except Exception as e:
        console.print(f"[red]Analysis error: {e}[/red]")


@cli.command()
@click.argument("directory", type=click.Path(exists=True))
def midi(directory):
    """Convert stems to MIDI"""
    print_banner()

    try:
        from src.note_detector import process_all_stems
        process_all_stems(Path(directory))
    except ImportError as e:
        console.print(f"[red]Import error: {e}[/red]")
    except Exception as e:
        console.print(f"[red]MIDI conversion error: {e}[/red]")


@cli.command()
def status():
    """Check system status and dependencies"""
    print_banner()

    table = Table(title="System Status")
    table.add_column("Component", style="cyan")
    table.add_column("Status")
    table.add_column("Details", style="dim")

    # Check Python
    table.add_row(
        "Python",
        "[green]OK[/green]",
        f"v{sys.version.split()[0]}"
    )

    # Check PyTorch
    try:
        import torch
        device_info = []
        if torch.backends.mps.is_available():
            device_info.append("MPS")
        if torch.cuda.is_available():
            device_info.append("CUDA")
        if not device_info:
            device_info.append("CPU")

        table.add_row(
            "PyTorch",
            "[green]OK[/green]",
            f"v{torch.__version__} ({', '.join(device_info)})"
        )
    except ImportError:
        table.add_row("PyTorch", "[red]Missing[/red]", "pip install torch")

    # Check Demucs
    try:
        import demucs
        table.add_row("Demucs", "[green]OK[/green]", "Stem separation ready")
    except ImportError:
        table.add_row("Demucs", "[red]Missing[/red]", "pip install demucs")

    # Check librosa
    try:
        import librosa
        table.add_row("librosa", "[green]OK[/green]", "Audio analysis ready")
    except ImportError:
        table.add_row("librosa", "[red]Missing[/red]", "pip install librosa")

    # Check basic-pitch
    try:
        import basic_pitch
        table.add_row("basic-pitch", "[green]OK[/green]", "Note detection ready")
    except ImportError:
        table.add_row("basic-pitch", "[yellow]Missing[/yellow]", "pip install basic-pitch")

    # Check anthropic
    try:
        import anthropic
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if api_key:
            table.add_row("Claude API", "[green]OK[/green]", "API key configured")
        else:
            table.add_row("Claude API", "[yellow]No key[/yellow]", "Set ANTHROPIC_API_KEY")
    except ImportError:
        table.add_row("Claude API", "[yellow]Missing[/yellow]", "pip install anthropic")

    # Check ffmpeg
    import shutil
    if shutil.which("ffmpeg"):
        table.add_row("ffmpeg", "[green]OK[/green]", "Audio codec support")
    else:
        table.add_row("ffmpeg", "[red]Missing[/red]", "brew install ffmpeg")

    console.print(table)

    # Output directory
    output_dir = Path.home() / "Music" / "Stems"
    if output_dir.exists():
        stems_count = len(list(output_dir.iterdir()))
        console.print(f"\nOutput directory: [cyan]{output_dir}[/cyan] ({stems_count} items)")
    else:
        console.print(f"\nOutput directory: [yellow]Not created yet[/yellow]")


@cli.command()
def interactive():
    """Interactive mode with prompts"""
    print_banner()

    console.print("[bold]Interactive Mode[/bold]\n")

    # Get input file
    input_file = Prompt.ask("Enter audio file path")
    input_path = Path(input_file).expanduser().resolve()

    if not input_path.exists():
        console.print(f"[red]File not found: {input_path}[/red]")
        return

    # Options
    model = Prompt.ask(
        "Model",
        choices=["htdemucs_6s", "htdemucs"],
        default="htdemucs_6s"
    )

    do_analyze = Confirm.ask("Run audio analysis?", default=True)
    do_midi = Confirm.ask("Convert to MIDI?", default=True)
    do_advice = Confirm.ask("Generate AI advice?", default=True)

    # Confirm
    console.print("\n[bold]Summary:[/bold]")
    console.print(f"  Input: {input_path.name}")
    console.print(f"  Model: {model}")
    console.print(f"  Analysis: {'Yes' if do_analyze else 'No'}")
    console.print(f"  MIDI: {'Yes' if do_midi else 'No'}")
    console.print(f"  AI Advice: {'Yes' if do_advice else 'No'}")

    if not Confirm.ask("\nProceed?", default=True):
        console.print("[yellow]Cancelled.[/yellow]")
        return

    # Run process command
    ctx = click.Context(process)
    ctx.invoke(
        process,
        input_file=str(input_path),
        output=None,
        model=model,
        device="auto",
        no_analyze=not do_analyze,
        no_midi=not do_midi,
        no_advice=not do_advice
    )


@cli.command()
@click.argument("directory", type=click.Path(exists=True))
@click.option("-r", "--recursive", is_flag=True)
@click.option("--watch", is_flag=True, help="Watch for new files")
def batch(directory, recursive, watch):
    """Batch process multiple files"""
    print_banner()

    from file_manager import batch_process, watch_directory

    if watch:
        watch_directory(directory, recursive)
    else:
        batch_process(directory, recursive)


def main():
    """Entry point"""
    cli()


if __name__ == "__main__":
    main()
