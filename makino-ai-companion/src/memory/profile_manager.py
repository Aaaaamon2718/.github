"""ユーザープロファイル管理。

ユーザーのプロファイルJSONをシステムプロンプト用のテキストに変換する。
セッション開始時に呼び出され、ユーザーに合わせた回答調整を実現する。
"""

import json
import logging
import sqlite3
from typing import Optional

from src.database.operations import get_or_create_profile

logger = logging.getLogger(__name__)


def load_profile_context(
    conn: sqlite3.Connection,
    user_id: str,
) -> Optional[str]:
    """ユーザープロファイルをシステムプロンプト注入用テキストに変換する。

    Args:
        conn: DB接続
        user_id: ユーザーID

    Returns:
        プロンプト注入用テキスト。anonymous や空プロファイルの場合は None。
    """
    if not user_id or user_id == "anonymous":
        return None

    profile = get_or_create_profile(conn, user_id)
    profile_json_str = profile.get("profile_json", "{}")

    try:
        profile_data = json.loads(profile_json_str)
    except (json.JSONDecodeError, TypeError):
        return None

    if not profile_data:
        return None

    parts: list[str] = ["## このユーザーについて"]

    # 理解度レベル
    understanding = profile_data.get("understanding_level", {})
    if understanding:
        parts.append("### 理解度")
        for topic, info in understanding.items():
            if isinstance(info, dict):
                level = info.get("level", "不明")
                evidence = info.get("evidence", "")
                parts.append(f"- {topic}: {level}")
                if evidence:
                    parts.append(f"  （根拠: {evidence}）")
            else:
                parts.append(f"- {topic}: {info}")

    # 行動パターン
    behavior = profile_data.get("behavior_pattern", {})
    if behavior:
        traits: list[str] = []
        if behavior.get("needs_concrete_examples"):
            traits.append("具体的な数値例を使った説明を好む")
        if behavior.get("tends_to_deep_dive"):
            traits.append("1つのテーマを深掘りする傾向")
        preferred = behavior.get("preferred_input", "")
        if preferred == "guided_nav":
            traits.append("質問ナビ経由の利用が多い")
        if traits:
            parts.append("### 行動傾向")
            for t in traits:
                parts.append(f"- {t}")

    # 未解決トピック
    unresolved = profile_data.get("unresolved_topics", [])
    if unresolved:
        parts.append("### 過去に解決しなかった質問")
        for item in unresolved[:3]:
            if isinstance(item, dict):
                topic = item.get("topic", "")
                parts.append(f"- {topic}")
            else:
                parts.append(f"- {item}")

    # 回答ガイドライン生成
    guidelines = _generate_guidelines(profile_data)
    if guidelines:
        parts.append("### 回答時の留意点")
        for g in guidelines:
            parts.append(f"- {g}")

    if len(parts) <= 1:
        return None

    return "\n".join(parts)


def _generate_guidelines(profile_data: dict) -> list[str]:
    """プロファイルから回答ガイドラインを自動生成する。"""
    guidelines: list[str] = []

    # 理解度に基づくガイドライン
    understanding = profile_data.get("understanding_level", {})
    has_beginner = False
    has_advanced = False
    for info in understanding.values():
        if isinstance(info, dict):
            level = info.get("level", "")
            if "基礎" in level or "初心" in level or "学習中" in level:
                has_beginner = True
            if "上級" in level or "実践" in level or "応用" in level:
                has_advanced = True

    if has_beginner:
        guidelines.append("専門用語を使う際は簡単な説明を添えること")
        guidelines.append("可能な限り具体的な数値例を含めること")
    if has_advanced:
        guidelines.append("専門的な内容にも踏み込んで詳細に説明してよい")

    # 未解決トピックへの配慮
    unresolved = profile_data.get("unresolved_topics", [])
    if unresolved:
        topics = []
        for item in unresolved[:2]:
            if isinstance(item, dict):
                topics.append(item.get("topic", ""))
        if topics:
            guidelines.append(
                f"過去に未解決の質問がある: {', '.join(topics)}。関連する質問には特に丁寧に回答すること"
            )

    # 行動パターンに基づくガイドライン
    behavior = profile_data.get("behavior_pattern", {})
    if behavior.get("needs_concrete_examples"):
        if "具体的な数値例を含めること" not in "".join(guidelines):
            guidelines.append("具体例や数値を交えた説明を優先すること")

    return guidelines
