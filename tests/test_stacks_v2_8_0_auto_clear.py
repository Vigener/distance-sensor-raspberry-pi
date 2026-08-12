# -*- coding: utf-8 -*-
"""v2.8.0 / v2.8.1: NG後ブザー完了で自動復帰する契約"""
from datetime import datetime
from pathlib import Path

from tests.conftest import join_background_threads


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


def test_auto_clear_after_buzzer(stacks_auto_clear):
    mod = stacks_auto_clear
    mod.pb_on.press()
    _trigger_beam(mod, cmos_ok=False)
    assert mod.relay_stop.on_count >= 1
    join_background_threads()
    assert mod.state.is_ng_locked is False
    assert mod.led_yellow.is_active is False
    assert any("自動復帰" in r for r in _csv_rows(mod))


def test_can_judge_again_after_auto_clear(stacks_auto_clear):
    mod = stacks_auto_clear
    mod.pb_on.press()
    _trigger_beam(mod, cmos_ok=False)
    join_background_threads()
    assert mod.state.is_ng_locked is False

    relay_before = mod.relay_stop.on_count
    _trigger_beam(mod, cmos_ok=False)
    join_background_threads()
    assert mod.relay_stop.on_count > relay_before


def test_yellow_button_does_not_clear_or_log_reset(stacks_auto_clear, monkeypatch):
    mod = stacks_auto_clear
    mod.pb_on.press()

    # 自動クリアしないブザーにして、ロック中の黄ボタンを検証
    def pulse_only(generation=None):
        mod.pulse_output(mod.buzzer, mod.BUZZER_PULSE)

    monkeypatch.setattr(mod, "_buzzer_then_auto_clear", pulse_only)
    _trigger_beam(mod, cmos_ok=False)
    join_background_threads()
    assert mod.state.is_ng_locked is True

    mod.pb_reset.press()
    mod.pb_reset.release()
    assert mod.state.is_ng_locked is True
    assert not any(",リセット," in r for r in _csv_rows(mod))

    mod.clear_ng_lock("テスト用解除")
    assert mod.state.is_ng_locked is False


def test_ng_lock_blocks_until_cleared(stacks_auto_clear, monkeypatch):
    mod = stacks_auto_clear
    mod.pb_on.press()

    def pulse_only(generation=None):
        mod.pulse_output(mod.buzzer, mod.BUZZER_PULSE)

    monkeypatch.setattr(mod, "_buzzer_then_auto_clear", pulse_only)
    _trigger_beam(mod, cmos_ok=False)
    join_background_threads()
    assert mod.state.is_ng_locked is True
    relay_after_first = mod.relay_stop.on_count

    _trigger_beam(mod, cmos_ok=False)
    assert mod.relay_stop.on_count == relay_after_first

    mod.clear_ng_lock("テスト用解除")
    assert mod.state.is_ng_locked is False


def test_stale_auto_clear_after_off_on_does_not_unlock(stacks_auto_clear, monkeypatch):
    """OFF→ON→再NG のあと、古いブザースレッドの clear が新ロックを消さないこと"""
    mod = stacks_auto_clear
    mod.pb_on.press()
    mod.pb_on.release()
    held = []

    def hold_clear(generation):
        held.append(generation)

    monkeypatch.setattr(mod, "_buzzer_then_auto_clear", hold_clear)
    _trigger_beam(mod, cmos_ok=False)
    join_background_threads()
    assert mod.state.is_ng_locked is True
    gen1 = held[0]

    mod.pb_off.press()
    mod.pb_off.release()
    mod.pb_on.press()
    mod.pb_on.release()
    assert mod.state.is_active is True
    _trigger_beam(mod, cmos_ok=False)
    join_background_threads()
    assert mod.state.is_ng_locked is True
    assert len(held) == 2
    gen2 = held[1]
    assert gen2 != gen1

    mod.clear_ng_lock(expected_generation=gen1)
    assert mod.state.is_ng_locked is True
    mod.clear_ng_lock(expected_generation=gen2)
    assert mod.state.is_ng_locked is False
