# -*- coding: utf-8 -*-
import importlib
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests import fake_gpiozero

REAL_EXISTS = os.path.exists


def _purge_stacks_modules():
    for name in list(sys.modules):
        if name.startswith("stacks_v2_7_"):
            del sys.modules[name]


@pytest.fixture
def load_stacks(monkeypatch, tmp_path):
    """指定バージョンの stacks モジュールをフェイクGPIO付きでロードするファクトリ"""

    def _load(module_name: str):
        _purge_stacks_modules()
        monkeypatch.setitem(sys.modules, "gpiozero", fake_gpiozero)

        # 実機パスへの mkdir を避ける（他パスは通常どおり）
        def _exists(path):
            if str(path) == "/home/raspai/Desktop/logs":
                return True
            return REAL_EXISTS(path)

        monkeypatch.setattr(os.path, "exists", _exists)

        mod = importlib.import_module(module_name)
        mod.LOG_DIR = str(tmp_path)
        mod.CHECK_DELAY = 0
        mod.RELAY_PULSE = 0.01
        mod.BUZZER_PULSE = 0.01
        mod.SAVE_OK_LOG = False

        # 実時間待ちを最小化（pulse_output 内の sleep も短縮）
        monkeypatch.setattr(mod.time, "sleep", lambda _s: None)

        mod.state.is_active = False
        mod.state.is_ng_locked = False
        if hasattr(mod, "_beam_armed"):
            mod._beam_armed = True
        if hasattr(mod, "_shutting_down"):
            mod._shutting_down = False

        mod.relay_stop.off()
        mod.buzzer.off()
        mod.led_green.off()
        mod.led_yellow.off()
        mod.led_red.off()

        mod.initialize_runtime()
        return mod

    return _load


@pytest.fixture(params=["stacks_v2_7_2", "stacks_v2_7_3"])
def stacks(request, load_stacks):
    """アルゴリズム互換性を両バージョンで検証するためのパラメタライズ fixture"""
    return load_stacks(request.param)
