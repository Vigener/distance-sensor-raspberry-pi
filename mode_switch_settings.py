# -*- coding: utf-8 -*-
"""ENABLE_MODE_SWITCH 用の外部設定（mode_switch.conf）の読み書き。"""

from __future__ import annotations

from pathlib import Path

CONFIG_FILENAME = "mode_switch.conf"
CONFIG_KEY = "enable_mode_switch"


def conf_path(base_dir: str | Path | None = None) -> Path:
    root = Path(base_dir) if base_dir is not None else Path(__file__).resolve().parent
    return root / CONFIG_FILENAME


def read_enable_mode_switch(base_dir: str | Path | None = None) -> bool:
    """conf が無い／不正なときは False（安全側）。"""
    path = conf_path(base_dir)
    if not path.is_file():
        return False
    try:
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key.strip() == CONFIG_KEY:
                return value.strip().lower() in ("1", "true", "yes", "on")
    except OSError:
        return False
    return False


def write_enable_mode_switch(enabled: bool, base_dir: str | Path | None = None) -> Path:
    path = conf_path(base_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = (
        "# 黄ボタンによる 3枚/2枚 モード切替機能\n"
        "# true / false\n"
        f"{CONFIG_KEY}={'true' if enabled else 'false'}\n"
    )
    path.write_text(text, encoding="utf-8")
    return path
