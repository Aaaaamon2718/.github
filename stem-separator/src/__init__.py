"""
Stem Separator - Source Modules
"""

from .audio_analyzer import AudioAnalyzer, analyze_file, analyze_stems
from .note_detector import NoteDetector, process_all_stems
from .catalog_builder import CatalogBuilder
from .matcher import SoundMatcher
from .claude_advisor import ClaudeAdvisor, generate_advice_for_stems
from .prompt_builder import PromptBuilder

__all__ = [
    "AudioAnalyzer",
    "analyze_file",
    "analyze_stems",
    "NoteDetector",
    "process_all_stems",
    "CatalogBuilder",
    "SoundMatcher",
    "ClaudeAdvisor",
    "generate_advice_for_stems",
    "PromptBuilder",
]
