"""設定ファイルの読み込み"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_config(config_path: Path | None = None) -> dict[str, Any]:
    """設定ファイルを読み込む。

    Args:
        config_path: 設定ファイルのパス。Noneの場合はデフォルトパスを使用。

    Returns:
        設定辞書
    """
    if config_path is None:
        config_path = Path(__file__).parent.parent / "config" / "settings.yaml"

    if not config_path.exists():
        raise FileNotFoundError(f"設定ファイルが見つかりません: {config_path}")

    with open(config_path, encoding="utf-8") as f:
        config: dict[str, Any] = yaml.safe_load(f)

    return config
