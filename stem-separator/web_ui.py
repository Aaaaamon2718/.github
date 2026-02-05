#!/usr/bin/env python3
"""
Stem Separator - Web UI
Streamlit-based interface
"""

import os
import sys
import tempfile
from pathlib import Path

import streamlit as st

# Page config
st.set_page_config(
    page_title="Stem Separator",
    page_icon="🎧",
    layout="wide"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        text-align: center;
        padding: 1rem;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .status-ok { color: #00c853; }
    .status-error { color: #ff5252; }
    .stem-card {
        padding: 1rem;
        border-radius: 8px;
        background: #1e1e1e;
        margin: 0.5rem 0;
    }
</style>
""", unsafe_allow_html=True)


def main():
    # Header
    st.markdown('<h1 class="main-header">🎧 Stem Separator</h1>', unsafe_allow_html=True)
    st.markdown(
        '<p style="text-align: center; color: gray;">AI-Powered Stem Separation & Sound Analysis</p>',
        unsafe_allow_html=True
    )

    # Sidebar
    with st.sidebar:
        st.header("Settings")

        model = st.selectbox(
            "Separation Model",
            ["htdemucs_6s (6 stems)", "htdemucs (4 stems)"],
            index=0
        )
        model_name = "htdemucs_6s" if "6 stems" in model else "htdemucs"

        device = st.selectbox(
            "Device",
            ["Auto", "MPS (Apple Silicon)", "CPU"],
            index=0
        )
        device_map = {"Auto": "auto", "MPS (Apple Silicon)": "mps", "CPU": "cpu"}
        device_name = device_map[device]

        st.divider()

        do_analyze = st.checkbox("Audio Analysis", value=True)
        do_midi = st.checkbox("MIDI Conversion", value=True)
        do_advice = st.checkbox("AI Advice", value=False)

        if do_advice:
            api_key = st.text_input(
                "Anthropic API Key",
                type="password",
                help="Required for AI advice"
            )
            if api_key:
                os.environ["ANTHROPIC_API_KEY"] = api_key

        st.divider()

        # Status
        st.header("Status")
        check_status()

    # Main content
    tab1, tab2, tab3 = st.tabs(["🎵 Separate", "📁 Batch", "📊 Results"])

    with tab1:
        st.header("Upload Audio File")

        uploaded_file = st.file_uploader(
            "Drag and drop or click to upload",
            type=["mp3", "wav", "m4a", "flac", "aiff"],
            help="Supported formats: MP3, WAV, M4A, FLAC, AIFF"
        )

        if uploaded_file:
            st.audio(uploaded_file)

            col1, col2 = st.columns(2)
            with col1:
                st.metric("File Name", uploaded_file.name)
            with col2:
                size_mb = uploaded_file.size / 1024 / 1024
                st.metric("File Size", f"{size_mb:.1f} MB")

            if st.button("🚀 Start Processing", type="primary", use_container_width=True):
                process_file(
                    uploaded_file,
                    model_name,
                    device_name,
                    do_analyze,
                    do_midi,
                    do_advice
                )

    with tab2:
        st.header("Batch Processing")

        batch_dir = st.text_input(
            "Directory Path",
            placeholder="~/Music/ToProcess",
            help="Enter path to folder containing audio files"
        )

        col1, col2 = st.columns(2)
        with col1:
            recursive = st.checkbox("Include subdirectories")
        with col2:
            watch_mode = st.checkbox("Watch mode (auto-process new files)")

        if batch_dir:
            dir_path = Path(batch_dir).expanduser()
            if dir_path.exists():
                files = list_audio_files(dir_path, recursive)
                st.success(f"Found {len(files)} audio files")

                if files and st.button("🚀 Process All", type="primary"):
                    process_batch(files, model_name, device_name)
            else:
                st.error(f"Directory not found: {dir_path}")

    with tab3:
        st.header("Processing Results")

        output_dir = Path.home() / "Music" / "Stems"
        if output_dir.exists():
            sessions = sorted(
                [d for d in output_dir.iterdir() if d.is_dir()],
                key=lambda x: x.stat().st_mtime,
                reverse=True
            )

            if sessions:
                selected = st.selectbox(
                    "Select Session",
                    sessions,
                    format_func=lambda x: x.name
                )

                if selected:
                    display_results(selected)
            else:
                st.info("No processed files yet. Upload a file to get started!")
        else:
            st.info("Output directory not created yet.")


def check_status():
    """Display system status in sidebar"""
    status_items = []

    # PyTorch
    try:
        import torch
        if torch.backends.mps.is_available():
            status_items.append(("PyTorch + MPS", True))
        else:
            status_items.append(("PyTorch (CPU)", True))
    except ImportError:
        status_items.append(("PyTorch", False))

    # Demucs
    try:
        import demucs
        status_items.append(("Demucs", True))
    except ImportError:
        status_items.append(("Demucs", False))

    # librosa
    try:
        import librosa
        status_items.append(("librosa", True))
    except ImportError:
        status_items.append(("librosa", False))

    for name, ok in status_items:
        if ok:
            st.markdown(f'<span class="status-ok">✓</span> {name}', unsafe_allow_html=True)
        else:
            st.markdown(f'<span class="status-error">✗</span> {name}', unsafe_allow_html=True)


def list_audio_files(directory: Path, recursive: bool) -> list:
    """List audio files in directory"""
    extensions = {".mp3", ".wav", ".m4a", ".flac", ".aiff"}
    files = []
    pattern = "**/*" if recursive else "*"

    for ext in extensions:
        files.extend(directory.glob(f"{pattern}{ext}"))

    return sorted(files)


def process_file(uploaded_file, model, device, do_analyze, do_midi, do_advice):
    """Process uploaded file"""
    progress = st.progress(0, text="Preparing...")

    # Save uploaded file to temp
    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(uploaded_file.name).suffix) as tmp:
        tmp.write(uploaded_file.getbuffer())
        tmp_path = tmp.name

    try:
        # Step 1: Separation
        progress.progress(10, text="Step 1/4: Separating stems...")

        from separator import separate_track
        output_dir = separate_track(
            input_path=tmp_path,
            model=model,
            device=device,
            open_finder=False
        )

        if not output_dir:
            st.error("Separation failed!")
            return

        progress.progress(50, text="Step 1/4: Separation complete!")

        # Step 2: Analysis
        if do_analyze:
            progress.progress(60, text="Step 2/4: Analyzing audio...")
            try:
                from src.audio_analyzer import analyze_stems
                analyze_stems(output_dir)
            except Exception as e:
                st.warning(f"Analysis skipped: {e}")

        progress.progress(70, text="Step 2/4: Analysis complete!")

        # Step 3: MIDI
        if do_midi:
            progress.progress(80, text="Step 3/4: Converting to MIDI...")
            try:
                from src.note_detector import process_all_stems
                process_all_stems(output_dir)
            except Exception as e:
                st.warning(f"MIDI conversion skipped: {e}")

        progress.progress(90, text="Step 3/4: MIDI complete!")

        # Step 4: AI Advice
        if do_advice:
            progress.progress(95, text="Step 4/4: Generating AI advice...")
            try:
                from src.claude_advisor import generate_advice_for_stems
                generate_advice_for_stems(output_dir)
            except Exception as e:
                st.warning(f"AI advice skipped: {e}")

        progress.progress(100, text="Complete!")

        st.success(f"Processing complete! Output: {output_dir}")
        st.balloons()

        # Display results
        display_results(output_dir)

    finally:
        # Cleanup temp file
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


def process_batch(files: list, model: str, device: str):
    """Process multiple files"""
    progress = st.progress(0)
    status = st.empty()

    from separator import separate_track

    for i, file_path in enumerate(files):
        status.text(f"Processing {i+1}/{len(files)}: {file_path.name}")
        progress.progress((i + 1) / len(files))

        separate_track(
            input_path=str(file_path),
            model=model,
            device=device,
            open_finder=False
        )

    st.success(f"Batch complete! Processed {len(files)} files.")


def display_results(output_dir: Path):
    """Display processing results"""
    st.subheader(f"Results: {output_dir.name}")

    # List files
    files = sorted(output_dir.iterdir())

    # Stems
    st.markdown("### 🎵 Stems")
    cols = st.columns(3)
    wav_files = [f for f in files if f.suffix == ".wav"]

    for i, wav_file in enumerate(wav_files):
        with cols[i % 3]:
            st.markdown(f"**{wav_file.stem}**")
            st.audio(str(wav_file))

    # MIDI files
    midi_files = [f for f in files if f.suffix in [".mid", ".midi"]]
    if midi_files:
        st.markdown("### 🎹 MIDI Files")
        for midi_file in midi_files:
            st.download_button(
                f"📥 {midi_file.name}",
                data=midi_file.read_bytes(),
                file_name=midi_file.name,
                mime="audio/midi"
            )

    # Analysis reports
    json_files = [f for f in files if f.suffix == ".json"]
    if json_files:
        st.markdown("### 📊 Analysis Reports")
        for json_file in json_files:
            with st.expander(json_file.name):
                import json
                data = json.loads(json_file.read_text())
                st.json(data)


if __name__ == "__main__":
    main()
