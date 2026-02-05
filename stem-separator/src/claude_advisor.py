#!/usr/bin/env python3
"""
Claude Advisor - AI-Powered Sound Recreation Advice
Uses Claude API to generate professional sound design guidance.
"""

import os
import json
from pathlib import Path
from typing import Dict, List, Optional, Any

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

console = Console()


class ClaudeAdvisor:
    """Generate AI-powered sound recreation advice"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self._client = None

    @property
    def client(self):
        """Lazy load Anthropic client"""
        if self._client is None:
            if not self.api_key:
                raise ValueError(
                    "ANTHROPIC_API_KEY not set. "
                    "Set environment variable or pass api_key parameter."
                )

            import anthropic
            self._client = anthropic.Anthropic(api_key=self.api_key)

        return self._client

    def generate_advice(
        self,
        analysis: Dict[str, Any],
        advice_type: str = "recreation",
        matches: Optional[List[Dict]] = None
    ) -> str:
        """
        Generate sound design advice based on analysis.

        Args:
            analysis: Audio analysis from AudioAnalyzer
            advice_type: Type of advice (recreation, mixing, arrangement)
            matches: Optional similar sounds from matcher

        Returns:
            Markdown-formatted advice
        """
        from .prompt_builder import PromptBuilder

        builder = PromptBuilder()
        prompt = builder.build(analysis, advice_type, matches)

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )

            return response.content[0].text

        except Exception as e:
            console.print(f"[red]API error: {e}[/red]")
            return self._get_offline_advice(analysis, advice_type)

    def _get_offline_advice(
        self,
        analysis: Dict[str, Any],
        advice_type: str
    ) -> str:
        """Generate template-based advice when API is unavailable"""
        instrument = self._guess_instrument(analysis)

        templates = {
            "drums": """
## Drum Sound Recreation

Based on analysis:
- **Percussive Ratio**: {percussive_ratio}
- **Spectral Centroid**: {spectral_centroid} Hz

### Recommended Logic Pro Instruments
1. **Drum Kit Designer** - Start with a kit matching your genre
2. **Ultrabeat** - For electronic/synthesized drums

### Key Parameters
- **Kick**: Low-pass filter around 100Hz, short decay
- **Snare**: 200Hz body, 5kHz crack, moderate reverb
- **Hi-hats**: High-pass filter, tight decay

### Effects Chain
1. Transient Designer - Shape attack/sustain
2. Channel EQ - Remove mud around 300Hz
3. Compressor - 4:1 ratio, fast attack
4. Bus Reverb - Small room, low mix
""",
            "bass": """
## Bass Sound Recreation

Based on analysis:
- **Key**: {key}
- **Spectral Centroid**: {spectral_centroid} Hz

### Recommended Logic Pro Instruments
1. **Alchemy** - Synth Bass presets
2. **Retro Synth** - Classic analog bass
3. **EXS24** - Sampled bass guitars

### Key Parameters
- **Oscillator**: Saw or Square wave
- **Filter**: Low-pass, cutoff 200-800Hz
- **Envelope**: Fast attack, medium decay

### Effects Chain
1. Channel EQ - Boost 80Hz, cut 200Hz mud
2. Compressor - Heavy compression (8:1)
3. Saturation - Add warmth
4. Sub Bass - Layer with sine sub if needed
""",
            "piano": """
## Piano Sound Recreation

Based on analysis:
- **Key**: {key}
- **BPM**: {bpm}
- **Spectral Centroid**: {spectral_centroid} Hz

### Recommended Logic Pro Instruments
1. **Steinway Grand** - Classic acoustic
2. **Alchemy** - Processed piano textures
3. **Vintage Electric Piano** - Rhodes/Wurlitzer

### Key Parameters
- **Velocity Sensitivity**: Adjust to match dynamics
- **Release**: Match the room character
- **Damper Pedal**: Use for sustain passages

### Effects Chain
1. Channel EQ - Shape body (200Hz) and presence (3kHz)
2. Compressor - Gentle, 2:1 ratio
3. Space Designer - Hall or room reverb
4. Stereo Spread - Subtle widening
""",
            "default": """
## Sound Recreation Guide

Based on analysis:
- **BPM**: {bpm}
- **Key**: {key}
- **Spectral Centroid**: {spectral_centroid} Hz

### General Approach
1. Identify the closest Logic Pro instrument
2. Start with an init or basic preset
3. Shape the tone with EQ
4. Add movement with modulation
5. Place in space with reverb/delay

