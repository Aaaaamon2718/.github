#!/usr/bin/env python3
"""
File Manager - Batch Processing & Watch Mode
"""

import os
import sys
import json
import hashlib
from pathlib import Path
from typing import List, Optional
from datetime import datetime

from rich.console import Console
from rich.table import Table
from rich.progress import Progress, TaskID

console = Console()

# Supported audio formats
SUPPORTED_FORMATS = {".mp3", ".wav", ".m4a", ".flac", ".aiff", ".ogg"}

# Cache file for tracking processed files
CACHE_FILE = Path.home() / ".stem-separator" / "processed_cache.json"


def get_file_hash(file_path: Path) -> str:
    """Calculate MD5 hash of file for deduplication"""
    hasher = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def load_cache() -> dict:
    """Load processed files cache"""
    if CACHE_FILE.exists():
        with open(CACHE_FILE) as f:
            return json.load(f)
    return {"processed": {}}


def save_cache(cache: dict):
    """Save processed files cache"""
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2)


def find_audio_files(
    directory: Path,
    recursive: bool = False
) -> List[Path]:
    """Find all audio files in directory"""
    files = []
    pattern = "**/*" if recursive else "*"

    for ext in SUPPORTED_FORMATS:
        files.extend(directory.glob(f"{pattern}{ext}"))
        files.extend(directory.glob(f"{pattern}{ext.upper()}"))

    return sorted(files, key=lambda x: x.name.lower())


def list_files(
    directory: str,
    recursive: bool = False
) -> List[Path]:
    """List audio files in directory"""
    dir_path = Path(directory).resolve()

    if not dir_path.exists():
        console.print(f"[red]Directory not found: {dir_path}[/red]")
        return []

    files = find_audio_files(dir_path, recursive)

    if not files:
        console.print(f"[yellow]No audio files found in {dir_path}[/yellow]")
        return []

    # Create table
    table = Table(title=f"Audio Files in {dir_path.name}")
    table.add_column("#", style="dim")
    table.add_column("Filename", style="cyan")
    table.add_column("Size", justify="right")
    table.add_column("Format", style="green")

    for i, f in enumerate(files, 1):
        size = f.stat().st_size
        size_str = f"{size / 1024 / 1024:.1f} MB"
        table.add_row(str(i), f.name, size_str, f.suffix.upper())

    console.print(table)
    console.print(f"\nTotal: {len(files)} files")

    return files


def batch_process(
    directory: str,
    recursive: bool = False,
    dry_run: bool = False,
    skip_processed: bool = True
) -> int:
    """
    Process all audio files in directory.

    Args:
        directory: Input directory
        recursive: Include subdirectories
        dry_run: Show what would be done without processing
        skip_processed: Skip already processed files

    Returns:
        Number of files processed
    """
    from separator import separate_track

    dir_path = Path(directory).resolve()
    files = find_audio_files(dir_path, recursive)

    if not files:
        console.print("[yellow]No audio files to process[/yellow]")
        return 0

    # Load cache for skip checking
    cache = load_cache() if skip_processed else {"processed": {}}

    # Filter already processed
    to_process = []
    for f in files:
        file_hash = get_file_hash(f)
        if file_hash in cache["processed"]:
            console.print(f"[dim]Skipping (already processed): {f.name}[/dim]")
        else:
            to_process.append((f, file_hash))

    if not to_process:
        console.print("[green]All files already processed![/green]")
        return 0

    console.print(f"\n[bold]Files to process: {len(to_process)}[/bold]\n")

    if dry_run:
        console.print("[yellow]DRY RUN - No actual processing[/yellow]")
        for f, _ in to_process:
            console.print(f"  Would process: {f.name}")
        return 0

    # Process files
    processed_count = 0

    with Progress() as progress:
        task = progress.add_task(
            "[cyan]Processing...",
            total=len(to_process)
        )

        for file_path, file_hash in to_process:
            console.print(f"\n[bold]Processing: {file_path.name}[/bold]")

            result = separate_track(
                input_path=str(file_path),
                open_finder=False
            )

            if result:
                # Update cache
                cache["processed"][file_hash] = {
                    "file": str(file_path),
                    "output": str(result),
                    "date": datetime.now().isoformat()
                }
                save_cache(cache)
                processed_count += 1

            progress.update(task, advance=1)

    console.print(f"\n[bold green]Batch complete![/bold green]")
    console.print(f"Processed: {processed_count}/{len(to_process)} files")

    return processed_count


def watch_directory(
    directory: str,
    recursive: bool = False
):
    """
    Watch directory for new files and process them automatically.

    Args:
        directory: Directory to watch
        recursive: Watch subdirectories
    """
    try:
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler
    except ImportError:
        console.print("[red]watchdog not installed. Run: pip install watchdog[/red]")
        return

    from separator import separate_track

    dir_path = Path(directory).resolve()

    if not dir_path.exists():
        console.print(f"[red]Directory not found: {dir_path}[/red]")
        return

    console.print(f"[bold cyan]Watching: {dir_path}[/bold cyan]")
    console.print("[dim]Press Ctrl+C to stop[/dim]\n")

    class AudioHandler(FileSystemEventHandler):
        def on_created(self, event):
            if event.is_directory:
                return

            file_path = Path(event.src_path)
            if file_path.suffix.lower() in SUPPORTED_FORMATS:
                console.print(f"\n[green]New file detected: {file_path.name}[/green]")

                # Wait a bit for file to be fully written
                import time
                time.sleep(1)

                separate_track(str(file_path), open_finder=True)

    handler = AudioHandler()
    observer = Observer()
    observer.schedule(handler, str(dir_path), recursive=recursive)
    observer.start()

    try:
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Stopping watch...[/yellow]")
        observer.stop()

    observer.join()


def clean_empty_dirs(base_dir: Optional[str] = None):
    """Remove empty directories from output folder"""
    if base_dir:
        dir_path = Path(base_dir).expanduser()
    else:
        dir_path = Path.home() / "Music" / "Stems"

    if not dir_path.exists():
        console.print(f"[yellow]Directory not found: {dir_path}[/yellow]")
        return

    removed = 0
    for subdir in dir_path.iterdir():
        if subdir.is_dir() and not any(subdir.iterdir()):
            subdir.rmdir()
            console.print(f"[dim]Removed empty: {subdir.name}[/dim]")
            removed += 1

    console.print(f"[green]Cleaned {removed} empty directories[/green]")


def main():
    """CLI entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Batch process audio files or watch directory"
    )
    parser.add_argument(
        "directory",
        nargs="?",
        help="Directory containing audio files"
    )
    parser.add_argument(
        "-r", "--recursive",
        action="store_true",
        help="Include subdirectories"
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Watch directory for new files"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without processing"
    )
    parser.add_argument(
        "--list-only",
        action="store_true",
        help="List files only, don't process"
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Remove empty directories"
    )
    parser.add_argument(
        "--no-skip",
        action="store_true",
        help="Don't skip already processed files"
    )

    args = parser.parse_args()

    if args.clean:
        clean_empty_dirs(args.directory)
        return

    if not args.directory:
        parser.print_help()
        return

    if args.watch:
        watch_directory(args.directory, args.recursive)
    elif args.list_only:
        list_files(args.directory, args.recursive)
    else:
        batch_process(
            args.directory,
            recursive=args.recursive,
            dry_run=args.dry_run,
            skip_processed=not args.no_skip
        )


if __name__ == "__main__":
    main()
