"""メディアファイルの変換処理。

PDF, DOCX, 動画, 音声, 画像ファイルからテキストを抽出する。
各フォーマットに応じた変換処理を提供し、パイプラインの Stage 2 を担当する。
"""

import base64
import logging
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# サポートするファイル拡張子
TEXT_EXTENSIONS = {".txt", ".md", ".csv"}
PDF_EXTENSIONS = {".pdf"}
DOCX_EXTENSIONS = {".docx"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".wmv"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}

ALL_EXTENSIONS = (
    TEXT_EXTENSIONS | PDF_EXTENSIONS | DOCX_EXTENSIONS
    | VIDEO_EXTENSIONS | AUDIO_EXTENSIONS | IMAGE_EXTENSIONS
)


@dataclass
class ExtractedContent:
    """ファイルから抽出されたコンテンツ。"""

    text: str
    source_path: str
    file_type: str  # text, pdf, docx, video, audio, image
    images: list[dict] = field(default_factory=list)  # [{"path": ..., "description": ""}]
    metadata: dict = field(default_factory=dict)


def classify_file(file_path: Path) -> Optional[str]:
    """ファイルの種別を判定する。

    Returns:
        "text", "pdf", "docx", "video", "audio", "image", or None
    """
    suffix = file_path.suffix.lower()
    if suffix in TEXT_EXTENSIONS:
        return "text"
    if suffix in PDF_EXTENSIONS:
        return "pdf"
    if suffix in DOCX_EXTENSIONS:
        return "docx"
    if suffix in VIDEO_EXTENSIONS:
        return "video"
    if suffix in AUDIO_EXTENSIONS:
        return "audio"
    if suffix in IMAGE_EXTENSIONS:
        return "image"
    return None


def extract_text(file_path: Path) -> ExtractedContent:
    """テキストファイルを読み込む。"""
    content = file_path.read_text(encoding="utf-8", errors="replace")
    return ExtractedContent(
        text=content,
        source_path=str(file_path),
        file_type="text",
    )


