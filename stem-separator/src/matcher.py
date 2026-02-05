#!/usr/bin/env python3
"""
Sound Matcher - Similarity Matching Engine
Matches stems to Logic Pro sounds based on audio features.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

import numpy as np
from rich.console import Console
from rich.table import Table

console = Console()


class SoundMatcher:
    """Match audio files to similar sounds in catalog"""

    def __init__(self, catalog_path: Optional[Path] = None):
        self.catalog_path = catalog_path or (
            Path.home() / ".stem-separator" / "logic_catalog.json"
        )
        self.catalog = self._load_catalog()

    def _load_catalog(self) -> Dict[str, Any]:
        """Load catalog from disk"""
        if self.catalog_path.exists():
            with open(self.catalog_path) as f:
                return json.load(f)
        return {"sounds": []}

    def match(
        self,
        audio_path: str,
        top_k: int = 5,
        category_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Find similar sounds in catalog.

        Args:
            audio_path: Path to audio file to match
            top_k: Number of matches to return
            category_filter: Optional category to filter by

        Returns:
            List of matches with similarity scores
        """
        from .audio_analyzer import AudioAnalyzer

        path = Path(audio_path)
        console.print(f"[dim]Matching: {path.name}[/dim]")

        # Analyze input file
        analyzer = AudioAnalyzer()
        input_features = analyzer.analyze(str(path))

        # Get catalog sounds with features
        sounds = [
            s for s in self.catalog.get("sounds", [])
            if "features" in s and "error" not in s.get("features", {})
        ]

        if category_filter:
            sounds = [s for s in sounds if s.get("category", "").lower() == category_filter.lower()]

        if not sounds:
            console.print("[yellow]No analyzed sounds in catalog. Run 'catalog analyze' first.[/yellow]")
            return []

        # Calculate similarities
        matches = []
        for sound in sounds:
            similarity = self._calculate_similarity(input_features, sound["features"])
            if similarity > 0:
                matches.append({
                    "name": sound["name"],
                    "path": sound["path"],
                    "category": sound.get("category", ""),
                    "subcategory": sound.get("subcategory", ""),
                    "similarity": round(similarity, 4),
                    "features": sound["features"]
                })

        # Sort by similarity
        matches.sort(key=lambda x: x["similarity"], reverse=True)

        return matches[:top_k]

    def _calculate_similarity(
        self,
        features_a: Dict[str, Any],
        features_b: Dict[str, Any]
    ) -> float:
        """
        Calculate similarity between two feature sets.

        Uses weighted combination of:
        - MFCC cosine similarity (primary)
        - Spectral centroid distance
        - Percussiveness similarity
        """
        scores = []
        weights = []

        # MFCC similarity (most important)
        mfcc_a = features_a.get("mfcc")
        mfcc_b = features_b.get("mfcc")

        if mfcc_a and mfcc_b:
            mfcc_sim = self._cosine_similarity(mfcc_a, mfcc_b)
            scores.append(mfcc_sim)
            weights.append(0.6)

        # Spectral centroid similarity
        sc_a = features_a.get("spectral_centroid")
        sc_b = features_b.get("spectral_centroid")

        if sc_a and sc_b:
            # Normalize difference (inverse exponential)
            sc_diff = abs(sc_a - sc_b) / max(sc_a, sc_b, 1)
            sc_sim = np.exp(-sc_diff * 2)
            scores.append(sc_sim)
            weights.append(0.2)

        # Percussiveness similarity
        perc_a = features_a.get("percussive_ratio")
        perc_b = features_b.get("percussive_ratio")

        if perc_a is not None and perc_b is not None:
            perc_diff = abs(perc_a - perc_b)
            perc_sim = 1 - perc_diff
            scores.append(perc_sim)
            weights.append(0.2)

        if not scores:
            return 0

        # Weighted average
        total_weight = sum(weights)
        weighted_score = sum(s * w for s, w in zip(scores, weights)) / total_weight

        return float(weighted_score)

    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """Calculate cosine similarity between two vectors"""
        a = np.array(a)
        b = np.array(b)

        if len(a) != len(b):
            min_len = min(len(a), len(b))
            a = a[:min_len]
            b = b[:min_len]

        dot_product = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)

        if norm_a == 0 or norm_b == 0:
            return 0

        return float(dot_product / (norm_a * norm_b))

    def match_stem(
        self,
        stem_path: str,
        top_k: int = 5
    ) -> Dict[str, Any]:
        """
        Match a stem file to Logic Pro sounds.

        Automatically determines the best category based on stem name.

        Args:
            stem_path: Path to stem WAV file
            top_k: Number of matches

        Returns:
            Dict with stem info and matches
        """
        path = Path(stem_path)
        stem_name = path.stem.lower()

        # Guess category from stem name
        category_map = {
            "drums": ["Drums", "Percussion"],
            "bass": ["Bass", "Synth Bass"],
            "piano": ["Piano", "Keyboards"],
            "guitar": ["Guitar", "Electric Guitar", "Acoustic Guitar"],
            "vocals": ["Vocals", "Voice"],
            "other": None
        }

        category = None
        for key, cats in category_map.items():
            if key in stem_name:
                category = cats[0] if cats else None
                break

        # Get matches
        matches = self.match(str(path), top_k=top_k, category_filter=category)

        return {
            "stem": path.name,
            "guessed_category": category,
            "matches": matches
        }


