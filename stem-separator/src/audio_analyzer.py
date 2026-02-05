#!/usr/bin/env python3
"""
Audio Analyzer - Feature Extraction Module
Extracts BPM, key, spectral features, and more from audio files.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Any

import numpy as np
from rich.console import Console
from rich.table import Table

console = Console()


class AudioAnalyzer:
    """Audio feature extraction and analysis"""

    def __init__(self, sr: int = 44100):
        self.sr = sr
        self._librosa = None

    @property
    def librosa(self):
        """Lazy load librosa"""
        if self._librosa is None:
            import librosa
            self._librosa = librosa
        return self._librosa

    def analyze(self, audio_path: str) -> Dict[str, Any]:
        """
        Analyze audio file and extract features.

        Returns dict with:
            - bpm: Tempo in beats per minute
            - key: Musical key (e.g., 'C major')
            - duration: Length in seconds
            - spectral_centroid: Brightness measure
            - spectral_rolloff: High frequency content
            - rms_energy: Overall loudness
            - zero_crossing_rate: Noisiness measure
            - mfcc: Mel-frequency cepstral coefficients
            - chroma: Pitch class distribution
        """
        path = Path(audio_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        console.print(f"[dim]Analyzing: {path.name}[/dim]")

        # Load audio
        y, sr = self.librosa.load(str(path), sr=self.sr)
        duration = len(y) / sr

        features = {
            "file": path.name,
            "duration": round(duration, 2),
            "sample_rate": sr,
        }

        # BPM detection
        tempo, beat_frames = self.librosa.beat.beat_track(y=y, sr=sr)
        features["bpm"] = round(float(tempo[0]) if hasattr(tempo, '__iter__') else float(tempo))

        # Key detection
        features["key"] = self._detect_key(y, sr)

        # Spectral features
        spectral_centroids = self.librosa.feature.spectral_centroid(y=y, sr=sr)[0]
        features["spectral_centroid"] = round(float(np.mean(spectral_centroids)), 2)

        spectral_rolloff = self.librosa.feature.spectral_rolloff(y=y, sr=sr)[0]
        features["spectral_rolloff"] = round(float(np.mean(spectral_rolloff)), 2)

        # RMS energy
        rms = self.librosa.feature.rms(y=y)[0]
        features["rms_energy"] = round(float(np.mean(rms)), 4)
        features["dynamic_range"] = round(float(np.std(rms)), 4)

        # Zero crossing rate
        zcr = self.librosa.feature.zero_crossing_rate(y)[0]
        features["zero_crossing_rate"] = round(float(np.mean(zcr)), 4)

        # MFCC (13 coefficients)
        mfccs = self.librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
        features["mfcc"] = [round(float(m), 4) for m in np.mean(mfccs, axis=1)]

        # Chroma features
        chroma = self.librosa.feature.chroma_stft(y=y, sr=sr)
        features["chroma"] = [round(float(c), 4) for c in np.mean(chroma, axis=1)]

        # Percussiveness
        features["percussive_ratio"] = self._estimate_percussiveness(y, sr)

        return features

    def _detect_key(self, y: np.ndarray, sr: int) -> str:
        """Detect musical key using chroma features"""
        chroma = self.librosa.feature.chroma_cqt(y=y, sr=sr)
        chroma_mean = np.mean(chroma, axis=1)

        # Note names
        notes = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

        # Major and minor profiles (Krumhansl-Kessler)
        major_profile = [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
        minor_profile = [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]

        major_correlations = []
        minor_correlations = []

        for i in range(12):
            rotated_chroma = np.roll(chroma_mean, -i)
            major_corr = np.corrcoef(rotated_chroma, major_profile)[0, 1]
            minor_corr = np.corrcoef(rotated_chroma, minor_profile)[0, 1]
            major_correlations.append(major_corr)
            minor_correlations.append(minor_corr)

        best_major = np.argmax(major_correlations)
        best_minor = np.argmax(minor_correlations)

        if major_correlations[best_major] > minor_correlations[best_minor]:
            return f"{notes[best_major]} major"
        else:
            return f"{notes[best_minor]} minor"

    def _estimate_percussiveness(self, y: np.ndarray, sr: int) -> float:
        """Estimate how percussive the audio is"""
        # Harmonic-percussive separation
        y_harmonic, y_percussive = self.librosa.effects.hpss(y)

        harmonic_energy = np.sum(y_harmonic ** 2)
        percussive_energy = np.sum(y_percussive ** 2)

        total = harmonic_energy + percussive_energy
        if total == 0:
            return 0.5

        return round(float(percussive_energy / total), 4)


def analyze_file(audio_path: str, save_json: bool = True) -> Dict[str, Any]:
    """
    Analyze single audio file.

    Args:
        audio_path: Path to audio file
        save_json: Save results to JSON file

    Returns:
        Analysis results dict
    """
    analyzer = AudioAnalyzer()
    results = analyzer.analyze(audio_path)

    # Display results
    table = Table(title=f"Analysis: {Path(audio_path).name}")
    table.add_column("Feature", style="cyan")
    table.add_column("Value", style="green")

    display_keys = ["bpm", "key", "duration", "spectral_centroid", "rms_energy", "percussive_ratio"]
    for key in display_keys:
        if key in results:
            value = results[key]
            if key == "duration":
                value = f"{value}s"
            elif key == "spectral_centroid":
                value = f"{value} Hz"
            table.add_row(key, str(value))

    console.print(table)

    # Save JSON
    if save_json:
        json_path = Path(audio_path).with_suffix(".json")
        with open(json_path, "w") as f:
            json.dump(results, f, indent=2)
        console.print(f"[dim]Saved: {json_path}[/dim]")

    return results


def analyze_stems(stems_dir: Path) -> Dict[str, Dict[str, Any]]:
    """
    Analyze all stems in directory.

    Args:
        stems_dir: Directory containing stem WAV files

    Returns:
        Dict mapping stem name to analysis results
    """
    stems_path = Path(stems_dir)
    if not stems_path.exists():
        raise FileNotFoundError(f"Directory not found: {stems_path}")

    wav_files = sorted(stems_path.glob("*.wav"))
    if not wav_files:
        console.print(f"[yellow]No WAV files found in {stems_path}[/yellow]")
        return {}

    console.print(f"\n[bold]Analyzing {len(wav_files)} stems...[/bold]\n")

    analyzer = AudioAnalyzer()
    results = {}

    for wav_file in wav_files:
        stem_name = wav_file.stem
        console.print(f"[cyan]{stem_name}[/cyan]")

        try:
            analysis = analyzer.analyze(str(wav_file))
            results[stem_name] = analysis

            # Save individual JSON
            json_path = wav_file.with_name(f"{stem_name}_analysis.json")
            with open(json_path, "w") as f:
                json.dump(analysis, f, indent=2)

            # Display key info
            console.print(f"  BPM: {analysis.get('bpm', 'N/A')}")
            console.print(f"  Key: {analysis.get('key', 'N/A')}")
            console.print(f"  Percussive: {analysis.get('percussive_ratio', 0) * 100:.1f}%")
            console.print()

        except Exception as e:
            console.print(f"  [red]Error: {e}[/red]\n")
            results[stem_name] = {"error": str(e)}

    # Save combined results
    combined_path = stems_path / "analysis_combined.json"
    with open(combined_path, "w") as f:
        json.dump(results, f, indent=2)

    console.print(f"[green]Analysis complete![/green]")
    console.print(f"Results saved to: {combined_path}")

    return results


def main():
    """CLI entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Analyze audio features")
    parser.add_argument("input", help="Audio file or directory")
    parser.add_argument("--no-save", action="store_true", help="Don't save JSON")

    args = parser.parse_args()

    path = Path(args.input)

    if path.is_file():
        analyze_file(str(path), save_json=not args.no_save)
    elif path.is_dir():
        analyze_stems(path)
    else:
        console.print(f"[red]Not found: {path}[/red]")


if __name__ == "__main__":
    main()
