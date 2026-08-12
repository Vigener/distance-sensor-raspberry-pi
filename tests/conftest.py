# -*- coding: utf-8 -*-
import importlib
import os
import sys
import threading
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests import fake_gpiozero

REAL_EXISTS = os.path.exists

MANUAL_RESET_MODULES = ("stacks_v2_7_2", "stacks_v2_7_3")
AUTO_CLEAR_MODULES = ("stacks_v2_8_0", "stacks_v2_8_1", "stacks_v2_8_2")
ALL_ALGORITHM_MODULES = MANUAL_RESET_MODULES + AUTO_CLEAR_MODULES


def _purge_stacks_modules():
    for name in list(sys.modules):
        if name.startswith("stacks_v2_"):
            del sys.modules[name]


def join_background_threads(timeout=1.0):
    """デーモン判定スレッド等の完了を待つ"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        alive = [
            t
            for t in threading.enumerate()
            if t is not threading.main_thread() and t.is_alive()
        ]
        if not alive:
            return
        time.sleep(0.005)


@pytest.fixture
def load_stacks(monkeypatch, tmp_path):
    """指定バージョンの stacks モジュールをフェイクGPIO付きでロードするファクトリ"""

    def _load(module_name: str):
        _purge_stacks_modules()
        monkeypatch.setitem(sys.modules, "gpiozero", fake_gpiozero)

        def _exists(path):
            if str(path) in (
                "/home/raspai/Desktop/logs",
                "/home/raspai/Desktop/stacks/logs",
            ):
                return True
            return REAL_EXISTS(path)

        monkeypatch.setattr(os.path, "exists", _exists)

        mod = importlib.import_module(module_name)
        mod.LOG_DIR = str(tmp_path)
        mod.CHECK_DELAY = 0
        mod.RELAY_PULSE = 0.01
        mod.BUZZER_PULSE = 0.01
        mod.SAVE_OK_LOG = False
        if hasattr(mod, "MODE_BEEP_DURATION"):
            mod.MODE_BEEP_DURATION = 0
            mod.MODE_BEEP_GAP = 0
        if hasattr(mod, "ENABLE_MODE_SWITCH"):
            mod.ENABLE_MODE_SWITCH = False
        if hasattr(mod, "reload_mode_switch_config"):
            from mode_switch_settings import write_enable_mode_switch

            write_enable_mode_switch(False, Path(mod._STACKS_DIR))
            mod.reload_mode_switch_config()

        monkeypatch.setattr(mod.time, "sleep", lambda _s: None)

        mod.state.is_active = False
        mod.state.is_ng_locked = False
        if hasattr(mod.state, "sheet_mode"):
            mod.state.sheet_mode = 3
        if hasattr(mod, "_beam_armed"):
            mod._beam_armed = True
        if hasattr(mod, "_shutting_down"):
            mod._shutting_down = False
        if hasattr(mod, "_mode_feedback_busy"):
            mod._mode_feedback_busy = False
        if hasattr(mod, "_mode_feedback_cancel"):
            mod._mode_feedback_cancel.clear()
        if hasattr(mod, "_ng_lock_generation"):
            mod._ng_lock_generation = 0

        mod.relay_stop.off()
        mod.buzzer.off()
        mod.led_green.off()
        mod.led_yellow.off()
        mod.led_red.off()

        mod.initialize_runtime()
        return mod

    return _load


@pytest.fixture(params=list(ALL_ALGORITHM_MODULES))
def stacks(request, load_stacks):
    """全バージョンの共通アルゴリズム契約"""
    return load_stacks(request.param)


@pytest.fixture(params=list(MANUAL_RESET_MODULES))
def stacks_manual_reset(request, load_stacks):
    """人手リセット必須のバージョン専用"""
    return load_stacks(request.param)


@pytest.fixture(params=list(AUTO_CLEAR_MODULES))
def stacks_auto_clear(request, load_stacks):
    """NG後自動復帰バージョン専用"""
    return load_stacks(request.param)