### Effects Chain (General)
1. Channel EQ - Tone shaping
2. Compressor - Dynamic control
3. Modulation - Chorus/Phaser if needed
4. Space - Reverb/Delay to taste
"""
        }

        template = templates.get(instrument, templates["default"])

        # Format template with analysis values
        try:
            return template.format(
                bpm=analysis.get("bpm", "N/A"),
                key=analysis.get("key", "N/A"),
                spectral_centroid=analysis.get("spectral_centroid", "N/A"),
                percussive_ratio=f"{analysis.get('percussive_ratio', 0) * 100:.1f}%",
                duration=analysis.get("duration", "N/A")
            )
        except KeyError:
            return template

    def _guess_instrument(self, analysis: Dict[str, Any]) -> str:
        """Guess instrument type from analysis"""
        filename = analysis.get("file", "").lower()

        for inst in ["drums", "bass", "piano", "guitar", "vocals"]:
            if inst in filename:
                return inst

        # Use percussive ratio as hint
        perc_ratio = analysis.get("percussive_ratio", 0.5)
        if perc_ratio > 0.7:
            return "drums"
        elif perc_ratio < 0.3:
            return "piano"

        return "default"


def generate_advice_for_stems(stems_dir: Path) -> Dict[str, str]:
    """
    Generate advice for all stems in directory.

    Args:
        stems_dir: Directory containing stems and analysis JSON files

    Returns:
        Dict mapping stem name to advice
    """
    stems_path = Path(stems_dir)
    results = {}

    # Find analysis files
    analysis_files = list(stems_path.glob("*_analysis.json"))

    if not analysis_files:
        console.print("[yellow]No analysis files found. Run analysis first.[/yellow]")
        return {}

    console.print(f"\n[bold]Generating advice for {len(analysis_files)} stems...[/bold]\n")

    advisor = ClaudeAdvisor()

    for json_file in analysis_files:
        stem_name = json_file.stem.replace("_analysis", "")
        console.print(f"[cyan]{stem_name}[/cyan]")

        try:
            with open(json_file) as f:
                analysis = json.load(f)

            advice = advisor.generate_advice(analysis)
            results[stem_name] = advice

            # Save advice
            advice_path = json_file.with_name(f"{stem_name}_advice.md")
            with open(advice_path, "w") as f:
                f.write(advice)

            console.print(f"  [green]Advice saved: {advice_path.name}[/green]")

            # Display preview
            console.print(Panel(
                Markdown(advice[:500] + "..." if len(advice) > 500 else advice),
                title=f"Preview: {stem_name}",
                border_style="dim"
            ))

        except Exception as e:
            console.print(f"  [red]Error: {e}[/red]")
            results[stem_name] = f"Error: {e}"

    console.print(f"\n[green]Advice generation complete![/green]")
    return results


def main():
    """CLI entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Generate AI sound design advice")
    parser.add_argument("input", help="Audio file or analysis JSON")
    parser.add_argument("--analyze", "-a", action="store_true", help="Analyze audio first")
    parser.add_argument("--offline", action="store_true", help="Use offline templates")
    parser.add_argument("--save", "-s", action="store_true", help="Save advice to file")
    parser.add_argument("--type", "-t", default="recreation",
                       choices=["recreation", "mixing", "arrangement"])

    args = parser.parse_args()

    path = Path(args.input)

    # Load or generate analysis
    if path.suffix == ".json":
        with open(path) as f:
            analysis = json.load(f)
    elif args.analyze:
        from .audio_analyzer import AudioAnalyzer
        analyzer = AudioAnalyzer()
        analysis = analyzer.analyze(str(path))
    else:
        console.print("[red]Provide analysis JSON or use --analyze flag[/red]")
        return

    # Generate advice
    advisor = ClaudeAdvisor()

    if args.offline:
        advice = advisor._get_offline_advice(analysis, args.type)
    else:
        try:
            advice = advisor.generate_advice(analysis, args.type)
        except ValueError as e:
            console.print(f"[yellow]{e}[/yellow]")
            console.print("[dim]Falling back to offline mode...[/dim]")
            advice = advisor._get_offline_advice(analysis, args.type)

    # Display
    console.print(Panel(
        Markdown(advice),
        title="Sound Recreation Advice",
        border_style="cyan"
    ))

    # Save
    if args.save:
        output_path = path.with_suffix(".advice.md")
        with open(output_path, "w") as f:
            f.write(advice)
        console.print(f"\n[green]Saved: {output_path}[/green]")


if __name__ == "__main__":
    main()