def extract_pdf(file_path: Path, image_output_dir: Optional[Path] = None) -> ExtractedContent:
    """PDFからテキストと画像を抽出する。

    PyMuPDF (fitz) を使用。インストールされていない場合はテキストのみ返す。
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        logger.warning("PyMuPDF未インストール。pip install PyMuPDF でインストールしてください")
        return ExtractedContent(
            text="[PDF処理エラー: PyMuPDFが必要です]",
            source_path=str(file_path),
            file_type="pdf",
        )

    doc = fitz.open(str(file_path))
    text_parts: list[str] = []
    images: list[dict] = []

    for page_num, page in enumerate(doc, 1):
        # テキスト抽出
        page_text = page.get_text("text")
        if page_text.strip():
            text_parts.append(f"--- ページ {page_num} ---\n{page_text.strip()}")

        # 画像抽出
        if image_output_dir:
            image_output_dir.mkdir(parents=True, exist_ok=True)
            for img_idx, img in enumerate(page.get_images(full=True)):
                xref = img[0]
                try:
                    pix = fitz.Pixmap(doc, xref)
                    if pix.n > 4:  # CMYK → RGB変換
                        pix = fitz.Pixmap(fitz.csRGB, pix)
                    img_path = image_output_dir / f"{file_path.stem}_p{page_num}_img{img_idx}.png"
                    pix.save(str(img_path))
                    images.append({"path": str(img_path), "description": "", "page": page_num})
                except Exception as e:
                    logger.warning(f"PDF画像抽出エラー p{page_num} img{img_idx}: {e}")

    doc.close()

    return ExtractedContent(
        text="\n\n".join(text_parts),
        source_path=str(file_path),
        file_type="pdf",
        images=images,
        metadata={"page_count": len(list(doc))},
    )


def extract_docx(file_path: Path, image_output_dir: Optional[Path] = None) -> ExtractedContent:
    """Word文書からテキストと画像を抽出する。"""
    try:
        from docx import Document
        from docx.opc.constants import RELATIONSHIP_TYPE as RT
    except ImportError:
        logger.warning("python-docx未インストール。pip install python-docx でインストールしてください")
        return ExtractedContent(
            text="[DOCX処理エラー: python-docxが必要です]",
            source_path=str(file_path),
            file_type="docx",
        )

    doc = Document(str(file_path))
    text_parts: list[str] = []
    images: list[dict] = []

    for para in doc.paragraphs:
        if para.text.strip():
            # 見出しスタイルをMarkdown見出しに変換
            if para.style.name.startswith("Heading"):
                level = para.style.name.replace("Heading ", "").replace("Heading", "1")
                try:
                    level = int(level)
                except ValueError:
                    level = 1
                text_parts.append(f"{'#' * level} {para.text.strip()}")
            else:
                text_parts.append(para.text.strip())

    # 画像抽出
    if image_output_dir:
        image_output_dir.mkdir(parents=True, exist_ok=True)
        for i, rel in enumerate(doc.part.rels.values()):
            if "image" in rel.reltype:
                try:
                    img_data = rel.target_part.blob
                    ext = Path(rel.target_ref).suffix or ".png"
                    img_path = image_output_dir / f"{file_path.stem}_img{i}{ext}"
                    img_path.write_bytes(img_data)
                    images.append({"path": str(img_path), "description": ""})
                except Exception as e:
                    logger.warning(f"DOCX画像抽出エラー img{i}: {e}")

    return ExtractedContent(
        text="\n\n".join(text_parts),
        source_path=str(file_path),
        file_type="docx",
        images=images,
    )


def extract_audio_whisper(
    file_path: Path,
    model_size: str = "base",
    language: str = "ja",
) -> ExtractedContent:
    """音声ファイルをWhisperで文字起こしする。

    Args:
        file_path: 音声ファイルのパス
        model_size: Whisperモデルサイズ (tiny/base/small/medium/large)
        language: 言語コード
    """
    try:
        import whisper
    except ImportError:
        logger.warning("openai-whisper未インストール。pip install openai-whisper でインストールしてください")
        return ExtractedContent(
            text="[音声処理エラー: openai-whisperが必要です]",
            source_path=str(file_path),
            file_type="audio",
        )

    logger.info(f"Whisper文字起こし開始: {file_path.name} (model={model_size})")
    model = whisper.load_model(model_size)
    result = model.transcribe(str(file_path), language=language)

    # セグメント付きテキスト生成
    segments_text: list[str] = []
    for seg in result.get("segments", []):
        start = _format_timestamp(seg["start"])
        end = _format_timestamp(seg["end"])
        segments_text.append(f"[{start} - {end}] {seg['text'].strip()}")

    return ExtractedContent(
        text=result.get("text", ""),
        source_path=str(file_path),
        file_type="audio",
        metadata={
            "language": result.get("language", language),
            "duration_seconds": result.get("segments", [{}])[-1].get("end", 0) if result.get("segments") else 0,
            "segments": segments_text,
        },
    )


def extract_video(
    file_path: Path,
    whisper_model: str = "base",
    language: str = "ja",
) -> ExtractedContent:
    """動画から音声を抽出し、Whisperで文字起こしする。

    ffmpegがシステムにインストールされている必要がある。
    """
    if not shutil.which("ffmpeg"):
        logger.error("ffmpegがインストールされていません")
        return ExtractedContent(
            text="[動画処理エラー: ffmpegが必要です]",
            source_path=str(file_path),
            file_type="video",
        )

    # 一時ファイルに音声を抽出
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_audio = Path(tmp.name)

    try:
        logger.info(f"動画→音声抽出: {file_path.name}")
        subprocess.run(
            [
                "ffmpeg", "-i", str(file_path),
                "-vn", "-acodec", "pcm_s16le",
                "-ar", "16000", "-ac", "1",
                "-y", str(tmp_audio),
            ],
            capture_output=True,
            check=True,
        )

        # Whisper文字起こし
        result = extract_audio_whisper(tmp_audio, whisper_model, language)
        result.source_path = str(file_path)
        result.file_type = "video"
        return result

    except subprocess.CalledProcessError as e:
        logger.error(f"ffmpegエラー: {e.stderr.decode('utf-8', errors='replace')[:500]}")
        return ExtractedContent(
            text=f"[動画処理エラー: 音声抽出失敗]",
            source_path=str(file_path),
            file_type="video",
        )
    finally:
        tmp_audio.unlink(missing_ok=True)


def encode_image_base64(file_path: Path) -> str:
    """画像ファイルをBase64エンコードする（Claude Vision用）。"""
    data = file_path.read_bytes()
    return base64.standard_b64encode(data).decode("utf-8")


def get_image_media_type(file_path: Path) -> str:
    """画像ファイルのメディアタイプを返す。"""
    suffix = file_path.suffix.lower()
    media_types = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
    }
    return media_types.get(suffix, "image/png")


def process_file(
    file_path: Path,
    image_output_dir: Optional[Path] = None,
    whisper_model: str = "base",
) -> Optional[ExtractedContent]:
    """ファイル種別に応じた抽出処理を実行する。

    Args:
        file_path: 処理対象ファイル
        image_output_dir: 画像出力先（PDF/DOCX内の埋め込み画像用）
        whisper_model: Whisperモデルサイズ

    Returns:
        ExtractedContent or None（未対応フォーマット）
    """
    file_type = classify_file(file_path)
    if not file_type:
        logger.warning(f"未対応フォーマット: {file_path.suffix} ({file_path.name})")
        return None

    processors = {
        "text": lambda: extract_text(file_path),
        "pdf": lambda: extract_pdf(file_path, image_output_dir),
        "docx": lambda: extract_docx(file_path, image_output_dir),
        "video": lambda: extract_video(file_path, whisper_model),
        "audio": lambda: extract_audio_whisper(file_path, whisper_model),
        "image": lambda: ExtractedContent(
            text="",  # 画像はClaude Visionで後処理
            source_path=str(file_path),
            file_type="image",
        ),
    }

    try:
        return processors[file_type]()
    except Exception as e:
        logger.error(f"ファイル処理エラー {file_path.name}: {e}")
        return ExtractedContent(
            text=f"[処理エラー: {e}]",
            source_path=str(file_path),
            file_type=file_type,
        )


def _format_timestamp(seconds: float) -> str:
    """秒数を MM:SS 形式に変換する。"""
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"
