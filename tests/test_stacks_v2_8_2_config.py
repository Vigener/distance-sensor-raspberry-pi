# -*- coding: utf-8 -*-
"""v2.8.2: mode_switch.conf による ENABLE_MODE_SWITCH 読み込み"""
from pathlib import Path

from mode_switch_settings import read_enable_mode_switch, write_enable_mode_switch
from tests.conftest import join_background_threads


def test_conf_default_false(tmp_path):
    assert read_enable_mode_switch(tmp_path) is False


def test_conf_roundtrip(tmp_path):
    write_enable_mode_switch(True, tmp_path)
    assert read_enable_mode_switch(tmp_path) is True
    write_enable_mode_switch(False, tmp_path)
    assert read_enable_mode_switch(tmp_path) is False


def test_v282_loads_conf_false(load_stacks):
    mod = load_stacks("stacks_v2_8_2")
    assert mod.ENABLE_MODE_SWITCH is False
    mod.pb_on.press()
    before = mod.buzzer.on_count
    mod.pb_reset.press()
    mod.pb_reset.release()
    join_background_threads()
    assert mod.buzzer.on_count == before


def test_v282_loads_conf_true(load_stacks):
    mod = load_stacks("stacks_v2_8_2")
    write_enable_mode_switch(True, Path(mod._STACKS_DIR))
    mod.reload_mode_switch_config()
    assert mod.ENABLE_MODE_SWITCH is True
    mod.pb_on.press()
    mod.pb_on.release()
    assert mod.led_yellow.is_active is True  # 3枚モード定常