class DrumSoundMatcher(SoundMatcher):
    """
    ドラム音源専用マッチャー
    Drum Kit Designer / Drum Machine Designerに特化
    """

    # ドラムパーツのカテゴリマッピング
    DRUM_CATEGORIES = {
        'kick': ['Kick', 'Bass Drum', '808', '909', 'BD'],
        'snare': ['Snare', 'Clap', 'Rim', 'SD'],
        'hihat': ['Hi-Hat', 'HH', 'Hat', 'Open Hat', 'Closed Hat'],
        'toms': ['Tom', 'Floor Tom', 'Rack Tom'],
        'ride': ['Ride', 'Bell'],
        'crash': ['Crash', 'Cymbal'],
    }

    def __init__(self, catalog_path: Optional[Path] = None):
        super().__init__(catalog_path)

    def match_drum_stem(
        self,
        stem_type: str,
        audio_path: str,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        ドラムステムタイプに応じた最適キット検索

        Args:
            stem_type: kick, snare, hihat, toms, ride, crash
            audio_path: 分離されたドラムステムのパス
            top_k: 返す候補数

        Returns:
            マッチング結果のリスト
        """
        console.print(f"[dim]Matching drum stem: {stem_type}[/dim]")

        # ステムタイプに応じたキーワードフィルタ
        keywords = self.DRUM_CATEGORIES.get(stem_type.lower(), [])

        # 基本マッチング実行
        all_matches = self.match(audio_path, top_k=top_k * 3)

        # キーワードでフィルタリング
        filtered_matches = []
        for match in all_matches:
            name = match["name"].lower()
            category = match.get("category", "").lower()

            # キーワードに一致するものを優先
            matches_keyword = any(
                kw.lower() in name or kw.lower() in category
                for kw in keywords
            )

            if matches_keyword:
                match["keyword_match"] = True
                filtered_matches.append(match)

        # キーワードマッチが不足している場合は全体から補完
        if len(filtered_matches) < top_k:
            for match in all_matches:
                if match not in filtered_matches:
                    match["keyword_match"] = False
                    filtered_matches.append(match)
                    if len(filtered_matches) >= top_k:
                        break

        return filtered_matches[:top_k]

    def match_all_drum_stems(
        self,
        stems_dir: str,
        top_k: int = 3
    ) -> Dict[str, List[Dict]]:
        """
        ドラムステムディレクトリ内の全パーツをマッチング

        Args:
            stems_dir: stage2/drums/ ディレクトリ
            top_k: 各パーツの候補数

        Returns:
            パーツ名 -> マッチングリストの辞書
        """
        stems_path = Path(stems_dir)
        results = {}

        console.print("\n[bold cyan]Drum Sound Matching[/bold cyan]")

        for stem_type in self.DRUM_CATEGORIES.keys():
            stem_file = stems_path / f"{stem_type}.wav"
            if stem_file.exists():
                matches = self.match_drum_stem(stem_type, str(stem_file), top_k)
                results[stem_type] = matches

                # 結果表示
                if matches:
                    top_match = matches[0]
                    console.print(
                        f"  {stem_type}: [green]{top_match['name']}[/green] "
                        f"({top_match['similarity']*100:.0f}%)"
                    )
            else:
                console.print(f"  {stem_type}: [dim]not found[/dim]")

        return results

    def generate_kit_suggestion(
        self,
        matching_results: Dict[str, List[Dict]]
    ) -> Dict[str, Any]:
        """
        マッチング結果から最適なドラムキット構成を提案

        Args:
            matching_results: match_all_drum_stemsの結果

        Returns:
            推奨キット設定
        """
        suggestion = {
            "recommended_kit": None,
            "parts": {},
            "eq_hints": []
        }

        # 各パーツの最適マッチを収集
        kit_candidates = {}

        for part, matches in matching_results.items():
            if matches:
                best = matches[0]
                suggestion["parts"][part] = {
                    "preset": best["name"],
                    "category": best.get("category", ""),
                    "similarity": best["similarity"]
                }

                # キットの出現頻度をカウント
                cat = best.get("category", "Unknown")
                kit_candidates[cat] = kit_candidates.get(cat, 0) + 1

        # 最も多く使われているカテゴリをキットとして推奨
        if kit_candidates:
            suggestion["recommended_kit"] = max(kit_candidates, key=kit_candidates.get)

        return suggestion


class TimbreMatcher(SoundMatcher):
    """
    Audio Spectrogram Transformerベースの高精度マッチャー
    768次元のTimbre Embeddingを使用
    """

    def __init__(self, catalog_path: Optional[Path] = None):
        super().__init__(catalog_path)
        self._ast_model = None
        self._ast_extractor = None

    def _load_ast_model(self):
        """AST（Audio Spectrogram Transformer）モデルの遅延ロード"""
        if self._ast_model is not None:
            return

        try:
            from transformers import ASTModel, ASTFeatureExtractor
            self._ast_model = ASTModel.from_pretrained(
                "MIT/ast-finetuned-audioset-10-10-0.4593"
            )
            self._ast_extractor = ASTFeatureExtractor.from_pretrained(
                "MIT/ast-finetuned-audioset-10-10-0.4593"
            )
            console.print("[dim]AST model loaded[/dim]")
        except ImportError:
            console.print("[yellow]transformers not installed. Using basic matching.[/yellow]")
        except Exception as e:
            console.print(f"[yellow]Could not load AST model: {e}[/yellow]")

    def get_timbre_embedding(self, audio_path: str) -> Optional[np.ndarray]:
        """
        音声ファイルから768次元のTimbre Embeddingを抽出

        Args:
            audio_path: 音声ファイルのパス

        Returns:
            768次元のembeddingベクトル、または失敗時None
        """
        self._load_ast_model()

        if self._ast_model is None:
            return None

        try:
            import torch
            import torchaudio

            # 音声読み込み
            waveform, sample_rate = torchaudio.load(audio_path)

            # 16kHzにリサンプリング
            if sample_rate != 16000:
                resampler = torchaudio.transforms.Resample(sample_rate, 16000)
                waveform = resampler(waveform)

            # モノラル化
            if waveform.shape[0] > 1:
                waveform = torch.mean(waveform, dim=0, keepdim=True)

            # 特徴量抽出
            inputs = self._ast_extractor(
                waveform.squeeze().numpy(),
                sampling_rate=16000,
                return_tensors="pt"
            )

            # Embedding取得
            with torch.no_grad():
                outputs = self._ast_model(**inputs)
                # [CLS]トークンのembedding
                embedding = outputs.last_hidden_state[:, 0, :].numpy()

            return embedding.flatten()

        except Exception as e:
            console.print(f"[yellow]Embedding extraction failed: {e}[/yellow]")
            return None

    def match_with_embedding(
        self,
        audio_path: str,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Timbre Embeddingを使用した高精度マッチング

        Args:
            audio_path: 音声ファイルのパス
            top_k: 返す候補数

        Returns:
            マッチング結果（embeddingベースの類似度含む）
        """
        input_embedding = self.get_timbre_embedding(audio_path)

        if input_embedding is None:
            # フォールバック: 基本マッチング
            return self.match(audio_path, top_k=top_k)

        # カタログ内の音源とembedding比較
        sounds = self.catalog.get("sounds", [])
        matches = []

        for sound in sounds:
            # カタログにembeddingがあれば使用
            if "timbre_embedding" in sound.get("features", {}):
                catalog_embedding = np.array(sound["features"]["timbre_embedding"])
                similarity = self._cosine_similarity(
                    input_embedding.tolist(),
                    catalog_embedding.tolist()
                )
            else:
                # embeddingがない場合はスキップ or 基本特徴量で計算
                continue

            matches.append({
                "name": sound["name"],
                "path": sound.get("path", ""),
                "category": sound.get("category", ""),
                "similarity": round(similarity, 4),
                "embedding_match": True
            })

        matches.sort(key=lambda x: x["similarity"], reverse=True)
        return matches[:top_k]


def match_file(audio_path: str, top_k: int = 5) -> List[Dict]:
    """Match single file to catalog"""
    matcher = SoundMatcher()
    matches = matcher.match(audio_path, top_k=top_k)

    if matches:
        table = Table(title=f"Matches for {Path(audio_path).name}")
        table.add_column("#", style="dim")
        table.add_column("Sound", style="cyan")
        table.add_column("Category")
        table.add_column("Similarity", justify="right", style="green")

        for i, match in enumerate(matches, 1):
            table.add_row(
                str(i),
                match["name"],
                match.get("category", ""),
                f"{match['similarity'] * 100:.1f}%"
            )

        console.print(table)
    else:
        console.print("[yellow]No matches found[/yellow]")

    return matches


def main():
    """CLI entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Match audio to Logic Pro sounds")
    parser.add_argument("input", help="Audio file to match")
    parser.add_argument("--top", "-k", type=int, default=5, help="Number of matches")
    parser.add_argument("--category", "-c", help="Filter by category")

    args = parser.parse_args()

    matcher = SoundMatcher()
    matches = matcher.match(args.input, top_k=args.top, category_filter=args.category)

    if matches:
        table = Table(title=f"Matches for {Path(args.input).name}")
        table.add_column("#", style="dim")
        table.add_column("Sound", style="cyan")
        table.add_column("Category")
        table.add_column("Similarity", justify="right", style="green")

        for i, match in enumerate(matches, 1):
            table.add_row(
                str(i),
                match["name"],
                match.get("category", ""),
                f"{match['similarity'] * 100:.1f}%"
            )

        console.print(table)
    else:
        console.print("[yellow]No matches found. Make sure catalog is built and analyzed.[/yellow]")


if __name__ == "__main__":
    main()
