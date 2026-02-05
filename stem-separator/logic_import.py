#!/usr/bin/env python3
"""
Logic Pro Auto-Import
Automatically import stems into Logic Pro
"""

import os
import sys
import subprocess
from pathlib import Path
from typing import Optional, List

from rich.console import Console
from rich.panel import Panel

console = Console()


def check_logic_pro() -> bool:
    """Check if Logic Pro is installed"""
    logic_paths = [
        "/Applications/Logic Pro.app",
        "/Applications/Logic Pro X.app",
    ]
    return any(Path(p).exists() for p in logic_paths)


def get_logic_app_path() -> Optional[str]:
    """Get Logic Pro application path"""
    paths = [
        "/Applications/Logic Pro.app",
        "/Applications/Logic Pro X.app",
    ]
    for p in paths:
        if Path(p).exists():
            return p
    return None


def create_applescript_import(
    stem_files: List[Path],
    project_name: str
) -> str:
    """
    Generate AppleScript to import stems into Logic Pro.

    Note: Logic Pro's AppleScript support is limited.
    This script opens Logic Pro and the Finder with stems ready to drag.
    """
    files_list = ", ".join([f'"{f}"' for f in stem_files])

    script = f'''
    -- Stem Separator: Logic Pro Import
    -- Project: {project_name}

    tell application "Finder"
        -- Open stems folder
        set stemsFolder to POSIX file "{stem_files[0].parent}" as alias
        open stemsFolder

        -- Select all stem files
        activate
        select every file of folder stemsFolder whose name extension is "wav"
    end tell

    tell application "Logic Pro"
        activate

        -- Show notification
        display notification "Stems ready to import. Drag from Finder to Logic Pro." with title "Stem Separator"
    end tell

    -- Return to Finder
    tell application "Finder"
        activate
    end tell
    '''

    return script


def run_applescript(script: str) -> bool:
    """Execute AppleScript"""
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            check=True
        )
        return True
    except subprocess.CalledProcessError as e:
        console.print(f"[red]AppleScript error: {e.stderr}[/red]")
        return False
    except FileNotFoundError:
        console.print("[red]osascript not found. Are you on macOS?[/red]")
        return False


def import_to_logic(
    stems_dir: str,
    open_logic: bool = True
) -> bool:
    """
    Import stems directory to Logic Pro.

    Args:
        stems_dir: Directory containing stem files
        open_logic: Whether to open Logic Pro

    Returns:
        True if successful
    """
    stems_path = Path(stems_dir).resolve()

    if not stems_path.exists():
        console.print(f"[red]Directory not found: {stems_path}[/red]")
        return False

    # Find WAV files
    stem_files = sorted(stems_path.glob("*.wav"))

    if not stem_files:
        console.print(f"[red]No WAV files found in {stems_path}[/red]")
        return False

    console.print(Panel.fit(
        "[bold cyan]Logic Pro Import[/bold cyan]\n"
        f"[dim]Importing {len(stem_files)} stems[/dim]",
        border_style="cyan"
    ))

    console.print(f"\nStem files:")
    for f in stem_files:
        console.print(f"  [green]{f.name}[/green]")

    # Check Logic Pro
    if not check_logic_pro():
        console.print("\n[yellow]Logic Pro not found.[/yellow]")
        console.print("Opening Finder with stems instead...")

        subprocess.run(["open", str(stems_path)], check=False)
        return True

    # Generate and run AppleScript
    project_name = stems_path.name
    script = create_applescript_import(stem_files, project_name)

    console.print("\n[dim]Running AppleScript...[/dim]")

    if run_applescript(script):
        console.print("\n[bold green]Import ready![/bold green]")
        console.print(
            "\n[cyan]Instructions:[/cyan]\n"
            "1. Logic Pro and Finder are now open\n"
            "2. Drag the selected WAV files from Finder to Logic Pro\n"
            "3. Each stem will create a new track"
        )
        return True
    else:
        # Fallback: just open Finder
        console.print("\n[yellow]AppleScript failed. Opening Finder...[/yellow]")
        subprocess.run(["open", str(stems_path)], check=False)

        if open_logic:
            logic_path = get_logic_app_path()
            if logic_path:
                subprocess.run(["open", logic_path], check=False)

        return True


def create_logic_project_template(
    stems_dir: str,
    bpm: Optional[int] = None,
    key: Optional[str] = None
) -> Optional[Path]:
    """
    Create a Logic Pro project template with stems pre-configured.

    Note: Logic Pro project files (.logicx) are actually directories
    with a specific structure. Creating them programmatically is complex
    and not officially supported.

    For now, this function creates a simple text file with project info
    that can be used as reference.
    """
    stems_path = Path(stems_dir).resolve()
    stem_files = sorted(stems_path.glob("*.wav"))

    if not stem_files:
        return None

    # Create project info file
    info_file = stems_path / "project_info.txt"

    content = f"""Logic Pro Project Info
=====================

Project: {stems_path.name}
BPM: {bpm or 'Auto-detect'}
Key: {key or 'Auto-detect'}

Stems:
"""
    for i, f in enumerate(stem_files, 1):
        content += f"  Track {i}: {f.stem}\n"

    content += """
Import Instructions:
1. Open Logic Pro
2. Create new project (or open existing)
3. Set BPM and key if known
4. Drag stems from Finder to Logic Pro
5. Each stem will create a new audio track

Tips:
- Color-code tracks by instrument type
- Group related tracks (e.g., all drums)
- Use Bus sends for shared effects
"""

    info_file.write_text(content)
    console.print(f"[dim]Created project info: {info_file}[/dim]")

    return info_file


def main():
    """CLI entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Import stems into Logic Pro"
    )
    parser.add_argument(
        "directory",
        help="Directory containing stem files"
    )
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="Don't open Logic Pro"
    )
    parser.add_argument(
        "--info-only",
        action="store_true",
        help="Create project info file only"
    )

    args = parser.parse_args()

    if args.info_only:
        result = create_logic_project_template(args.directory)
        if result:
            console.print(f"[green]Created: {result}[/green]")
    else:
        import_to_logic(
            args.directory,
            open_logic=not args.no_open
        )


if __name__ == "__main__":
    main()
