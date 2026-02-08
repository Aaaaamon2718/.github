"""牧野氏の人格設定を管理するモジュール。

人格定義書の内容をプログラムから扱える形式で管理し、
システムプロンプトへの組み込みを行う。
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)


@dataclass
class PersonaConfig:
    """人格設定を保持するデータクラス。"""

    name: str = "牧野 克彦"
    role: str = "生命保険営業のカリスマ"

    # 性格パラメータ (0.0 - 1.0)
    warmth: float = 0.7
    strictness: float = 0.6
    professionalism: float = 0.9
    empathy: float = 0.8

    # 象徴的フレーズ
    signature_phrases: list[str] = field(default_factory=lambda: [
        "誰にでもできることを、だれにも負けないほどやる",
        "過去と他人は変えられないが、未来と自分は変えられる",
    ])

    # NGワード
    ng_words: list[str] = field(default_factory=lambda: [
        "ネットスラング全般",
        "他社批判",
        "不確実な断定表現",
        "コンプライアンス違反となる発言",
    ])

    # 文末表現の傾向
    ending_patterns: list[str] = field(default_factory=lambda: [
        "〜だね",
        "〜ですよ",
        "〜なのかな",
    ])

    def format_persona_section(self) -> str:
        """システムプロンプト用の人格セクションを生成する。"""
        return (
            f"- 名前: {self.name}\n"
            f"- 役割: {self.role}\n"
            f"- 温かさ: {self.warmth} (0:事務的 〜 1:非常に温かい)\n"
            f"- 厳しさ: {self.strictness} (0:甘い 〜 1:非常に厳しい)\n"
            f"- プロ意識: {self.professionalism} (0:カジュアル 〜 1:プロフェッショナル)\n"
            f"- 共感力: {self.empathy} (0:論理のみ 〜 1:感情重視)\n"
            f"- 文末表現: {', '.join(self.ending_patterns)}"
        )

    def format_ng_words(self) -> str:
        """システムプロンプト用のNGワードセクションを生成する。"""
        return "\n".join(f"- {word}" for word in self.ng_words)

    def format_signature_phrases(self) -> str:
        """システムプロンプト用の象徴的フレーズセクションを生成する。"""
        return "\n".join(f'- 「{phrase}」' for phrase in self.signature_phrases)


def load_persona_config(config_path: Optional[str | Path] = None) -> PersonaConfig:
    """設定ファイルから人格設定を読み込む。

    Args:
        config_path: 設定ファイルのパス。Noneの場合はデフォルト設定を返す

    Returns:
        PersonaConfigインスタンス
    """
    if config_path is None:
        logger.info("デフォルトの人格設定を使用します")
        return PersonaConfig()

    config_path = Path(config_path)
    if not config_path.exists():
        logger.warning(f"設定ファイルが見つかりません: {config_path}。デフォルト設定を使用します")
        return PersonaConfig()

    with open(config_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    persona_data = data.get("persona", {})

    config = PersonaConfig(
        name=persona_data.get("name", "牧野 克彦"),
        role=persona_data.get("role", "生命保険営業のカリスマ"),
        warmth=persona_data.get("traits", {}).get("warmth", 0.7),
        strictness=persona_data.get("traits", {}).get("strictness", 0.6),
        professionalism=persona_data.get("traits", {}).get("professionalism", 0.9),
        empathy=persona_data.get("traits", {}).get("empathy", 0.8),
        signature_phrases=persona_data.get("signature_phrases", []),
        ng_words=persona_data.get("ng_words", []),
    )

    logger.info(f"人格設定を読み込みました: {config_path}")
    return config
