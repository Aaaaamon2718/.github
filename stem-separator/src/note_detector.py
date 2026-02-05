#!/usr/bin/env python3
"""
Note Detector - MIDI Conversion & Analysis
Detects notes, chords, and drum patterns from audio.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

import numpy as np
from rich.console import Console
from rich.table import Table

console = Console()

# Note names
NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

# General MIDI drum map
GM_DRUM_MAP = {
    36: 'kick',
    38: 'snare',
    40: 'snare_rim',
    42: 'hihat_closed',
    44: 'hihat_pedal',
    46: 'hihat_open',
    49: 'crash',
    51: 'ride',
    47: 'tom_low',
    48: 'tom_mid',
    50: 'tom_high',
}


class NoteDetector:
    """Detect notes and convert to MIDI"""

    def __init__(self):
        self._basic_pitch = None
        self._librosa = None
        self._pretty_midi = None

    @property
    def librosa(self):
        if self._librosa is None:
            import librosa
            self._librosa = librosa
        return self._librosa

    @property
    def pretty_midi(self):
        if self._pretty_midi is None:
            import pretty_midi
            self._pretty_midi = pretty_midi
        return self._pretty_midi

    def detect_notes(
        self,
        audio_path: str,
        instrument_type: str = "auto"
    ) -> Dict[str, Any]:
        """
        Detect notes from audio file.

        Args:
            audio_path: Path to audio file
            instrument_type: Type of instrument (vocals, drums, bass, guitar, piano, other)

        Returns:
            Dict with notes, timing, and analysis
        """
        path = Path(audio_path)
        console.print(f"[dim]Detecting notes: {path.name}[/dim]")

        # Determine instrument type from filename if auto
        if instrument_type == "auto":
            instrument_type = self._guess_instrument(path.stem)

        # Load audio
        y, sr = self.librosa.load(str(path), sr=22050)

        if instrument_type == "drums":
            return self._analyze_drums(y, sr, path)
        else:
            return self._analyze_pitched(y, sr, path, instrument_type)

    def _guess_instrument(self, filename: str) -> str:
        """Guess instrument type from filename"""
        filename_lower = filename.lower()
        for inst in ["vocals", "drums", "bass", "guitar", "piano"]:
            if inst in filename_lower:
                return inst
        return "other"

    def _analyze_pitched(
        self,
        y: np.ndarray,
        sr: int,
        path: Path,
        instrument_type: str
    ) -> Dict[str, Any]:
        """Analyze pitched instruments (bass, piano, guitar, vocals)"""
        results = {
            "file": path.name,
            "instrument": instrument_type,
            "notes": [],
            "chords": [],
        }

        # Try basic-pitch for polyphonic detection
        try:
            from basic_pitch.inference import predict
            from basic_pitch import ICASSP_2022_MODEL_PATH

            model_output, midi_data, note_events = predict(str(path))

            # Extract notes
            for note in note_events:
                results["notes"].append({
                    "pitch": int(note[2]),
                    "start": round(float(note[0]), 3),
                    "end": round(float(note[1]), 3),
                    "velocity": int(note[3] * 127),
                    "note_name": self._midi_to_note_name(int(note[2]))
                })

            console.print(f"  [green]Detected {len(results['notes'])} notes[/green]")

        except ImportError:
            console.print("  [yellow]basic-pitch not available, using pyin[/yellow]")
            results["notes"] = self._detect_with_pyin(y, sr)

        except Exception as e:
            console.print(f"  [yellow]Note detection error: {e}[/yellow]")
            results["notes"] = self._detect_with_pyin(y, sr)

        # Chord detection for piano/guitar
        if instrument_type in ["piano", "guitar", "other"]:
            results["chords"] = self._detect_chords(y, sr)

        return results

    def _detect_with_pyin(self, y: np.ndarray, sr: int) -> List[Dict]:
        """Fallback note detection using pyin"""
        f0, voiced_flag, voiced_probs = self.librosa.pyin(
            y,
            fmin=self.librosa.note_to_hz('C2'),
            fmax=self.librosa.note_to_hz('C7'),
            sr=sr
        )

        notes = []
        times = self.librosa.times_like(f0, sr=sr)

        current_note = None
        note_start = None

        for i, (freq, voiced) in enumerate(zip(f0, voiced_flag)):
            if voiced and not np.isnan(freq):
                midi_note = int(round(self.librosa.hz_to_midi(freq)))

                if current_note != midi_note:
                    if current_note is not None:
                        notes.append({
                            "pitch": current_note,
                            "start": round(note_start, 3),
                            "end": round(times[i], 3),
                            "velocity": 80,
                            "note_name": self._midi_to_note_name(current_note)
                        })
                    current_note = midi_note
                    note_start = times[i]
            else:
                if current_note is not None:
                    notes.append({
                        "pitch": current_note,
                        "start": round(note_start, 3),
                        "end": round(times[i], 3),
                        "velocity": 80,
                        "note_name": self._midi_to_note_name(current_note)
                    })
                    current_note = None

        return notes

    def _analyze_drums(
        self,
        y: np.ndarray,
        sr: int,
        path: Path
    ) -> Dict[str, Any]:
        """Analyze drum patterns"""
        results = {
            "file": path.name,
            "instrument": "drums",
            "hits": [],
            "pattern": {},
            "fills": [],
        }

        # Onset detection
        onset_env = self.librosa.onset.onset_strength(y=y, sr=sr)
        onset_frames = self.librosa.onset.onset_detect(
            onset_envelope=onset_env,
            sr=sr,
            backtrack=True
        )
        onset_times = self.librosa.frames_to_time(onset_frames, sr=sr)

        # Spectral analysis for drum classification
        for i, onset in enumerate(onset_frames):
            # Get short segment around onset
            start_sample = max(0, self.librosa.frames_to_samples(onset) - 512)
            end_sample = min(len(y), start_sample + 4096)
            segment = y[start_sample:end_sample]

            if len(segment) < 1024:
                continue

            # Simple classification based on spectral centroid
            centroid = self.librosa.feature.spectral_centroid(y=segment, sr=sr)[0]
            mean_centroid = np.mean(centroid)

            # Classify hit
            if mean_centroid < 200:
                drum_type = "kick"
                midi_note = 36
            elif mean_centroid < 2000:
                drum_type = "snare"
                midi_note = 38
            else:
                drum_type = "hihat"
                midi_note = 42

            results["hits"].append({
                "time": round(float(onset_times[i]), 3),
                "type": drum_type,
                "midi_note": midi_note,
                "velocity": 100
            })

            # Count pattern
            results["pattern"][drum_type] = results["pattern"].get(drum_type, 0) + 1

        # Detect fills (sudden increase in density)
        results["fills"] = self._detect_fills(onset_times)

        console.print(f"  [green]Detected {len(results['hits'])} drum hits[/green]")
        console.print(f"  Pattern: {results['pattern']}")

        return results

    def _detect_fills(self, onset_times: np.ndarray) -> List[Dict]:
        """Detect drum fills based on onset density changes"""
        if len(onset_times) < 10:
            return []

        fills = []
        window_size = 1.0  # seconds

        # Calculate onset density over time
        for i in range(len(onset_times) - 5):
            window_start = onset_times[i]
            window_end = window_start + window_size

            # Count onsets in window
            count = np.sum((onset_times >= window_start) & (onset_times < window_end))

            # Count in previous window
            prev_start = window_start - window_size
            prev_count = np.sum((onset_times >= prev_start) & (onset_times < window_start))

            # Detect significant increase (fill)
            if prev_count > 0 and count > prev_count * 1.5 and count > 8:
                fills.append({
                    "time": round(float(window_start), 2),
                    "density": int(count),
                    "type": "buildup" if count > 12 else "transition"
                })

        return fills

    def _detect_chords(self, y: np.ndarray, sr: int) -> List[Dict]:
        """Detect chord progression"""
        chroma = self.librosa.feature.chroma_cqt(y=y, sr=sr)
        times = self.librosa.times_like(chroma, sr=sr)

        # Chord templates
        chord_templates = {
            'maj': [1, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0],
            'min': [1, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 0],
            '7': [1, 0, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0],
            'min7': [1, 0, 0, 1, 0, 0, 0, 1, 0, 0, 1, 0],
            'maj7': [1, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 1],
        }

        chords = []
        hop = 20  # frames

        for i in range(0, chroma.shape[1] - hop, hop):
            segment = np.mean(chroma[:, i:i+hop], axis=1)

            best_chord = None
            best_score = -1

            for root in range(12):
                rotated = np.roll(segment, -root)

                for chord_type, template in chord_templates.items():
                    score = np.dot(rotated, template) / (np.linalg.norm(rotated) + 1e-6)

                    if score > best_score:
                        best_score = score
                        best_chord = f"{NOTE_NAMES[root]}{chord_type}"

            if best_chord and best_score > 0.5:
                start_time = times[i]
                if not chords or chords[-1]["chord"] != best_chord:
                    chords.append({
                        "chord": best_chord,
                        "start": round(float(start_time), 2),
                        "confidence": round(float(best_score), 2)
                    })

        return chords

    def _midi_to_note_name(self, midi_note: int) -> str:
        """Convert MIDI note number to note name"""
        octave = (midi_note // 12) - 1
        note = NOTE_NAMES[midi_note % 12]
        return f"{note}{octave}"

    def to_midi(
        self,
        notes_data: Dict[str, Any],
        output_path: str,
        bpm: int = 120
    ) -> Path:
        """
        Convert detected notes to MIDI file.

        Args:
            notes_data: Output from detect_notes()
            output_path: Path for output MIDI file
            bpm: Tempo in BPM

        Returns:
            Path to created MIDI file
        """
        midi = self.pretty_midi.PrettyMIDI(initial_tempo=bpm)

        instrument_type = notes_data.get("instrument", "other")

        if instrument_type == "drums":
            # Drum track
            drum_track = self.pretty_midi.Instrument(program=0, is_drum=True)

            for hit in notes_data.get("hits", []):
                note = self.pretty_midi.Note(
                    velocity=hit.get("velocity", 100),
                    pitch=hit.get("midi_note", 36),
                    start=hit["time"],
                    end=hit["time"] + 0.1
                )
                drum_track.notes.append(note)

            midi.instruments.append(drum_track)

        else:
            # Melodic track
            program = {
                "piano": 0,
                "bass": 33,
                "guitar": 25,
                "vocals": 52,
                "other": 0
            }.get(instrument_type, 0)

            track = self.pretty_midi.Instrument(program=program)

            for note in notes_data.get("notes", []):
                midi_note = self.pretty_midi.Note(
                    velocity=note.get("velocity", 80),
                    pitch=note["pitch"],
                    start=note["start"],
                    end=note["end"]
                )
                track.notes.append(midi_note)

            midi.instruments.append(track)

        # Save
        output_path = Path(output_path)
        midi.write(str(output_path))

        console.print(f"  [green]MIDI saved: {output_path.name}[/green]")
        return output_path


def process_all_stems(stems_dir: Path) -> Dict[str, Any]:
    """
    Process all stems in directory.

    Args:
        stems_dir: Directory containing stem WAV files

    Returns:
        Dict with analysis results for each stem
    """
    stems_path = Path(stems_dir)
    wav_files = sorted(stems_path.glob("*.wav"))

    if not wav_files:
        console.print(f"[yellow]No WAV files found in {stems_path}[/yellow]")
        return {}

    console.print(f"\n[bold]Processing {len(wav_files)} stems for MIDI conversion...[/bold]\n")

    detector = NoteDetector()
    results = {}

    for wav_file in wav_files:
        stem_name = wav_file.stem
        console.print(f"[cyan]{stem_name}[/cyan]")

        try:
            # Detect notes
            notes_data = detector.detect_notes(str(wav_file))
            results[stem_name] = notes_data

            # Save JSON
            json_path = wav_file.with_name(f"{stem_name}_notes.json")
            with open(json_path, "w") as f:
                json.dump(notes_data, f, indent=2)

            # Create MIDI
            midi_path = wav_file.with_suffix(".mid")
            detector.to_midi(notes_data, str(midi_path))

            console.print()

        except Exception as e:
            console.print(f"  [red]Error: {e}[/red]\n")
            results[stem_name] = {"error": str(e)}

    console.print(f"[green]MIDI conversion complete![/green]")
    return results


def main():
    """CLI entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Detect notes and convert to MIDI")
    parser.add_argument("input", help="Audio file or directory")
    parser.add_argument("--midi", "-m", action="store_true", help="Output MIDI file")
    parser.add_argument("--report", "-r", action="store_true", help="Generate analysis report")
    parser.add_argument("--all", "-a", action="store_true", help="Process all stems in directory")

    args = parser.parse_args()

    path = Path(args.input)

    if path.is_dir() or args.all:
        process_all_stems(path if path.is_dir() else path.parent)
    elif path.is_file():
        detector = NoteDetector()
        results = detector.detect_notes(str(path))

        if args.midi:
            midi_path = path.with_suffix(".mid")
            detector.to_midi(results, str(midi_path))

        if args.report:
            json_path = path.with_suffix(".json")
            with open(json_path, "w") as f:
                json.dump(results, f, indent=2)
            console.print(f"Report saved: {json_path}")
    else:
        console.print(f"[red]Not found: {path}[/red]")


if __name__ == "__main__":
    main()
