"""ナレッジパイプライン — 大量データを並列で高精度にknowledge/へ格納する。

使い方:
    python scripts/knowledge_pipeline.py                    # intake/raw/ を全処理
    python scripts/knowledge_pipeline.py --dry-run          # ドライラン
    python scripts/knowledge_pipeline.py --input /path/to   # 入力ディレクトリ指定
    python scripts/knowledge_pipeline.py --workers 3        # 並列度指定
    python scripts/knowledge_pipeline.py --type video       # 種別フィルタ
    python scripts/knowledge_pipeline.py --report latest    # 最新レポート表示
    python scripts/knowledge_pipeline.py --no-verify        # Pass3品質検証をスキップ
"""

import argparse
import asyncio
import json
import logging
import shutil
import sys
from datetime import datetime
from pathlib import Path

# プロジェクトルートをパスに追加
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import yaml

from src.knowledge_base.media_processor import (
    ALL_EXTENSIONS,
    VIDEO_EXTENSIONS,
    AUDIO_EXTENSIONS,
    IMAGE_EXTENSIONS,
    TEXT_EXTENSIONS,
    PDF_EXTENSIONS,
    DOCX_EXTENSIONS,
    classify_file,
    process_file,
    ExtractedContent,
)
from src.knowledge_base.content_analyzer import (
    ContentAnalyzer,
    AnalysisResult,
    generate_markdown,
    generate_entry_id,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("pipeline")


# =============================================================================
# パイプラインレポート
# =============================================================================

class PipelineReport:
    """パイプライン実行結果のレポート。"""

    def __init__(self) -> None:
        self.run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.started_at = datetime.now().isoformat()
        self.completed_at = ""
        self.input_files = 0
        self.success: list[dict] = []
        self.failed: list[dict] = []
        self.skipped_duplicate: list[dict] = []
        self.manual_review: list[dict] = []
        self.stats: dict = {}

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "input_files": self.input_files,
            "results": {
                "success": len(self.success),
                "failed": len(self.failed),
                "skipped_duplicate": len(self.skipped_duplicate),
                "manual_review": len(self.manual_review),
            },
            "files_created": self.success,
            "errors": self.failed,
            "manual_review": self.manual_review,
            "stats": self.stats,
        }

    def save(self, output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / f"report_{self.run_id}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
        return path

    def print_summary(self) -> None:
        total = len(self.success) + len(self.failed) + len(self.skipped_duplicate)
        print("\n" + "=" * 60)
        print(f"  ナレッジパイプライン実行結果  [{self.run_id}]")
        print("=" * 60)
        print(f"  入力ファイル数:   {self.input_files}")
        print(f"  成功:             {len(self.success)}")
        print(f"  失敗:             {len(self.failed)}")
        print(f"  重複スキップ:     {len(self.skipped_duplicate)}")
        print(f"  手動レビュー対象: {len(self.manual_review)}")
        print("-" * 60)

        if self.success:
            print("\n  [成功ファイル]")
            for item in self.success:
                conf = item.get("confidence", 0)
                print(f"    {item['output']}  ({item['category']}  conf={conf:.2f})")

        if self.manual_review:
            print("\n  [★手動レビュー対象]")
            for item in self.manual_review:
                print(f"    {item['output']}")
                print(f"      理由: {item['reason']}")

        if self.failed:
            print("\n  [失敗ファイル]")
            for item in self.failed:
                print(f"    {item['source']}: {item['error']}")

        print("=" * 60 + "\n")


# =============================================================================
# パイプライン本体
# =============================================================================

class KnowledgePipeline:
    """ナレッジ投入パイプライン。"""

    def __init__(
        self,
        project_root: Path,
        input_dir: Optional[Path] = None,
        workers: int = 5,
        dry_run: bool = False,
        file_type_filter: Optional[str] = None,
        verification_enabled: bool = True,
        whisper_model: str = "base",
    ) -> None:
        self.project_root = project_root
        self.knowledge_dir = project_root / "knowledge"
        self.intake_dir = project_root / "intake"
        self.input_dir = input_dir or (self.intake_dir / "raw")
        self.processing_dir = self.intake_dir / "processing"
        self.completed_dir = self.intake_dir / "completed"
        self.failed_dir = self.intake_dir / "failed"
        self.report_dir = project_root / "logs" / "pipeline"
        self.dry_run = dry_run
        self.file_type_filter = file_type_filter
        self.whisper_model = whisper_model
        self.image_tmp_dir = self.intake_dir / "tmp_images"

        # settings.yaml読み込み
        settings_path = project_root / "config" / "settings.yaml"
        self.settings: dict = {}
        if settings_path.exists():
            with open(settings_path, encoding="utf-8") as f:
                self.settings = yaml.safe_load(f) or {}

        # Claude分析エンジン
        self.analyzer = ContentAnalyzer(
            model=self.settings.get("claude", {}).get("model", "claude-sonnet-4-5-20250929"),
            max_concurrent=workers,
            verification_enabled=verification_enabled,
        )

        self.report = PipelineReport()

    async def run(self) -> PipelineReport:
        """パイプラインを実行する。"""
        logger.info(f"パイプライン開始 (input={self.input_dir}, dry_run={self.dry_run})")

        # ディレクトリ準備
        self._ensure_directories()

        # Stage 1: ファイル検出
        files = self._discover_files()
        self.report.input_files = len(files)

        if not files:
            logger.info("処理対象ファイルがありません")
            self.report.completed_at = datetime.now().isoformat()
            return self.report

        logger.info(f"検出ファイル数: {len(files)}")

        if self.dry_run:
            self._print_dry_run(files)
            self.report.completed_at = datetime.now().isoformat()
            return self.report

        # Stage 2-5: 並列処理
        tasks = [self._process_single_file(f) for f in files]
        await asyncio.gather(*tasks)

        # レポート集計
        self.report.completed_at = datetime.now().isoformat()
        self._compute_stats()

        # レポート保存・表示
        report_path = self.report.save(self.report_dir)
        logger.info(f"レポート保存: {report_path}")
        self.report.print_summary()

        # 一時ディレクトリ削除
        if self.image_tmp_dir.exists():
            shutil.rmtree(self.image_tmp_dir, ignore_errors=True)

        return self.report

    def _ensure_directories(self) -> None:
        """必要なディレクトリを作成する。"""
        for d in [self.input_dir, self.processing_dir, self.completed_dir,
                  self.failed_dir, self.report_dir, self.image_tmp_dir]:
            d.mkdir(parents=True, exist_ok=True)

    def _discover_files(self) -> list[Path]:
        """入力ディレクトリからファイルを検出する。"""
        if not self.input_dir.exists():
            logger.warning(f"入力ディレクトリが存在しません: {self.input_dir}")
            return []

        files: list[Path] = []
        for f in sorted(self.input_dir.iterdir()):
            if f.is_file() and f.suffix.lower() in ALL_EXTENSIONS:
                file_type = classify_file(f)
                if self.file_type_filter and not self._matches_filter(file_type):
                    continue
                files.append(f)

        return files

    def _matches_filter(self, file_type: Optional[str]) -> bool:
        """ファイルタイプフィルタに一致するか判定する。"""
        if not self.file_type_filter or not file_type:
            return True
        filter_map = {
            "text": ("text", "pdf", "docx"),
            "video": ("video",),
            "audio": ("audio",),
            "image": ("image",),
            "media": ("video", "audio", "image"),
        }
        allowed = filter_map.get(self.file_type_filter, (self.file_type_filter,))
        return file_type in allowed

    def _print_dry_run(self, files: list[Path]) -> None:
        """ドライラン結果を表示する。"""
        print("\n" + "=" * 60)
        print("  ドライラン — 以下のファイルが処理対象です")
        print("=" * 60)
        for f in files:
            ft = classify_file(f)
            size_kb = f.stat().st_size / 1024
            print(f"  [{ft:>6s}] {f.name:40s} ({size_kb:.1f} KB)")
        print(f"\n  合計: {len(files)} ファイル")
        print("=" * 60 + "\n")

    async def _process_single_file(self, file_path: Path) -> None:
        """1ファイルの全パイプラインを実行する。"""
        fname = file_path.name
        processing_path = self.processing_dir / fname

        try:
            # processing/ に移動（ロック）
            shutil.move(str(file_path), str(processing_path))
            logger.info(f"処理開始: {fname}")

            # Stage 2: メディア変換
            extracted = process_file(
                processing_path,
                image_output_dir=self.image_tmp_dir / file_path.stem,
                whisper_model=self.whisper_model,
            )

            if not extracted:
                raise ValueError(f"未対応フォーマット: {file_path.suffix}")

            if extracted.text.startswith("[") and "エラー" in extracted.text:
                raise RuntimeError(extracted.text)

            # Stage 3: Claude分析（3パス）
            result = await self.analyzer.analyze(extracted)

            if result.error:
                raise RuntimeError(result.error)

            # Stage 4: Markdown生成
            entry_id = generate_entry_id(result.id_prefix, self.knowledge_dir)
            source_name = self._infer_source_name(file_path)
            markdown = generate_markdown(result, entry_id, source_name)

            # Stage 5: 検証・格納
            output_subdir = self.knowledge_dir / result.knowledge_dir
            output_subdir.mkdir(parents=True, exist_ok=True)

            # ファイル名生成
            safe_title = self._sanitize_filename(result.title or file_path.stem)
            output_path = output_subdir / f"{entry_id}_{safe_title}.md"

            # 重複チェック
            if output_path.exists():
                self.report.skipped_duplicate.append({
                    "source": fname,
                    "output": str(output_path.relative_to(self.project_root)),
                    "reason": "同名ファイルが既に存在",
                })
                shutil.move(str(processing_path), str(self.completed_dir / fname))
                logger.warning(f"重複スキップ: {fname}")
                return

            # Markdown書き込み
            output_path.write_text(markdown, encoding="utf-8")

            # 完了処理
            shutil.move(str(processing_path), str(self.completed_dir / fname))

            record = {
                "source": fname,
                "output": str(output_path.relative_to(self.project_root)),
                "category": result.category,
                "sub_category": result.sub_category,
                "priority": result.priority,
                "confidence": result.confidence,
                "quality_score": result.quality_score,
                "entry_id": entry_id,
            }

            if result.needs_manual_review:
                self.report.manual_review.append({
                    **record,
                    "reason": "; ".join(result.review_reasons),
                })

            self.report.success.append(record)
            logger.info(f"完了: {fname} → {output_path.name}")

        except Exception as e:
            logger.error(f"失敗: {fname}: {e}")
            # failed/ に移動
            if processing_path.exists():
                shutil.move(str(processing_path), str(self.failed_dir / fname))
            elif file_path.exists():
                shutil.move(str(file_path), str(self.failed_dir / fname))
            self.report.failed.append({
                "source": fname,
                "error": str(e),
                "moved_to": f"intake/failed/{fname}",
            })

    def _infer_source_name(self, file_path: Path) -> str:
        """ファイル名から出典名を推定する。"""
        stem = file_path.stem
        # パターンマッチ: seminar_vol5_2024 → 牧野生保塾 Vol.5 (2024)
        import re
        match = re.match(r"(?:seminar|セミナー).*?vol\.?(\d+).*?(\d{4})", stem, re.IGNORECASE)
        if match:
            return f"牧野生保塾 Vol.{match.group(1)} ({match.group(2)})"
        return file_path.name

    def _sanitize_filename(self, name: str) -> str:
        """ファイル名として安全な文字列に変換する。"""
        import re
        # 使えない文字を除去
        sanitized = re.sub(r'[\\/:*?"<>|]', "", name)
        # 長すぎる場合は切り詰め
        if len(sanitized) > 50:
            sanitized = sanitized[:50]
        return sanitized.strip() or "untitled"

    def _compute_stats(self) -> None:
        """統計情報を集計する。"""
        by_category: dict[str, int] = {}
        by_type: dict[str, int] = {}

        for item in self.success:
            cat = item.get("category", "不明")
            by_category[cat] = by_category.get(cat, 0) + 1
            eid = item.get("entry_id", "")
            prefix = eid.split("_")[0] if "_" in eid else "OTHER"
            by_type[prefix] = by_type.get(prefix, 0) + 1

        self.report.stats = {
            "by_category": by_category,
            "by_type": by_type,
        }


# =============================================================================
# レポート表示
# =============================================================================

def show_report(report_dir: Path, which: str = "latest") -> None:
    """保存済みレポートを表示する。"""
    if not report_dir.exists():
        print("レポートディレクトリが存在しません")
        return

    reports = sorted(report_dir.glob("report_*.json"), reverse=True)
    if not reports:
        print("レポートファイルがありません")
        return

    if which == "latest":
        target = reports[0]
    else:
        target = report_dir / f"report_{which}.json"
        if not target.exists():
            print(f"レポートが見つかりません: {which}")
            print(f"利用可能: {[r.stem.replace('report_', '') for r in reports[:10]]}")
            return

    with open(target, encoding="utf-8") as f:
        data = json.load(f)

    print(json.dumps(data, ensure_ascii=False, indent=2))


# =============================================================================
# エントリーポイント
# =============================================================================

# shutil.moveのために必要な型ヒント用
from typing import Optional


def main() -> None:
    parser = argparse.ArgumentParser(
        description="牧野生保塾 ナレッジパイプライン",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  python scripts/knowledge_pipeline.py                  # intake/raw/ を全処理
  python scripts/knowledge_pipeline.py --dry-run        # ドライラン
  python scripts/knowledge_pipeline.py --input ./data   # 入力ディレクトリ指定
  python scripts/knowledge_pipeline.py --workers 3      # 並列度3
  python scripts/knowledge_pipeline.py --type video     # 動画のみ
  python scripts/knowledge_pipeline.py --report latest  # レポート表示
""",
    )
    parser.add_argument("--input", type=str, help="入力ディレクトリ（デフォルト: intake/raw/）")
    parser.add_argument("--workers", type=int, default=5, help="並列実行数（デフォルト: 5）")
    parser.add_argument("--dry-run", action="store_true", help="処理せず対象ファイルを表示")
    parser.add_argument("--type", choices=["text", "video", "audio", "image", "media"],
                        help="処理するファイル種別を限定")
    parser.add_argument("--no-verify", action="store_true", help="Pass3 品質検証をスキップ")
    parser.add_argument("--whisper-model", default="base",
                        choices=["tiny", "base", "small", "medium", "large"],
                        help="Whisperモデルサイズ（デフォルト: base）")
    parser.add_argument("--report", nargs="?", const="latest",
                        help="レポート表示（latest or run_id）")

    args = parser.parse_args()

    # レポート表示モード
    if args.report is not None:
        show_report(PROJECT_ROOT / "logs" / "pipeline", args.report)
        return

    # パイプライン実行
    input_dir = Path(args.input) if args.input else None

    pipeline = KnowledgePipeline(
        project_root=PROJECT_ROOT,
        input_dir=input_dir,
        workers=args.workers,
        dry_run=args.dry_run,
        file_type_filter=args.type,
        verification_enabled=not args.no_verify,
        whisper_model=args.whisper_model,
    )

    asyncio.run(pipeline.run())


if __name__ == "__main__":
    main()
