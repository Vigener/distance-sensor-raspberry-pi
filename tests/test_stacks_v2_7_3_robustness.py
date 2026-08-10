# -*- coding: utf-8 -*-
"""v2.7.3 固有の堅牢化テスト（v2.7.2 との差分仕様）"""
import signal

from datetime import datetime
from pathlib import Path


def _csv_rows(mod):
    date_str = datetime.now().strftime("%Y%m%d")
    path = Path(mod.LOG_DIR) / f"wafer_log_{date_str}.csv"
    if not path.exists():
        return []
    return path.read_text(encoding="utf-8-sig").strip().splitlines()


def test_beam_has_bounce_time(load_stacks):
    mod = load_stacks("stacks_v2_7_3")
    assert mod.beam_trig.bounce_time == mod.BOUNCE_TIME


def test_v2_7_2_beam_has_no_bounce_time(load_stacks):
    mod = load_stacks("stacks_v2_7_2")
    assert mod.beam_trig.bounce_time is None


def test_startup_forces_relay_and_buzzer_off(load_stacks):
    mod = load_stacks("stacks_v2_7_3")
    # initialize 前にONだったとしても、initialize_runtime でOFFになること
    mod.relay_stop.on()
    mod.buzzer.on()
    mod.initialize_runtime()
    assert mod.relay_stop.is_active is False
    assert mod.buzzer.is_active is False


def test_chatter_without_release_judges_only_once(load_stacks):
    """遮光解除前の多重立ち上がりは1回だけ判定する"""
    mod = load_stacks("stacks_v2_7_3")
    mod.pb_on.press()
    mod.cmos_out1.is_pressed = False

    mod.beam_trig.press()
    first_relay = mod.relay_stop.on_count
    assert mod.state.is_ng_locked is True
    assert first_relay >= 1

    # release せずに再度 press 相当（すでに pressed なので Fake は再発火しない）。
    # 明示的に when_pressed を二重呼び出ししてチャタを模擬する。
    mod.beam_trig.when_pressed()
    assert mod.relay_stop.on_count == first_relay


def test_release_rearms_for_next_product(load_stacks):
    mod = load_stacks("stacks_v2_7_3")
    mod.pb_on.press()

    mod.cmos_out1.is_pressed = True
    mod.beam_trig.press()
    mod.beam_trig.release()
    assert mod.state.is_ng_locked is False

    mod.cmos_out1.is_pressed = False
    mod.beam_trig.press()
    mod.beam_trig.release()
    assert mod.state.is_ng_locked is True


def test_sigterm_handler_cleans_outputs(load_stacks):
    mod = load_stacks("stacks_v2_7_3")
    mod.pb_on.press()
    mod.relay_stop.on()
    mod.buzzer.on()

    try:
        mod._handle_shutdown(signal.SIGTERM, None)
        assert False, "sys.exit される想定"
    except SystemExit as e:
        assert e.code == 0

    assert mod.relay_stop.is_active is False
    assert mod.buzzer.is_active is False
    assert mod.led_green.is_active is False
    assert any("シグナル終了" in r for r in _csv_rows(mod))
