"""ナレッジベースの読み込み・加工・検証を行うモジュール。

CSV形式のナレッジデータを読み込み、
バリデーションと統計情報の生成を行う。
"""

import csv
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ラベリングスキーマに定義されたカテゴリ
VALID_CATEGORIES = [
    "法人保険",
    "ドクターマーケット",
    "相続",
    "営業マインド",
    "営業スキル",
    "コンプライアンス",
]

VALID_PRIORITIES = ["高", "中", "低"]

VALID_EMOTION_TAGS = [
    "励まし",
    "叱咤",
    "論理的解説",
    "共感",
    "雑談/アイスブレイク",
    "情熱",
]


@dataclass
class KnowledgeEntry:
    """ナレッジベースの1エントリを表すデータクラス。"""

    entry_id: str
    category: str
    sub_category: str
    question_topic: str
    answer_content: str
    source: str
    expression_tags: list[str]
    emotion_tag: str
    priority: str


def load_knowledge_csv(file_path: str | Path) -> list[KnowledgeEntry]:
    """CSV形式のナレッジベースファイルを読み込む。

    Args:
        file_path: CSVファイルのパス

    Returns:
        KnowledgeEntryのリスト

    Raises:
        FileNotFoundError: ファイルが存在しない場合
        ValueError: CSVのフォーマットが不正な場合
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"ナレッジベースファイルが見つかりません: {file_path}")

    entries: list[KnowledgeEntry] = []

    with open(file_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row_num, row in enumerate(reader, start=2):
            try:
                entry = KnowledgeEntry(
                    entry_id=row["ID"],
                    category=row["カテゴリ"],
                    sub_category=row["サブカテゴリ"],
                    question_topic=row["質問/トピック"],
                    answer_content=row["回答/内容"],
                    source=row["出典"],
                    expression_tags=[
                        t.strip() for t in row.get("言い回しタグ", "").split(",") if t.strip()
                    ],
                    emotion_tag=row.get("感情タグ", ""),
                    priority=row.get("優先度", "中"),
                )
                entries.append(entry)
            except KeyError as e:
                logger.warning(f"行 {row_num}: 必須カラムが不足しています: {e}")

    logger.info(f"ナレッジベース読み込み完了: {len(entries)}件")
    return entries


def validate_entry(entry: KnowledgeEntry) -> list[str]:
    """エントリのバリデーションを実施する。

    Args:
        entry: 検証対象のエントリ

    Returns:
        エラーメッセージのリスト（空なら問題なし）
    """
    errors: list[str] = []

    if not entry.entry_id:
        errors.append("IDが空です")

    if entry.category not in VALID_CATEGORIES:
        errors.append(f"無効なカテゴリ: {entry.category}")

    if entry.priority not in VALID_PRIORITIES:
        errors.append(f"無効な優先度: {entry.priority}")

    if not entry.question_topic:
        errors.append("質問/トピックが空です")

    if not entry.answer_content:
        errors.append("回答/内容が空です")

    if not entry.source:
        errors.append("出典が空です")

    return errors


def validate_knowledge_base(entries: list[KnowledgeEntry]) -> dict[str, list[str]]:
    """ナレッジベース全体のバリデーションを実施する。

    Args:
        entries: 検証対象のエントリリスト

    Returns:
        エントリIDをキー、エラーリストを値とする辞書
    """
    all_errors: dict[str, list[str]] = {}

    for entry in entries:
        errors = validate_entry(entry)
        if errors:
            all_errors[entry.entry_id] = errors

    if all_errors:
        logger.warning(f"バリデーションエラー: {len(all_errors)}件のエントリに問題があります")
    else:
        logger.info("バリデーション完了: 全エントリが正常です")

    return all_errors


def get_entries_by_category(
    entries: list[KnowledgeEntry],
    category: str,
    priority: Optional[str] = None,
) -> list[KnowledgeEntry]:
    """カテゴリと優先度でエントリをフィルタする。

    Args:
        entries: フィルタ対象のエントリリスト
        category: 検索するカテゴリ
        priority: 優先度フィルタ（省略時は全優先度）

    Returns:
        条件に一致するエントリのリスト
    """
    filtered = [e for e in entries if e.category == category]

    if priority:
        filtered = [e for e in filtered if e.priority == priority]

    return filtered


def generate_stats(entries: list[KnowledgeEntry]) -> dict[str, int]:
    """ナレッジベースの統計情報を生成する。

    Args:
        entries: 統計対象のエントリリスト

    Returns:
        統計情報の辞書
    """
    stats: dict[str, int] = {
        "total": len(entries),
        "priority_high": len([e for e in entries if e.priority == "高"]),
        "priority_medium": len([e for e in entries if e.priority == "中"]),
        "priority_low": len([e for e in entries if e.priority == "低"]),
    }

    for cat in VALID_CATEGORIES:
        stats[f"category_{cat}"] = len([e for e in entries if e.category == cat])

    return stats
