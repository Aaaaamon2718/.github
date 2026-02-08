#!/usr/bin/env python3
"""
スクリーンショットからOCRテキストを抽出するスクリプト。

Usage:
    python scripts/ocr_extract.py input/books/{book}/screenshots/
    python scripts/ocr_extract.py input/books/{book}/screenshots/p042_01.png

依存:
    pip install pytesseract Pillow
    Tesseract OCR がインストールされていること
"""

import sys
import os
from pathlib import Path

try:
    import pytesseract
    from PIL import Image
except ImportError:
    print("Error: pytesseract と Pillow が必要です")
    print("  pip install pytesseract Pillow")
    print("  また、Tesseract OCR のインストールも必要です")
    sys.exit(1)


def extract_text(image_path: Path, lang: str = "jpn+eng") -> str:
    """画像からテキストを抽出する。"""
    image = Image.open(image_path)
    text = pytesseract.image_to_string(image, lang=lang)
    return text.strip()


def process_file(image_path: Path, output_dir: Path) -> None:
    """単一の画像ファイルを処理し、OCRテキストを保存する。"""
    print(f"Processing: {image_path.name}")
    text = extract_text(image_path)

    output_file = output_dir / f"{image_path.stem}.txt"
    output_file.write_text(text, encoding="utf-8")
    print(f"  -> {output_file}")


def process_directory(screenshots_dir: Path) -> None:
    """ディレクトリ内のすべての画像を処理する。"""
    # OCR出力先を特定（screenshots/ の兄弟ディレクトリ ocr/）
    book_dir = screenshots_dir.parent
    ocr_dir = book_dir / "ocr"
    ocr_dir.mkdir(exist_ok=True)

    image_extensions = {".png", ".jpg", ".jpeg", ".bmp", ".tiff"}
    images = sorted(
        f for f in screenshots_dir.iterdir()
        if f.suffix.lower() in image_extensions
    )

    if not images:
        print(f"画像ファイルが見つかりません: {screenshots_dir}")
        return

    print(f"{len(images)} 件の画像を処理します")
    for image_path in images:
        process_file(image_path, ocr_dir)

    print("完了")


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python scripts/ocr_extract.py <path>")
        print("  <path>: スクリーンショットのディレクトリまたは画像ファイル")
        sys.exit(1)

    target = Path(sys.argv[1])

    if target.is_file():
        ocr_dir = target.parent.parent / "ocr"
        ocr_dir.mkdir(exist_ok=True)
        process_file(target, ocr_dir)
    elif target.is_dir():
        process_directory(target)
    else:
        print(f"Error: パスが見つかりません: {target}")
        sys.exit(1)


if __name__ == "__main__":
    main()
