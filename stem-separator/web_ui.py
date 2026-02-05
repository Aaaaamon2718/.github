#!/usr/bin/env python3
"""
Stem Separator Pro - Web UI
Modern Streamlit-based interface with 5-stage pipeline support
"""

import os
import sys
import json
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any

import streamlit as st

# Page config - must be first Streamlit call
st.set_page_config(
    page_title="Stem Separator Pro",
    page_icon="🎧",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Modern Dark Theme CSS
st.markdown("""
<style>
    /* Main styling */
    .stApp {
        background: linear-gradient(180deg, #0d1117 0%, #161b22 100%);
    }

    /* Header styling */
    .main-header {
        font-size: 3rem;
        font-weight: 800;
        text-align: center;
        padding: 1.5rem 0;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 50%, #f093fb 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        letter-spacing: -1px;
    }

    .sub-header {
        text-align: center;
        color: #8b949e;
        font-size: 1.1rem;
        margin-bottom: 2rem;
    }

    /* Card styling */
    .stem-card {
        background: linear-gradient(145deg, #21262d 0%, #161b22 100%);
        border: 1px solid #30363d;
        border-radius: 12px;
        padding: 1.5rem;
        margin: 0.75rem 0;
        transition: all 0.3s ease;
    }

    .stem-card:hover {
        border-color: #58a6ff;
        transform: translateY(-2px);
        box-shadow: 0 8px 24px rgba(88, 166, 255, 0.1);
    }

    /* Status badges */
    .status-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 600;
    }

    .status-ok {
        background: rgba(35, 134, 54, 0.2);
        color: #3fb950;
        border: 1px solid #238636;
    }

    .status-warn {
        background: rgba(187, 128, 9, 0.2);
        color: #d29922;
        border: 1px solid #bb8009;
    }

    .status-error {
        background: rgba(248, 81, 73, 0.2);
        color: #f85149;
        border: 1px solid #da3633;
    }

    /* Stage indicators */
    .stage-container {
        display: flex;
        justify-content: space-between;
        padding: 1rem 0;
        margin: 1rem 0;
    }

    .stage-item {
        text-align: center;
        flex: 1;
        position: relative;
    }

    .stage-item::after {
        content: '→';
        position: absolute;
        right: -10px;
        top: 50%;
        transform: translateY(-50%);
        color: #30363d;
        font-size: 1.5rem;
    }

    .stage-item:last-child::after {
        content: '';
    }

    .stage-number {
        width: 40px;
        height: 40px;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        margin: 0 auto 0.5rem;
        font-weight: bold;
        color: white;
    }

    .stage-active {
        animation: pulse 1.5s infinite;
    }

    @keyframes pulse {
        0% { box-shadow: 0 0 0 0 rgba(102, 126, 234, 0.4); }
        70% { box-shadow: 0 0 0 15px rgba(102, 126, 234, 0); }
        100% { box-shadow: 0 0 0 0 rgba(102, 126, 234, 0); }
    }

    /* Custom file uploader */
    .upload-area {
        border: 2px dashed #30363d;
        border-radius: 16px;
        padding: 3rem;
        text-align: center;
        transition: all 0.3s ease;
        background: rgba(33, 38, 45, 0.5);
    }

    .upload-area:hover {
        border-color: #58a6ff;
        background: rgba(88, 166, 255, 0.05);
    }

    /* Metric cards */
    .metric-card {
        background: #21262d;
        border-radius: 8px;
        padding: 1rem;
        text-align: center;
    }

    .metric-value {
        font-size: 2rem;
        font-weight: bold;
        color: #58a6ff;
    }

    .metric-label {
        color: #8b949e;
        font-size: 0.9rem;
    }

    /* Button styling */
    .stButton > button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        padding: 0.75rem 2rem;
        border-radius: 8px;
        font-weight: 600;
        transition: all 0.3s ease;
    }

    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 24px rgba(102, 126, 234, 0.3);
    }

    /* Audio player styling */
    audio {
        width: 100%;
        border-radius: 8px;
    }

    /* Sidebar styling */
    .css-1d391kg {
        background: #161b22;
    }

    /* Expander styling */
    .streamlit-expanderHeader {
        background: #21262d;
        border-radius: 8px;
    }

    /* Tab styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }

    .stTabs [data-baseweb="tab"] {
        background: #21262d;
        border-radius: 8px;
        padding: 0.5rem 1rem;
    }

    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    }

    /* Divider */
    hr {
        border-color: #30363d;
    }

    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)


def main():
    """Main application entry point"""

    # Header
    st.markdown('<h1 class="main-header">Stem Separator Pro</h1>', unsafe_allow_html=True)
    st.markdown(
        '<p class="sub-header">🎵 AI-Powered 5-Stage Audio Separation & Analysis for Logic Pro</p>',
        unsafe_allow_html=True
    )

    # Pipeline visualization
    render_pipeline_stages()

    # Sidebar
    config = render_sidebar()

    # Main content tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "🎵 Process",
        "📁 Batch",
        "📊 Results",
        "🔄 GitHub Sync"
    ])

    with tab1:
        render_process_tab(config)

    with tab2:
        render_batch_tab(config)

    with tab3:
        render_results_tab()

    with tab4:
        render_github_sync_tab()


def render_pipeline_stages():
    """Render the 5-stage pipeline visualization"""
    st.markdown("""
    <div style="display: flex; justify-content: center; gap: 20px; padding: 1rem; margin-bottom: 1rem;">
        <div style="text-align: center;">
            <div style="background: linear-gradient(135deg, #667eea, #764ba2); width: 50px; height: 50px; border-radius: 50%; display: flex; align-items: center; justify-content: center; margin: 0 auto;">
                <span style="color: white; font-weight: bold;">1</span>
            </div>
            <div style="color: #8b949e; font-size: 0.8rem; margin-top: 8px;">Demucs<br/>6-Stem</div>
        </div>
        <div style="color: #30363d; font-size: 2rem; display: flex; align-items: center;">→</div>
        <div style="text-align: center;">
            <div style="background: linear-gradient(135deg, #667eea, #764ba2); width: 50px; height: 50px; border-radius: 50%; display: flex; align-items: center; justify-content: center; margin: 0 auto;">
                <span style="color: white; font-weight: bold;">2</span>
            </div>
            <div style="color: #8b949e; font-size: 0.8rem; margin-top: 8px;">Drum<br/>Split</div>
        </div>
        <div style="color: #30363d; font-size: 2rem; display: flex; align-items: center;">→</div>
        <div style="text-align: center;">
            <div style="background: linear-gradient(135deg, #667eea, #764ba2); width: 50px; height: 50px; border-radius: 50%; display: flex; align-items: center; justify-content: center; margin: 0 auto;">
                <span style="color: white; font-weight: bold;">3</span>
            </div>
            <div style="color: #8b949e; font-size: 0.8rem; margin-top: 8px;">Analysis<br/>+ MIDI</div>
        </div>
        <div style="color: #30363d; font-size: 2rem; display: flex; align-items: center;">→</div>
        <div style="text-align: center;">
            <div style="background: linear-gradient(135deg, #667eea, #764ba2); width: 50px; height: 50px; border-radius: 50%; display: flex; align-items: center; justify-content: center; margin: 0 auto;">
                <span style="color: white; font-weight: bold;">4</span>
            </div>
            <div style="color: #8b949e; font-size: 0.8rem; margin-top: 8px;">Logic Pro<br/>Match</div>
        </div>
        <div style="color: #30363d; font-size: 2rem; display: flex; align-items: center;">→</div>
        <div style="text-align: center;">
            <div style="background: linear-gradient(135deg, #667eea, #764ba2); width: 50px; height: 50px; border-radius: 50%; display: flex; align-items: center; justify-content: center; margin: 0 auto;">
                <span style="color: white; font-weight: bold;">5</span>
            </div>
            <div style="color: #8b949e; font-size: 0.8rem; margin-top: 8px;">AI<br/>Advice</div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_sidebar() -> Dict[str, Any]:
    """Render sidebar and return configuration"""
    with st.sidebar:
        st.markdown("## ⚙️ Settings")

        # Model selection
        st.markdown("### Separation Model")
        model = st.selectbox(
            "Model",
            ["htdemucs_6s (6 stems)", "htdemucs (4 stems)"],
            index=0,
            label_visibility="collapsed"
        )
        model_name = "htdemucs_6s" if "6 stems" in model else "htdemucs"

        # Device selection
        st.markdown("### Processing Device")
        device = st.selectbox(
            "Device",
            ["Auto (Recommended)", "MPS (Apple Silicon)", "CUDA (NVIDIA)", "CPU"],
            index=0,
            label_visibility="collapsed"
        )
        device_map = {
            "Auto (Recommended)": "auto",
            "MPS (Apple Silicon)": "mps",
            "CUDA (NVIDIA)": "cuda",
            "CPU": "cpu"
        }
        device_name = device_map[device]

        st.divider()

        # Pipeline options
        st.markdown("### Pipeline Options")

        col1, col2 = st.columns(2)
        with col1:
            do_drums = st.checkbox("🥁 Drum Split", value=True, help="Stage 2: Fine drum separation")
            do_analyze = st.checkbox("📊 Analysis", value=True, help="Stage 3: Audio analysis")
        with col2:
            do_midi = st.checkbox("🎹 MIDI", value=True, help="Stage 3: MIDI conversion")
            do_match = st.checkbox("🎯 Matching", value=True, help="Stage 4: Logic Pro matching")

        do_advice = st.checkbox("🤖 AI Advice", value=False, help="Stage 5: Claude AI advice")

        if do_advice:
            api_key = st.text_input(
                "Anthropic API Key",
                type="password",
                help="Required for AI advice generation"
            )
            if api_key:
                os.environ["ANTHROPIC_API_KEY"] = api_key

        st.divider()

        # GitHub Sync
        st.markdown("### GitHub Sync")
        github_sync = st.checkbox("🔄 Auto-sync to GitHub", value=False)

        if github_sync:
            github_branch = st.text_input(
                "Branch",
                value="analysis-results",
                help="Branch to push analysis results"
            )
        else:
            github_branch = None

        st.divider()

        # System Status
        st.markdown("### System Status")
        render_system_status()

        return {
            "model": model_name,
            "device": device_name,
            "do_drums": do_drums,
            "do_analyze": do_analyze,
            "do_midi": do_midi,
            "do_match": do_match,
            "do_advice": do_advice,
            "github_sync": github_sync,
            "github_branch": github_branch
        }


def render_system_status():
    """Render system status indicators"""
    status_items = []

    # Check components
    try:
        import torch
        mps_available = torch.backends.mps.is_available()
        cuda_available = torch.cuda.is_available()
        if mps_available:
            status_items.append(("PyTorch + MPS", "ok", "Apple Silicon GPU ready"))
        elif cuda_available:
            status_items.append(("PyTorch + CUDA", "ok", "NVIDIA GPU ready"))
        else:
            status_items.append(("PyTorch (CPU)", "warn", "No GPU acceleration"))
    except ImportError:
        status_items.append(("PyTorch", "error", "Not installed"))

    try:
        import demucs
        status_items.append(("Demucs", "ok", "Separation ready"))
    except ImportError:
        status_items.append(("Demucs", "error", "Not installed"))

    try:
        import librosa
        status_items.append(("librosa", "ok", "Analysis ready"))
    except ImportError:
        status_items.append(("librosa", "error", "Not installed"))

    try:
        import basic_pitch
        status_items.append(("basic-pitch", "ok", "MIDI ready"))
    except ImportError:
        status_items.append(("basic-pitch", "warn", "Optional"))

    # Render status
    for name, status, detail in status_items:
        if status == "ok":
            st.markdown(f'<span class="status-badge status-ok">✓</span> **{name}**', unsafe_allow_html=True)
        elif status == "warn":
            st.markdown(f'<span class="status-badge status-warn">!</span> **{name}**', unsafe_allow_html=True)
        else:
            st.markdown(f'<span class="status-badge status-error">✗</span> **{name}**', unsafe_allow_html=True)


def render_process_tab(config: Dict[str, Any]):
    """Render the main processing tab"""
    st.markdown("### Upload Audio File")

    # File uploader with custom styling
    uploaded_file = st.file_uploader(
        "Drag and drop or click to upload",
        type=["mp3", "wav", "m4a", "flac", "aiff", "ogg"],
        help="Supported: MP3, WAV, M4A, FLAC, AIFF, OGG (up to 500MB)"
    )

    if uploaded_file:
        # File info display
        col1, col2, col3 = st.columns(3)

        with col1:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">🎵</div>
                <div class="metric-label">{uploaded_file.name}</div>
            </div>
            """, unsafe_allow_html=True)

        with col2:
            size_mb = uploaded_file.size / 1024 / 1024
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">{size_mb:.1f} MB</div>
                <div class="metric-label">File Size</div>
            </div>
            """, unsafe_allow_html=True)

        with col3:
            ext = Path(uploaded_file.name).suffix.upper()
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">{ext}</div>
                <div class="metric-label">Format</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # Audio preview
        st.markdown("#### Preview")
        st.audio(uploaded_file)

        st.markdown("<br>", unsafe_allow_html=True)

        # Process button
        if st.button("🚀 Start 5-Stage Processing", type="primary", use_container_width=True):
            process_file_5stage(uploaded_file, config)
    else:
        # Empty state
        st.markdown("""
        <div class="upload-area">
            <div style="font-size: 4rem; margin-bottom: 1rem;">🎧</div>
            <div style="color: #8b949e; font-size: 1.2rem;">
                Drop your audio file here or click to browse
            </div>
            <div style="color: #484f58; font-size: 0.9rem; margin-top: 0.5rem;">
                Supports MP3, WAV, M4A, FLAC, AIFF
            </div>
        </div>
        """, unsafe_allow_html=True)


def process_file_5stage(uploaded_file, config: Dict[str, Any]):
    """Process file through full 5-stage pipeline"""

    # Stage status display
    stage_status = st.empty()
    progress_bar = st.progress(0)
    log_container = st.container()

    def update_stage(stage: int, text: str, progress: float):
        stage_status.markdown(f"""
        <div style="text-align: center; padding: 1rem;">
            <div style="font-size: 1.5rem; color: #58a6ff; margin-bottom: 0.5rem;">
                Stage {stage}/5
            </div>
            <div style="color: #8b949e;">{text}</div>
        </div>
        """, unsafe_allow_html=True)
        progress_bar.progress(progress)

    # Save uploaded file
    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(uploaded_file.name).suffix) as tmp:
        tmp.write(uploaded_file.getbuffer())
        tmp_path = tmp.name

    try:
        # Stage 1 & 2: Separation
        update_stage(1, "Separating stems with Demucs...", 0.1)

        if config["do_drums"]:
            # Full 2-stage separation
            try:
                from separator import separate_two_stage
                stems = separate_two_stage(
                    input_path=tmp_path,
                    device=config["device"],
                    open_finder=False
                )
                if stems:
                    output_dir = list(stems.values())[0].parent.parent
                else:
                    st.error("Separation failed!")
                    return
            except ImportError:
                with log_container:
                    st.warning("2-stage separator not available, using basic separation")
                from separator import separate_track
                output_dir = separate_track(
                    input_path=tmp_path,
                    model=config["model"],
                    device=config["device"],
                    open_finder=False
                )
        else:
            from separator import separate_track
            output_dir = separate_track(
                input_path=tmp_path,
                model=config["model"],
                device=config["device"],
                open_finder=False
            )

        if not output_dir:
            st.error("Separation failed!")
            return

        output_dir = Path(output_dir)
        update_stage(2, "Drum fine separation complete!" if config["do_drums"] else "Stem separation complete!", 0.4)

        # Stage 3: Analysis + MIDI
        if config["do_analyze"]:
            update_stage(3, "Analyzing audio features...", 0.5)
            try:
                from src.audio_analyzer import analyze_stems
                stage1_dir = output_dir / "stage1"
                if stage1_dir.exists():
                    analyze_stems(stage1_dir)
                elif output_dir.exists():
                    analyze_stems(output_dir)
                with log_container:
                    st.success("Audio analysis complete")
            except Exception as e:
                with log_container:
                    st.warning(f"Analysis skipped: {e}")

        if config["do_midi"]:
            update_stage(3, "Converting to MIDI...", 0.6)
            try:
                from src.note_detector import process_all_stems
                stage1_dir = output_dir / "stage1"
                midi_dir = output_dir / "midi"
                midi_dir.mkdir(exist_ok=True)
                if stage1_dir.exists():
                    process_all_stems(stage1_dir, midi_dir)
                elif output_dir.exists():
                    process_all_stems(output_dir, midi_dir)
                with log_container:
                    st.success("MIDI conversion complete")
            except Exception as e:
                with log_container:
                    st.warning(f"MIDI conversion skipped: {e}")

        # Stage 4: Logic Pro Matching
        if config["do_match"]:
            update_stage(4, "Matching Logic Pro sounds...", 0.75)
            try:
                from src.matcher import SoundMatcher, DrumSoundMatcher

                matcher = SoundMatcher()
                stage1_dir = output_dir / "stage1"

                if stage1_dir.exists():
                    for stem_file in stage1_dir.glob("*.wav"):
                        if stem_file.stem != "drums":
                            result = matcher.match_stem(str(stem_file), top_k=3)
                            if result.get("matches"):
                                top = result["matches"][0]
                                with log_container:
                                    st.info(f"🎯 {stem_file.stem}: **{top['name']}** ({top['similarity']*100:.0f}%)")

                with log_container:
                    st.success("Sound matching complete")
            except Exception as e:
                with log_container:
                    st.warning(f"Matching skipped: {e}")

        # Stage 5: AI Advice
        if config["do_advice"]:
            update_stage(5, "Generating AI advice with Claude...", 0.9)
            try:
                from src.claude_advisor import generate_advice_for_stems
                advice_dir = output_dir / "advice"
                advice_dir.mkdir(exist_ok=True)
                stage1_dir = output_dir / "stage1"
                if stage1_dir.exists():
                    generate_advice_for_stems(stage1_dir, advice_dir)
                with log_container:
                    st.success("AI advice generated")
            except Exception as e:
                with log_container:
                    st.warning(f"AI advice skipped: {e}")

        # GitHub Sync
        if config["github_sync"]:
            update_stage(5, "Syncing to GitHub...", 0.95)
            try:
                from src.github_sync import sync_results
                sync_results(output_dir, config.get("github_branch", "analysis-results"))
                with log_container:
                    st.success("Results synced to GitHub")
            except Exception as e:
                with log_container:
                    st.warning(f"GitHub sync skipped: {e}")

        # Complete!
        progress_bar.progress(1.0)
        stage_status.markdown("""
        <div style="text-align: center; padding: 2rem;">
            <div style="font-size: 3rem; margin-bottom: 1rem;">🎉</div>
            <div style="font-size: 1.5rem; color: #3fb950; font-weight: bold;">
                Processing Complete!
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.balloons()

        # Display results
        st.markdown("---")
        display_results_detailed(output_dir)

    finally:
        # Cleanup temp file
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


def render_batch_tab(config: Dict[str, Any]):
    """Render batch processing tab"""
    st.markdown("### Batch Processing")
    st.markdown("Process multiple files at once from a directory.")

    batch_dir = st.text_input(
        "Directory Path",
        placeholder="~/Music/ToProcess",
        help="Enter the path to a folder containing audio files"
    )

    col1, col2 = st.columns(2)
    with col1:
        recursive = st.checkbox("📁 Include subdirectories", value=False)
    with col2:
        watch_mode = st.checkbox("👀 Watch mode (auto-process new files)", value=False)

    if batch_dir:
        dir_path = Path(batch_dir).expanduser()

        if dir_path.exists():
            files = list_audio_files(dir_path, recursive)

            st.markdown(f"""
            <div class="stem-card">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <div style="font-size: 1.2rem; color: #58a6ff; font-weight: bold;">
                            {len(files)} audio files found
                        </div>
                        <div style="color: #8b949e;">
                            {dir_path}
                        </div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            if files:
                # Show file list
                with st.expander(f"View files ({len(files)})"):
                    for f in files[:20]:
                        st.markdown(f"- {f.name}")
                    if len(files) > 20:
                        st.markdown(f"*...and {len(files) - 20} more*")

                if st.button("🚀 Process All Files", type="primary", use_container_width=True):
                    process_batch_files(files, config)
        else:
            st.error(f"Directory not found: {dir_path}")


def render_results_tab():
    """Render results browser tab"""
    st.markdown("### Processing Results")

    output_dir = Path.home() / "Music" / "Stems"

    if not output_dir.exists():
        st.info("No processed files yet. Upload a file to get started!")
        return

    sessions = sorted(
        [d for d in output_dir.iterdir() if d.is_dir()],
        key=lambda x: x.stat().st_mtime,
        reverse=True
    )

    if not sessions:
        st.info("No processed files yet. Upload a file to get started!")
        return

    # Session selector
    selected = st.selectbox(
        "Select Session",
        sessions,
        format_func=lambda x: f"🎵 {x.name}"
    )

    if selected:
        display_results_detailed(selected)


def render_github_sync_tab():
    """Render GitHub sync configuration tab"""
    st.markdown("### GitHub Sync Configuration")
    st.markdown("Sync your analysis results to GitHub for later review with Claude Code.")

    st.markdown("""
    <div class="stem-card">
        <h4 style="color: #58a6ff;">Why sync to GitHub?</h4>
        <ul style="color: #8b949e;">
            <li>Access analysis results from Claude Code</li>
            <li>Track changes over time with version control</li>
            <li>Share results across devices</li>
            <li>Build a library of analyzed tracks</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("#### Configuration")

    col1, col2 = st.columns(2)

    with col1:
        repo_path = st.text_input(
            "Repository Path",
            value="~/.github",
            help="Local path to your GitHub repository"
        )

    with col2:
        branch = st.text_input(
            "Branch Name",
            value="analysis-results",
            help="Branch to push analysis results"
        )

    sync_items = st.multiselect(
        "Items to Sync",
        ["analysis/*.json", "advice/*.md", "metadata.json"],
        default=["analysis/*.json", "advice/*.md", "metadata.json"]
    )

    if st.button("🔄 Test Connection", type="secondary"):
        repo_expanded = Path(repo_path).expanduser()
        if repo_expanded.exists():
            st.success(f"Repository found at {repo_expanded}")
        else:
            st.error(f"Repository not found at {repo_expanded}")

    st.markdown("---")

    st.markdown("#### Manual Sync")

    output_dir = Path.home() / "Music" / "Stems"
    if output_dir.exists():
        sessions = sorted(
            [d for d in output_dir.iterdir() if d.is_dir()],
            key=lambda x: x.stat().st_mtime,
            reverse=True
        )[:10]

        if sessions:
            selected_sessions = st.multiselect(
                "Select sessions to sync",
                sessions,
                format_func=lambda x: x.name
            )

            if selected_sessions and st.button("🚀 Sync Selected", type="primary"):
                for session in selected_sessions:
                    try:
                        from src.github_sync import sync_results
                        sync_results(session, branch)
                        st.success(f"Synced: {session.name}")
                    except Exception as e:
                        st.error(f"Failed to sync {session.name}: {e}")


def list_audio_files(directory: Path, recursive: bool) -> list:
    """List audio files in directory"""
    extensions = {".mp3", ".wav", ".m4a", ".flac", ".aiff", ".ogg"}
    files = []
    pattern = "**/*" if recursive else "*"

    for ext in extensions:
        files.extend(directory.glob(f"{pattern}{ext}"))

    return sorted(files)


def process_batch_files(files: list, config: Dict[str, Any]):
    """Process multiple files"""
    progress = st.progress(0)
    status = st.empty()

    from separator import separate_track

    for i, file_path in enumerate(files):
        status.markdown(f"""
        <div style="text-align: center; color: #8b949e;">
            Processing {i+1}/{len(files)}: <strong>{file_path.name}</strong>
        </div>
        """, unsafe_allow_html=True)

        progress.progress((i + 1) / len(files))

        try:
            separate_track(
                input_path=str(file_path),
                model=config["model"],
                device=config["device"],
                open_finder=False
            )
        except Exception as e:
            st.warning(f"Failed to process {file_path.name}: {e}")

    st.success(f"Batch complete! Processed {len(files)} files.")
    st.balloons()


def display_results_detailed(output_dir: Path):
    """Display detailed processing results"""
    st.markdown(f"### Results: {output_dir.name}")

    # Check for stage directories
    stage1_dir = output_dir / "stage1"
    stage2_dir = output_dir / "stage2" / "drums"
    midi_dir = output_dir / "midi"
    analysis_dir = output_dir / "analysis"
    advice_dir = output_dir / "advice"

    # Stage 1 Stems
    if stage1_dir.exists():
        st.markdown("#### 🎵 Stage 1: Main Stems")
        cols = st.columns(3)
        wav_files = sorted(stage1_dir.glob("*.wav"))

        for i, wav_file in enumerate(wav_files):
            with cols[i % 3]:
                st.markdown(f"""
                <div class="stem-card">
                    <div style="font-weight: bold; color: #58a6ff; margin-bottom: 0.5rem;">
                        {wav_file.stem.upper()}
                    </div>
                </div>
                """, unsafe_allow_html=True)
                st.audio(str(wav_file))
    elif output_dir.exists():
        # Flat structure (no stages)
        wav_files = sorted(output_dir.glob("*.wav"))
        if wav_files:
            st.markdown("#### 🎵 Stems")
            cols = st.columns(3)
            for i, wav_file in enumerate(wav_files):
                with cols[i % 3]:
                    st.markdown(f"**{wav_file.stem}**")
                    st.audio(str(wav_file))

    # Stage 2 Drums
    if stage2_dir.exists():
        st.markdown("#### 🥁 Stage 2: Drum Parts")
        cols = st.columns(3)
        drum_files = sorted(stage2_dir.glob("*.wav"))

        for i, drum_file in enumerate(drum_files):
            with cols[i % 3]:
                st.markdown(f"""
                <div class="stem-card">
                    <div style="font-weight: bold; color: #f093fb; margin-bottom: 0.5rem;">
                        {drum_file.stem.upper()}
                    </div>
                </div>
                """, unsafe_allow_html=True)
                st.audio(str(drum_file))

    # MIDI Files
    if midi_dir.exists():
        midi_files = sorted(midi_dir.glob("*.mid"))
        if midi_files:
            st.markdown("#### 🎹 MIDI Files")
            cols = st.columns(4)
            for i, midi_file in enumerate(midi_files):
                with cols[i % 4]:
                    st.download_button(
                        f"📥 {midi_file.name}",
                        data=midi_file.read_bytes(),
                        file_name=midi_file.name,
                        mime="audio/midi",
                        use_container_width=True
                    )

    # Analysis Reports
    if analysis_dir.exists():
        json_files = sorted(analysis_dir.glob("*.json"))
        if json_files:
            st.markdown("#### 📊 Analysis Reports")

            # Combined report
            combined = analysis_dir / "combined.json"
            if combined.exists():
                with st.expander("📄 Combined Analysis", expanded=True):
                    data = json.loads(combined.read_text())

                    # Key metrics
                    if "bpm" in data or "key" in data:
                        col1, col2 = st.columns(2)
                        with col1:
                            if "bpm" in data:
                                st.metric("BPM", f"{data['bpm']:.0f}")
                        with col2:
                            if "key" in data:
                                st.metric("Key", data["key"])

                    st.json(data)

            # Individual reports
            for json_file in json_files:
                if json_file.name != "combined.json":
                    with st.expander(f"📄 {json_file.stem}"):
                        data = json.loads(json_file.read_text())
                        st.json(data)

    # AI Advice
    if advice_dir.exists():
        md_files = sorted(advice_dir.glob("*.md"))
        if md_files:
            st.markdown("#### 🤖 AI Production Advice")
            for md_file in md_files:
                with st.expander(f"📝 {md_file.name}", expanded=True):
                    st.markdown(md_file.read_text())

    # Download all
    st.markdown("---")
    st.markdown("#### 📦 Download All")

    if st.button("📥 Download as ZIP", use_container_width=True):
        import shutil
        import io

        # Create zip in memory
        zip_buffer = io.BytesIO()
        with shutil.make_archive(
            str(output_dir / "export"),
            'zip',
            output_dir
        ) as zip_path:
            pass

        zip_file = output_dir / "export.zip"
        if zip_file.exists():
            st.download_button(
                "⬇️ Download ZIP",
                data=zip_file.read_bytes(),
                file_name=f"{output_dir.name}.zip",
                mime="application/zip"
            )


if __name__ == "__main__":
    main()
