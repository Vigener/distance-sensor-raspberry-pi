# -*- coding: utf-8 -*-
"""v2.8.3: 初動スキップと C-MOS 複数回サンプリング"""
from datetime import datetime
from pathlib import Path

from tests.conftest import join_background_threads


def _csv_rows(mod):
    date_str = datetime.now().strftime("%Y%m%d")
    path = Path(mod.LOG_DIR) / f"wafer_log_{date_str}.csv"
    if not path.exists():
        return []
    return path.read_text(encoding="utf-8-sig").strip().splitlines()


def _trigger(mod, ok: bool):
    mod.cmos_out1.is_pressed = ok
    if hasattr(mod, "cmos_out2"):
        mod.cmos_out2.is_pressed = ok
    mod.beam_trig.press()
    mod.beam_trig.release()


class _SeqSensor:
    def __init__(self, values):
        self._values = list(values)
        self._i = 0

    @property
    def is_pressed(self):
        v = self._values[min(self._i, len(self._values) - 1)]
        self._i += 1
        return v


def test_startup_skips_first_judgment(load_stacks):
    mod = load_stacks("stacks_v2_8_3")
    mod.STARTUP_SKIP_COUNT = 1
    mod.pb_on.press()
    mod.pb_on.release()
    assert mod.state.startup_skips_remaining == 1

    _trigger(mod, ok=False)
    assert mod.state.is_ng_locked is False
    assert mod.relay_stop.on_count == 0
    assert any("スキップ" in r for r in _csv_rows(mod))
    assert mod.state.startup_skips_remaining == 0

    _trigger(mod, ok=False)
    join_background_threads()
    assert mod.relay_stop.on_count >= 1
    assert any(",NG," in r for r in _csv_rows(mod))


def test_cmos_flicker_one_on_is_ok(load_stacks):
    """3サンプル中1回でも ON なら OK（瞬間 OFF の誤NGを防ぐ）"""
    mod = load_stacks("stacks_v2_8_3")
    mod.CMOS_SAMPLE_COUNT = 3
    mod.CMOS_SAMPLE_INTERVAL = 0
    assert mod.sample_cmos_ok(_SeqSensor([False, True, False])) is True


def test_cmos_all_off_is_ng_sample(load_stacks):
    mod = load_stacks("stacks_v2_8_3")
    mod.CMOS_SAMPLE_COUNT = 3
    mod.CMOS_SAMPLE_INTERVAL = 0
    assert mod.sample_cmos_ok(_SeqSensor([False, False, False])) is False


def test_cmos_all_off_triggers_ng(load_stacks):
    mod = load_stacks("stacks_v2_8_3")
    mod.STARTUP_SKIP_COUNT = 0
    mod.state.startup_skips_remaining = 0
    mod.CMOS_SAMPLE_COUNT = 3
    mod.CMOS_SAMPLE_INTERVAL = 0
    mod.pb_on.press()
    mod.pb_on.release()
    _trigger(mod, ok=False)
    join_background_threads()
    assert mod.relay_stop.on_count >= 1
    assert any(",NG," in r for r in _csv_rows(mod))


def test_auto_clear_rearms_startup_skip(load_stacks):
    mod = load_stacks("stacks_v2_8_3")
    mod.STARTUP_SKIP_COUNT = 1
    mod.state.startup_skips_remaining = 0
    mod.CMOS_SAMPLE_COUNT = 1
    mod.pb_on.press()
    mod.pb_on.release()
    mod.state.startup_skips_remaining = 0
    relay_before = mod.relay_stop.on_count
    _trigger(mod, ok=False)
    join_background_threads()
    assert mod.relay_stop.on_count > relay_before
    assert mod.state.startup_skips_remaining == 1

    relay_mid = mod.relay_stop.on_count
    _trigger(mod, ok=False)
    assert mod.relay_stop.on_count == relay_mid
    assert any("スキップ" in r for r in _csv_rows(mod))
