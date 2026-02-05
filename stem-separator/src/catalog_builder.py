#!/usr/bin/env python3
"""
Catalog Builder - Logic Pro Sound Library Indexer
Builds and manages a searchable catalog of Logic Pro sounds.
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

from rich.console import Console
from rich.table import Table
from rich.progress import Progress

console = Console()

# Default Logic Pro paths
LOGIC_SOUND_PATHS = [
    "/Library/Application Support/Logic/Sounds",
    "/Library/Application Support/GarageBand/Sounds",
    Path.home() / "Library/Application Support/Logic/Sounds",
]

# Cache location
CACHE_DIR = Path.home() / ".stem-separator"
CATALOG_FILE = CACHE_DIR / "logic_catalog.json"


class CatalogBuilder:
    """Build and manage Logic Pro sound catalog"""

    def __init__(self, catalog_path: Optional[Path] = None):
        self.catalog_path = catalog_path or CATALOG_FILE
        self.catalog = self._load_catalog()

    def _load_catalog(self) -> Dict[str, Any]:
        """Load existing catalog from disk"""
        if self.catalog_path.exists():
            try:
                with open(self.catalog_path) as f:
                    return json.load(f)
            except Exception as e:
                console.print(f"[yellow]Warning: Could not load catalog: {e}[/yellow]")

        return {
            "version": "1.0",
            "created": datetime.now().isoformat(),
            "updated": None,
            "sounds": [],
            "categories": {},
            "stats": {}
        }

    def _save_catalog(self):
        """Save catalog to disk"""
        self.catalog_path.parent.mkdir(parents=True, exist_ok=True)
        self.catalog["updated"] = datetime.now().isoformat()

        with open(self.catalog_path, "w") as f:
            json.dump(self.catalog, f, indent=2)

        console.print(f"[dim]Catalog saved: {self.catalog_path}[/dim]")

    def scan(self, paths: Optional[List[str]] = None) -> int:
        """
        Scan Logic Pro sound directories.

        Args:
            paths: List of paths to scan (default: standard Logic paths)

        Returns:
            Number of sounds found
        """
        if paths is None:
            paths = [str(p) for p in LOGIC_SOUND_PATHS if Path(p).exists()]

        if not paths:
            console.print("[yellow]No Logic Pro sound libraries found.[/yellow]")
            console.print("Expected locations:")
            for p in LOGIC_SOUND_PATHS:
                console.print(f"  {p}")
            return 0

        console.print(f"[bold]Scanning {len(paths)} sound libraries...[/bold]\n")

        sounds = []
        categories = {}

        for base_path in paths:
            base = Path(base_path)
            console.print(f"[cyan]Scanning: {base}[/cyan]")

            # Find audio files
            audio_extensions = {".aif", ".aiff", ".wav", ".caf", ".mp3", ".m4a"}

            for audio_file in base.rglob("*"):
                if audio_file.suffix.lower() in audio_extensions:
                    # Extract category from path
                    rel_path = audio_file.relative_to(base)
                    parts = rel_path.parts

                    category = parts[0] if len(parts) > 1 else "Uncategorized"
                    subcategory = parts[1] if len(parts) > 2 else None

                    sound_entry = {
                        "name": audio_file.stem,
                        "path": str(audio_file),
                        "category": category,
                        "subcategory": subcategory,
                        "format": audio_file.suffix.lower(),
                        "size": audio_file.stat().st_size,
                    }

                    sounds.append(sound_entry)

                    # Update categories
                    if category not in categories:
                        categories[category] = {"count": 0, "subcategories": {}}
                    categories[category]["count"] += 1

                    if subcategory:
                        if subcategory not in categories[category]["subcategories"]:
                            categories[category]["subcategories"][subcategory] = 0
                        categories[category]["subcategories"][subcategory] += 1

        # Update catalog
        self.catalog["sounds"] = sounds
        self.catalog["categories"] = categories
        self.catalog["stats"] = {
            "total_sounds": len(sounds),
            "total_categories": len(categories),
            "scan_date": datetime.now().isoformat()
        }

        self._save_catalog()

        console.print(f"\n[green]Found {len(sounds)} sounds in {len(categories)} categories[/green]")

        return len(sounds)

    def analyze(self, limit: Optional[int] = None) -> int:
        """
        Analyze cataloged sounds to extract audio features.

        Args:
            limit: Maximum number of sounds to analyze

        Returns:
            Number of sounds analyzed
        """
        from .audio_analyzer import AudioAnalyzer

        sounds = self.catalog.get("sounds", [])
        if not sounds:
            console.print("[yellow]No sounds in catalog. Run 'scan' first.[/yellow]")
            return 0

        if limit:
            sounds = sounds[:limit]

        console.print(f"[bold]Analyzing {len(sounds)} sounds...[/bold]")
        console.print("[dim]This may take a while...[/dim]\n")

        analyzer = AudioAnalyzer()
        analyzed_count = 0

        with Progress() as progress:
            task = progress.add_task("[cyan]Analyzing...", total=len(sounds))

            for sound in sounds:
                if "features" in sound:
                    progress.update(task, advance=1)
                    continue

                try:
                    path = sound["path"]
                    if not Path(path).exists():
                        continue

                    features = analyzer.analyze(path)

                    # Store subset of features
                    sound["features"] = {
                        "bpm": features.get("bpm"),
                        "key": features.get("key"),
                        "spectral_centroid": features.get("spectral_centroid"),
                        "mfcc": features.get("mfcc"),
                        "percussive_ratio": features.get("percussive_ratio"),
                    }

                    analyzed_count += 1

                except Exception as e:
                    sound["features"] = {"error": str(e)}

                progress.update(task, advance=1)

                # Save periodically
                if analyzed_count % 50 == 0:
                    self._save_catalog()

        self._save_catalog()

        console.print(f"\n[green]Analyzed {analyzed_count} sounds[/green]")
        return analyzed_count

    def search(
        self,
        query: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict]:
        """
        Search catalog for sounds.

        Args:
            query: Search query (searches name)
            category: Filter by category
            limit: Maximum results

        Returns:
            List of matching sounds
        """
        sounds = self.catalog.get("sounds", [])

        results = []
        for sound in sounds:
            # Filter by category
            if category and sound.get("category", "").lower() != category.lower():
                continue

            # Filter by query
            if query:
                query_lower = query.lower()
                name_match = query_lower in sound.get("name", "").lower()
                cat_match = query_lower in sound.get("category", "").lower()
                subcat_match = query_lower in str(sound.get("subcategory", "")).lower()

                if not (name_match or cat_match or subcat_match):
                    continue

            results.append(sound)

            if len(results) >= limit:
                break

        return results

    def list_categories(self) -> List[str]:
        """List all categories"""
        return list(self.catalog.get("categories", {}).keys())

    def stats(self):
        """Display catalog statistics"""
        stats = self.catalog.get("stats", {})
        categories = self.catalog.get("categories", {})

        table = Table(title="Catalog Statistics")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Total Sounds", str(stats.get("total_sounds", 0)))
        table.add_row("Total Categories", str(stats.get("total_categories", 0)))
        table.add_row("Last Scan", stats.get("scan_date", "Never"))

        analyzed = sum(1 for s in self.catalog.get("sounds", []) if "features" in s)
        table.add_row("Analyzed", str(analyzed))

        console.print(table)

        # Category breakdown
        if categories:
            console.print("\n[bold]Categories:[/bold]")
            for cat, data in sorted(categories.items(), key=lambda x: x[1]["count"], reverse=True)[:10]:
                console.print(f"  {cat}: {data['count']} sounds")


def main():
    """CLI entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Logic Pro Sound Catalog Builder")
    parser.add_argument(
        "command",
        choices=["scan", "analyze", "search", "stats", "categories"],
        help="Command to run"
    )
    parser.add_argument("--query", "-q", help="Search query")
    parser.add_argument("--category", "-c", help="Filter by category")
    parser.add_argument("--limit", "-l", type=int, default=20, help="Limit results")
    parser.add_argument("--path", "-p", action="append", help="Additional paths to scan")

    args = parser.parse_args()

    builder = CatalogBuilder()

    if args.command == "scan":
        builder.scan(args.path)

    elif args.command == "analyze":
        builder.analyze(args.limit)

    elif args.command == "search":
        results = builder.search(args.query, args.category, args.limit)

        if results:
            table = Table(title=f"Search Results ({len(results)})")
            table.add_column("Name", style="cyan")
            table.add_column("Category")
            table.add_column("Format")

            for sound in results:
                table.add_row(
                    sound["name"],
                    sound.get("category", ""),
                    sound.get("format", "")
                )

            console.print(table)
        else:
            console.print("[yellow]No results found[/yellow]")

    elif args.command == "stats":
        builder.stats()

    elif args.command == "categories":
        categories = builder.list_categories()
        console.print("[bold]Categories:[/bold]")
        for cat in sorted(categories):
            console.print(f"  {cat}")


if __name__ == "__main__":
    main()
