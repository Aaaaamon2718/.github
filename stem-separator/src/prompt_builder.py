#!/usr/bin/env python3
"""
Prompt Builder - Structured Prompt Construction for Claude
Builds optimized prompts for different analysis scenarios.
"""

from typing import Dict, List, Optional, Any


class PromptBuilder:
    """Build structured prompts for Claude AI"""

    def build(
        self,
        analysis: Dict[str, Any],
        advice_type: str = "recreation",
        matches: Optional[List[Dict]] = None
    ) -> str:
        """
        Build a prompt based on analysis and advice type.

        Args:
            analysis: Audio analysis data
            advice_type: Type of advice (recreation, mixing, arrangement, genre_conversion)
            matches: Optional similar sounds from catalog

        Returns:
            Formatted prompt string
        """
        builders = {
            "recreation": self._build_recreation_prompt,
            "mixing": self._build_mixing_prompt,
            "arrangement": self._build_arrangement_prompt,
            "genre_conversion": self._build_genre_conversion_prompt,
            "comparison": self._build_comparison_prompt,
        }

        builder = builders.get(advice_type, self._build_recreation_prompt)
        return builder(analysis, matches)

    def _format_analysis(self, analysis: Dict[str, Any]) -> str:
        """Format analysis data for prompt"""
        lines = []

        if "file" in analysis:
            lines.append(f"- File: {analysis['file']}")

        if "bpm" in analysis:
            lines.append(f"- BPM: {analysis['bpm']}")

        if "key" in analysis:
            lines.append(f"- Key: {analysis['key']}")

        if "duration" in analysis:
            lines.append(f"- Duration: {analysis['duration']}s")

        if "spectral_centroid" in analysis:
            lines.append(f"- Spectral Centroid: {analysis['spectral_centroid']} Hz")

        if "percussive_ratio" in analysis:
            perc = analysis['percussive_ratio'] * 100
            lines.append(f"- Percussive Ratio: {perc:.1f}%")

        if "rms_energy" in analysis:
            lines.append(f"- RMS Energy: {analysis['rms_energy']}")

        if "dynamic_range" in analysis:
            lines.append(f"- Dynamic Range: {analysis['dynamic_range']}")

        return "\n".join(lines)

    def _format_matches(self, matches: List[Dict]) -> str:
        """Format catalog matches for prompt"""
        if not matches:
            return "No similar sounds found in catalog."

        lines = ["Similar sounds from Logic Pro library:"]
        for i, match in enumerate(matches[:5], 1):
            sim = match.get('similarity', 0) * 100
            lines.append(f"{i}. {match['name']} ({match.get('category', 'Unknown')}) - {sim:.0f}% similar")

        return "\n".join(lines)

    def _build_recreation_prompt(
        self,
        analysis: Dict[str, Any],
        matches: Optional[List[Dict]] = None
    ) -> str:
        """Build prompt for sound recreation advice"""
        prompt = f"""You are an expert sound designer and Logic Pro specialist. Analyze the following audio characteristics and provide detailed advice on how to recreate this sound in Logic Pro.

## Audio Analysis
{self._format_analysis(analysis)}

{self._format_matches(matches) if matches else ""}

## Instructions
Please provide a comprehensive guide including:

1. **Sound Overview** - Brief description of the sound character (2-3 sentences)

2. **Recommended Instruments** - Top 3 Logic Pro instruments to use, with specific preset suggestions if applicable

3. **Synth/Instrument Parameters** - Detailed settings including:
   - Oscillator configuration
   - Filter settings (type, cutoff, resonance)
   - Envelope (ADSR) settings
   - LFO configuration if needed

4. **Effects Chain** - Recommended effects in order, with approximate settings:
   - EQ adjustments
   - Compression settings
   - Modulation effects
   - Reverb/Delay

5. **Step-by-Step Recreation** - Numbered steps to recreate the sound

6. **Pro Tips** - 2-3 professional tips for getting the sound just right

Format your response in Markdown with clear headers and bullet points. Use emoji sparingly for visual clarity. Focus on practical, actionable advice specific to Logic Pro X/11.
"""
        return prompt

    def _build_mixing_prompt(
        self,
        analysis: Dict[str, Any],
        matches: Optional[List[Dict]] = None
    ) -> str:
        """Build prompt for mixing advice"""
        prompt = f"""You are an expert mixing engineer specializing in Logic Pro. Analyze the following audio characteristics and provide professional mixing advice.

## Audio Analysis
{self._format_analysis(analysis)}

## Instructions
Please provide mixing advice including:

1. **Track Assessment** - What role does this sound play in a mix?

2. **EQ Recommendations**
   - Frequencies to cut
   - Frequencies to boost
   - Problem areas to address

3. **Dynamics Processing**
   - Compression settings
   - Transient shaping recommendations
   - Parallel processing suggestions

4. **Spatial Positioning**
   - Panning recommendations
   - Reverb/delay suggestions
   - Stereo width considerations

5. **Bus/Routing Suggestions**
   - Recommended bus sends
   - Sidechain considerations
   - Automation ideas

6. **Genre-Specific Tips** - Based on the characteristics, provide genre-appropriate mixing suggestions

Format in Markdown with practical, specific settings for Logic Pro plugins.
"""
        return prompt

    def _build_arrangement_prompt(
        self,
        analysis: Dict[str, Any],
        matches: Optional[List[Dict]] = None
    ) -> str:
        """Build prompt for arrangement suggestions"""
        prompt = f"""You are an expert music producer and arranger. Based on the following audio analysis, provide arrangement and composition suggestions.

## Audio Analysis
{self._format_analysis(analysis)}

## Instructions
Please provide arrangement advice including:

1. **Musical Context**
   - Suggested genres this sound fits
   - Potential song sections (verse, chorus, bridge)
   - Mood and energy level

2. **Complementary Elements**
   - What other instruments would work well
   - Rhythm section suggestions
   - Melodic elements to add

3. **Arrangement Structure**
   - Suggested song structure
   - Build-up and breakdown ideas
   - Transition suggestions

4. **Production Techniques**
   - Layering ideas
   - Variation suggestions
   - Automation ideas for movement

5. **Reference Tracks** - Suggest 2-3 commercially released songs with similar elements

Format in Markdown with clear sections.
"""
        return prompt

    def _build_genre_conversion_prompt(
        self,
        analysis: Dict[str, Any],
        matches: Optional[List[Dict]] = None
    ) -> str:
        """Build prompt for genre conversion advice"""
        prompt = f"""You are an expert producer who specializes in genre transformation. Analyze this sound and explain how to adapt it for different genres.

## Original Sound Analysis
{self._format_analysis(analysis)}

## Instructions
Provide genre conversion guides for:

1. **Electronic/EDM Version**
   - Tempo and rhythm adjustments
   - Sound design changes
   - Processing chain

2. **Lo-Fi/Chill Version**
   - Texture modifications
   - Effect processing
   - Vibe adjustments

3. **Hip-Hop/Trap Version**
   - Rhythm and groove changes
   - Processing for punch
   - 808 integration tips

4. **Acoustic/Organic Version**
   - Instrument substitutions
   - Natural processing approach
   - Live feel techniques

For each genre, provide specific Logic Pro settings and techniques.
"""
        return prompt

    def _build_comparison_prompt(
        self,
        analysis: Dict[str, Any],
        matches: Optional[List[Dict]] = None
    ) -> str:
        """Build prompt for comparing multiple stems"""
        prompt = f"""You are an audio analysis expert. Compare and analyze the following audio characteristics.

## Audio Analysis
{self._format_analysis(analysis)}

{self._format_matches(matches) if matches else ""}

## Instructions
Provide a comparative analysis including:

1. **Frequency Balance**
   - How do the spectral characteristics compare?
   - Which elements are dominant?

2. **Dynamic Range**
   - Compare loudness and dynamics
   - Identify any issues

3. **Tonal Character**
   - Compare harmonic content
   - Identify key differences

4. **Recommendations**
   - How to better balance these elements
   - Mixing priorities
   - Potential conflicts to address

Format as a clear comparison with actionable insights.
"""
        return prompt


def main():
    """Test prompt builder"""
    builder = PromptBuilder()

    # Sample analysis
    sample_analysis = {
        "file": "bass.wav",
        "bpm": 128,
        "key": "A minor",
        "duration": 180,
        "spectral_centroid": 450.5,
        "percussive_ratio": 0.25,
        "rms_energy": 0.15
    }

    for advice_type in ["recreation", "mixing", "arrangement"]:
        print(f"\n{'='*60}")
        print(f"Prompt Type: {advice_type}")
        print('='*60)
        prompt = builder.build(sample_analysis, advice_type)
        print(prompt[:500] + "...")


if __name__ == "__main__":
    main()
