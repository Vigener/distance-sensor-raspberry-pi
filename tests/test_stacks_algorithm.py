# -*- coding: utf-8 -*-
"""
共通アルゴリズム契約テスト。

- 全バージョン: ON/OFF/OK/NGパルス等
- 人手リセット系は stacks_manual_reset のみ
- 自動復帰系のロック持続は別ファイルで検証
"""
from datetime import datetime
from pathlib import Path

import pytest

from tests.conftest import AUTO_CLEAR_MODULES, ALL_ALGORITHM_MODULES, join_background_threads


def _csv_rows(mod):
    date_str = datetime.now().strftime("%Y%m%d")
    path = Path(mod.LOG_DIR) / f"wafer_log_{date_str}.csv"
    if not path.exists():
        return []
    return path.read_text(encoding="utf-8-sig").strip().splitlines()


def _trigger_beam(mod, cmos_ok: bool):
    mod.cmos_out1.is_pressed = cmos_ok
    if hasattr(mod, "cmos_out2"):
        mod.cmos_out2.is_pressed = cmos_ok
    mod.beam_trig.press()
    mod.beam_trig.release()


def test_power_on_is_inactive_red_led(stacks):
    mod = stacks
    assert mod.state.is_active is False
    assert mod.state.is_ng_locked is False
    assert mod.led_red.is_active is True
    assert mod.led_green.is_active is False
    assert mod.led_yellow.is_active is False
    assert mod.relay_stop.is_active is False
    assert mod.buzzer.is_active is False


def test_startup_csv_log(stacks):
    assert any("通電起動" in r for r in _csv_rows(stacks))


def test_on_button_starts_monitoring(stacks):
    mod = stacks
    mod.pb_on.press()
    assert mod.state.is_active is True
    assert mod.state.is_ng_locked is False
    assert mod.led_green.is_active is True
    assert mod.led_red.is_active is False
    assert any("起動" in r for r in _csv_rows(mod))


def test_off_button_stops_monitoring(stacks):
    mod = stacks
    mod.pb_on.press()
    mod.pb_off.press()
    assert mod.state.is_active is False
    assert mod.state.is_ng_locked is False
    assert mod.led_red.is_active is True
    assert mod.led_green.is_active is False
    assert mod.relay_stop.is_active is False
    assert mod.buzzer.is_active is False


def test_inactive_ignores_beam(stacks):
    mod = stacks
    _trigger_beam(mod, cmos_ok=False)
    assert mod.state.is_ng_locked is False
    assert mod.relay_stop.on_count == 0
    assert not any("枚数判定" in r for r in _csv_rows(mod))


def test_ok_judgment_does_not_lock_or_pulse(stacks):
    mod = stacks
    mod.pb_on.press()
    relay_before = mod.relay_stop.on_count
    buzzer_before = mod.buzzer.on_count

    _trigger_beam(mod, cmos_ok=True)

    assert mod.state.is_ng_locked is False
    assert mod.led_yellow.is_active is False
    assert mod.relay_stop.on_count == relay_before
    assert mod.buzzer.on_count == buzzer_before
    assert not any("枚数判定" in r and ",OK," in r for r in _csv_rows(mod))


@pytest.mark.parametrize("module_name", list(ALL_ALGORITHM_MODULES))
def test_ok_log_when_enabled(load_stacks, module_name):
    mod = load_stacks(module_name)
    mod.SAVE_OK_LOG = True
    mod.pb_on.press()
    _trigger_beam(mod, cmos_ok=True)
    assert any("枚数判定" in r and ",OK," in r for r in _csv_rows(mod))


def test_ng_pulses_and_logs(stacks):
    mod = stacks
    mod.pb_on.press()
    _trigger_beam(mod, cmos_ok=False)

    assert mod.led_green.is_active is True
    assert mod.relay_stop.on_count >= 1
    assert mod.buzzer.on_count >= 1
    assert any("枚数判定" in r and ",NG," in r for r in _csv_rows(mod))

    if mod.__name__ in AUTO_CLEAR_MODULES:
        join_background_threads()
        assert mod.state.is_ng_locked is False
        assert mod.led_yellow.is_active is False
    else:
        assert mod.state.is_ng_locked is True
        assert mod.led_yellow.is_active is True


def test_ng_lock_blocks_further_judgment_manual_reset(stacks_manual_reset):
    mod = stacks_manual_reset
    mod.pb_on.press()
    _trigger_beam(mod, cmos_ok=False)
    relay_after_first = mod.relay_stop.on_count

    _trigger_beam(mod, cmos_ok=False)
    assert mod.relay_stop.on_count == relay_after_first


def test_reset_clears_ng_lock_and_allows_next(stacks_manual_reset):
    mod = stacks_manual_reset
    mod.pb_on.press()
    _trigger_beam(mod, cmos_ok=False)
    assert mod.state.is_ng_locked is True

    mod.pb_reset.press()
    assert mod.state.is_ng_locked is False
    assert mod.led_yellow.is_active is False

    _trigger_beam(mod, cmos_ok=True)
    assert mod.state.is_ng_locked is False


def test_reset_ignored_when_not_locked(stacks_manual_reset):
    mod = stacks_manual_reset
    mod.pb_on.press()
    mod.pb_reset.press()
    assert mod.state.is_active is True
    assert mod.state.is_ng_locked is False
    assert not any("リセット" in r for r in _csv_rows(mod))


def test_off_clears_ng_lock(stacks):
    mod = stacks
    mod.pb_on.press()
    _trigger_beam(mod, cmos_ok=False)
    if mod.__name__ in AUTO_CLEAR_MODULES:
        # 自動復帰前にOFFしても落ちること
        pass
    mod.pb_off.press()
    assert mod.state.is_active is False
    assert mod.state.is_ng_locked is False
    assert mod.led_yellow.is_active is False


def test_cleanup_outputs_turns_all_off(stacks):
    mod = stacks
    mod.pb_on.press()
    mod.led_green.on()
    mod.led_yellow.on()
    mod.relay_stop.on()
    mod.buzzer.on()
    mod.cleanup_outputs()
    assert mod.led_green.is_active is False
    assert mod.led_yellow.is_active is False
    assert mod.led_red.is_active is False
    assert mod.relay_stop.is_active is False
    assert mod.buzzer.is_active is False


def test_button_bounce_time_configured(stacks):
    mod = stacks
    assert mod.pb_on.bounce_time == mod.BOUNCE_TIME
    assert mod.pb_off.bounce_time == mod.BOUNCE_TIME
    assert mod.pb_reset.bounce_time == mod.BOUNCE_TIME
