#!/usr/bin/env python3
"""
Sound Matcher - Similarity Matching Engine
Matches stems to Logic Pro sounds based on audio features.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

import numpy as np
from rich.console import Console
from rich.table import Table

console = Console()


class SoundMatcher:
    """Match audio files to similar sounds in catalog"""

    def __init__(self, catalog_path: Optional[Path] = None):
        self.catalog_path = catalog_path or (
            Path.home() / ".stem-separator" / "logic_catalog.json"
        )
        self.catalog = self._load_catalog()

    def _load_catalog(self) -> Dict[str, Any]:
        """Load catalog from disk"""
        if self.catalog_path.exists():
            with open(self.catalog_path) as f:
                return json.load(f)
        return {"sounds": []}

    def match(
        self,
        audio_path: str,
        top_k: int = 5,
        category_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Find similar sounds in catalog.

        Args:
            audio_path: Path to audio file to match
            top_k: Number of matches to return
            category_filter: Optional category to filter by

        Returns:
            List of matches with similarity scores
        """
        from .audio_analyzer import AudioAnalyzer

        path = Path(audio_path)
        console.print(f"[dim]Matching: {path.name}[/dim]")

        # Analyze input file
        analyzer = AudioAnalyzer()
        input_features = analyzer.analyze(str(path))

        # Get catalog sounds with features
        sounds = [
            s for s in self.catalog.get("sounds", [])
            if "features" in s and "error" not in s.get("features", {})
        ]

        if category_filter:
            sounds = [s for s in sounds if s.get("category", "").lower() == category_filter.lower()]

        if not sounds:
            console.print("[yellow]No analyzed sounds in catalog. Run 'catalog analyze' first.[/yellow]")
            return []

        # Calculate similarities
        matches = []
        for sound in sounds:
            similarity = self._calculate_similarity(input_features, sound["features"])
            if similarity > 0:
                matches.append({
                    "name": sound["name"],
                    "path": sound["path"],
                    "category": sound.get("category", ""),
                    "subcategory": sound.get("subcategory", ""),
                    "similarity": round(similarity, 4),
                    "features": sound["features"]
                })

        # Sort by similarity
        matches.sort(key=lambda x: x["similarity"], reverse=True)

        return matches[:top_k]

    def _calculate_similarity(
        self,
        features_a: Dict[str, Any],
        features_b: Dict[str, Any]
    ) -> float:
        """
        Calculate similarity between two feature sets.

        Uses weighted combination of:
        - MFCC cosine similarity (primary)
        - Spectral centroid distance
        - Percussiveness similarity
        """
        scores = []
        weights = []

        # MFCC similarity (most important)
        mfcc_a = features_a.get("mfcc")
        mfcc_b = features_b.get("mfcc")

        if mfcc_a and mfcc_b:
            mfcc_sim = self._cosine_similarity(mfcc_a, mfcc_b)
            scores.append(mfcc_sim)
            weights.append(0.6)

        # Spectral centroid similarity
        sc_a = features_a.get("spectral_centroid")
        sc_b = features_b.get("spectral_centroid")

        if sc_a and sc_b:
            # Normalize difference (inverse exponential)
            sc_diff = abs(sc_a - sc_b) / max(sc_a, sc_b, 1)
            sc_sim = np.exp(-sc_diff * 2)
            scores.append(sc_sim)
            weights.append(0.2)

        # Percussiveness similarity
        perc_a = features_a.get("percussive_ratio")
        perc_b = features_b.get("percussive_ratio")

        if perc_a is not None and perc_b is not None:
            perc_diff = abs(perc_a - perc_b)
            perc_sim = 1 - perc_diff
            scores.append(perc_sim)
            weights.append(0.2)

        if not scores:
            return 0

        # Weighted average
        total_weight = sum(weights)
        weighted_score = sum(s * w for s, w in zip(scores, weights)) / total_weight

        return float(weighted_score)

    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """Calculate cosine similarity between two vectors"""
        a = np.array(a)
        b = np.array(b)

        if len(a) != len(b):
            min_len = min(len(a), len(b))
            a = a[:min_len]
            b = b[:min_len]

        dot_product = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)

        if norm_a == 0 or norm_b == 0:
            return 0

        return float(dot_product / (norm_a * norm_b))

    def match_stem(
        self,
        stem_path: str,
        top_k: int = 5
    ) -> Dict[str, Any]:
        """
        Match a stem file to Logic Pro sounds.

        Automatically determines the best category based on stem name.

        Args:
            stem_path: Path to stem WAV file
            top_k: Number of matches

        Returns:
            Dict with stem info and matches
        """
        path = Path(stem_path)
        stem_name = path.stem.lower()

        # Guess category from stem name
        category_map = {
            "drums": ["Drums", "Percussion"],
            "bass": ["Bass", "Synth Bass"],
            "piano": ["Piano", "Keyboards"],
            "guitar": ["Guitar", "Electric Guitar", "Acoustic Guitar"],
            "vocals": ["Vocals", "Voice"],
            "other": None
        }

        category = None
        for key, cats in category_map.items():
            if key in stem_name:
                category = cats[0] if cats else None
                break

        # Get matches
        matches = self.match(str(path), top_k=top_k, category_filter=category)

        return {
            "stem": path.name,
            "guessed_category": category,
            "matches": matches
        }


def match_file(audio_path: str, top_k: int = 5) -> List[Dict]:
    """Match single file to catalog"""
    matcher = SoundMatcher()
    matches = matcher.match(audio_path, top_k=top_k)

    if matches:
        table = Table(title=f"Matches for {Path(audio_path).name}")
        table.add_column("#", style="dim")
        table.add_column("Sound", style="cyan")
        table.add_column("Category")
        table.add_column("Similarity", justify="right", style="green")

        for i, match in enumerate(matches, 1):
            table.add_row(
                str(i),
                match["name"],
                match.get("category", ""),
                f"{match['similarity'] * 100:.1f}%"
            )

        console.print(table)
    else:
        console.print("[yellow]No matches found[/yellow]")

    return matches


def main():
    """CLI entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Match audio to Logic Pro sounds")
    parser.add_argument("input", help="Audio file to match")
    parser.add_argument("--top", "-k", type=int, default=5, help="Number of matches")
    parser.add_argument("--category", "-c", help="Filter by category")

    args = parser.parse_args()

    matcher = SoundMatcher()
    matches = matcher.match(args.input, top_k=args.top, category_filter=args.category)

    if matches:
        table = Table(title=f"Matches for {Path(args.input).name}")
        table.add_column("#", style="dim")
        table.add_column("Sound", style="cyan")
        table.add_column("Category")
        table.add_column("Similarity", justify="right", style="green")

        for i, match in enumerate(matches, 1):
            table.add_row(
                str(i),
                match["name"],
                match.get("category", ""),
                f"{match['similarity'] * 100:.1f}%"
            )

        console.print(table)
    else:
        console.print("[yellow]No matches found. Make sure catalog is built and analyzed.[/yellow]")


if __name__ == "__main__":
    main()
