# -*- coding: utf-8 -*-
"""v2.8.1 モード切替（ENABLE_MODE_SWITCH）のテスト"""
from datetime import datetime
from pathlib import Path

import pytest

from tests.conftest import join_background_threads


def _csv_rows(mod):
    date_str = datetime.now().strftime("%Y%m%d")
    path = Path(mod.LOG_DIR) / f"wafer_log_{date_str}.csv"
    if not path.exists():
        return []
    return path.read_text(encoding="utf-8-sig").strip().splitlines()


def _press_yellow(mod):
    mod.pb_reset.press()
    mod.pb_reset.release()
    join_background_threads()


def _trigger_beam_on(mod, sensor, ok: bool):
    mod.cmos_out1.is_pressed = False
    mod.cmos_out2.is_pressed = False
    sensor.is_pressed = ok
    mod.beam_trig.press()
    mod.beam_trig.release()


@pytest.fixture
def stacks_mode_off(load_stacks):
    return load_stacks("stacks_v2_8_1")


@pytest.fixture
def stacks_mode_on(load_stacks):
    mod = load_stacks("stacks_v2_8_1")
    mod.ENABLE_MODE_SWITCH = True
    mod.MODE_BEEP_DURATION = 0
    mod.MODE_BEEP_GAP = 0
    mod.state.sheet_mode = 3
    mod._mode_feedback_busy = False
    mod.update_status_leds()
    return mod


@pytest.fixture
def stacks_mode_on_v282(load_stacks):
    from mode_switch_settings import write_enable_mode_switch

    mod = load_stacks("stacks_v2_8_2")
    write_enable_mode_switch(True, Path(mod._STACKS_DIR))
    mod.reload_mode_switch_config()
    mod.MODE_BEEP_DURATION = 0
    mod.MODE_BEEP_GAP = 0
    mod.state.sheet_mode = 3
    mod._mode_feedback_busy = False
    mod.update_status_leds()
    return mod


def test_flag_false_yellow_button_noop(stacks_mode_off):
    mod = stacks_mode_off
    assert mod.ENABLE_MODE_SWITCH is False
    mod.pb_on.press()
    before = mod.state.sheet_mode
    buzzer_before = mod.buzzer.on_count
    _press_yellow(mod)
    assert mod.state.sheet_mode == before
    assert mod.buzzer.on_count == buzzer_before
    assert not any("モード切替" in r for r in _csv_rows(mod))


def test_flag_false_always_uses_gpio16(stacks_mode_off):
    mod = stacks_mode_off
    mod.pb_on.press()
    mod.cmos_out1.is_pressed = True
    mod.cmos_out2.is_pressed = False
    mod.beam_trig.press()
    mod.beam_trig.release()
    assert mod.state.is_ng_locked is False
    assert not any(",NG," in r for r in _csv_rows(mod))


def test_toggle_switches_active_cmos(stacks_mode_on):
    mod = stacks_mode_on
    mod.pb_on.press()
    assert mod.state.sheet_mode == 3
    assert mod.active_cmos() is mod.cmos_out1

    _press_yellow(mod)
    assert mod.state.sheet_mode == 2
    assert mod.active_cmos() is mod.cmos_out2
    assert any("モード切替" in r for r in _csv_rows(mod))

    _press_yellow(mod)
    assert mod.state.sheet_mode == 3
    assert mod.active_cmos() is mod.cmos_out1


def test_v282_conf_true_toggles_like_v281(stacks_mode_on_v282):
    mod = stacks_mode_on_v282
    assert mod.ENABLE_MODE_SWITCH is True
    mod.pb_on.press()
    mod.pb_on.release()
    _press_yellow(mod)
    assert mod.state.sheet_mode == 2
    assert mod.active_cmos() is mod.cmos_out2


def test_judgment_uses_selected_channel(stacks_mode_on):
    mod = stacks_mode_on
    mod.pb_on.press()

    _trigger_beam_on(mod, mod.cmos_out1, True)
    assert mod.state.is_ng_locked is False

    _press_yellow(mod)
    assert mod.state.sheet_mode == 2

    mod.cmos_out1.is_pressed = True
    mod.cmos_out2.is_pressed = False
    mod.beam_trig.press()
    mod.beam_trig.release()
    join_background_threads()
    assert any("GPIO20" in r and ",NG," in r for r in _csv_rows(mod))


def test_feedback_beep_counts_and_steady_led(stacks_mode_on):
    mod = stacks_mode_on
    mod.pb_on.press()
    assert mod.led_yellow.is_active is True

    buzzer_before = mod.buzzer.on_count
    _press_yellow(mod)  # → 2枚
    assert mod.state.sheet_mode == 2
    assert mod.buzzer.on_count - buzzer_before == 2
    assert mod.led_yellow.is_active is False

    buzzer_before = mod.buzzer.on_count
    _press_yellow(mod)  # → 3枚
    assert mod.state.sheet_mode == 3
    assert mod.buzzer.on_count - buzzer_before == 3
    assert mod.led_yellow.is_active is True


def test_ignore_yellow_during_ng_lock(stacks_mode_on, monkeypatch):
    mod = stacks_mode_on
    mod.pb_on.press()

    def pulse_only(generation=None):
        mod.pulse_output(mod.buzzer, mod.BUZZER_PULSE)

    monkeypatch.setattr(mod, "_buzzer_then_auto_clear", pulse_only)
    mod.cmos_out1.is_pressed = False
    mod.beam_trig.press()
    mod.beam_trig.release()
    join_background_threads()
    assert mod.state.is_ng_locked is True
    mode_before = mod.state.sheet_mode
    _press_yellow(mod)
    assert mod.state.sheet_mode == mode_before


def test_beam_ignored_during_mode_feedback(stacks_mode_on):
    """切替フィードバック中は判定せず、NG警報とLEDが競合しない"""
    mod = stacks_mode_on
    mod.pb_on.press()
    mod._mode_feedback_busy = True
    relay_before = mod.relay_stop.on_count
    mod.cmos_out1.is_pressed = False
    mod.beam_trig.press()
    mod.beam_trig.release()
    assert mod.state.is_ng_locked is False
    assert mod.relay_stop.on_count == relay_before


def test_stale_auto_clear_does_not_unlock_new_ng(stacks_mode_on, monkeypatch):
    mod = stacks_mode_on
    mod.pb_on.press()
    mod.pb_on.release()
    held = []

    def hold_clear(generation):
        held.append(generation)

    monkeypatch.setattr(mod, "_buzzer_then_auto_clear", hold_clear)
    _trigger_beam_on(mod, mod.cmos_out1, False)
    join_background_threads()
    assert held, "NG 時に hold_clear が呼ばれていない"
    gen1 = held[0]
    mod.pb_off.press()
    mod.pb_off.release()
    mod.pb_on.press()
    mod.pb_on.release()
    assert mod.state.is_active is True
    _trigger_beam_on(mod, mod.cmos_out1, False)
    join_background_threads()
    assert len(held) == 2
    gen2 = held[1]
    assert gen1 != gen2
    mod.clear_ng_lock(expected_generation=gen1)
    assert mod.state.is_ng_locked is True
    mod.clear_ng_lock(expected_generation=gen2)
    assert mod.state.is_ng_locked is False
