# -*- coding: utf-8 -*-
"""
枚数検知センサシステム 制御プログラム (Ver 2.8.0)

v2.7.3 ベース:
- NG後の人手リセット必須を廃止
- 警報ブザー完了後に is_ng_locked を自動クリアし判定を再開
- 黄ボタン（旧リセット）は無効果（後継の切替用に配線のみ残す）
"""

import time
import threading
import logging
import os
import csv
import signal
import sys
from datetime import datetime
from gpiozero import Button, LED, OutputDevice
from signal import pause

# ==========================================
# 1. 現場調整パラメータ & ログ設定
# ==========================================
CHECK_DELAY = 0.05    # ビーム遮光検知(ON)からC-MOSサンプリングまでの遅延時間 (秒)
RELAY_PULSE = 1.0     # 包装機 定停止リレーの導通時間 (秒)
BUZZER_PULSE = 3.0    # 警報ブザーの鳴動時間 (秒) ※終了後にNGロック自動解除
BOUNCE_TIME = 0.05     # 押しボタンのチャタリング防止用マスク時間 (秒)。ビームには使わない

# CSVログ保存先設定
LOG_DIR = "/home/raspai/Desktop/logs"  # ログを保存するフォルダパス
SAVE_OK_LOG = False              # OK時の判定もCSVに記録するかどうか (FalseにするとNG時とステータス変化のみ記録)

# ログ出力ディレクトリの作成
if not os.path.exists(LOG_DIR):
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
    except Exception as e:
        print(f"ログフォルダ作成エラー: {e}")

# コンソール出力用ログの設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

# ==========================================
# CSVログ書き込み関数
# ==========================================
def write_csv_log(event_type, result, detail=""):
    """
    指定フォルダに日別のCSVファイル(wafer_log_YYYYMMDD.csv)で履歴を出力する
    項目: 日時, イベント種別, 判定結果, 詳細
    """
    now = datetime.now()
    date_str = now.strftime("%Y%m%d")
    time_str = now.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]  # ミリ秒まで記録
    filename = os.path.join(LOG_DIR, f"wafer_log_{date_str}.csv")

    file_exists = os.path.isfile(filename)

    try:
        with open(filename, mode='a', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["日時", "イベント種別", "判定結果", "詳細"])
            writer.writerow([time_str, event_type, result, detail])
    except Exception as e:
        logging.error(f"CSV書き込み失敗: {e}")

# ==========================================
# 2. GPIO 割り当て設定 (Ver 2.4仕様準拠)
# ==========================================
pb_on      = Button(13, pull_up=False, bounce_time=BOUNCE_TIME) # 押しボタン①: ON
pb_reset   = Button(22, pull_up=False, bounce_time=BOUNCE_TIME) # 押しボタン②: 未使用（v2.8.0）
pb_off     = Button(6,  pull_up=False, bounce_time=BOUNCE_TIME) # 押しボタン③: OFF

# ビームは短パルスになり得るため bounce_time なし（v2.7.2 と同じ）。多重判定は _beam_armed で抑止
beam_trig  = Button(12, pull_up=False) # ビームセンサ (EX-11EB-PN: 遮光時ON)
cmos_out1  = Button(16, pull_up=False) # C-MOS 出力1 (適正厚みゾーン内でON / ゾーン外でOFF)

# 出力デバイス
led_green  = LED(11)          # LED① 緑 (判定機能ON中)
led_yellow = LED(27)          # LED② 黄 (NG一時ロック中)
led_red    = LED(9)           # LED③ 赤 (システム停止中)
relay_stop = OutputDevice(4)  # 包装機 定停止リレー (NO回路)
buzzer     = OutputDevice(17) # 警報ブザー

# ==========================================
# 3. 状態管理クラス
# ==========================================
class SystemState:
    def __init__(self):
        self.is_active = False    # システムが監視中かどうか
        self.is_ng_locked = False # NG一時ロック（ブザー完了まで）

state = SystemState()

# 判定の再入防止 & 1遮光=1判定
_judge_lock = threading.Lock()
_beam_armed = True
_shutting_down = False
# NG自動クリア用世代。OFF/再NGで進め、古いブザースレッドの clear を無効化する
_ng_lock_generation = 0

def pulse_output(device, duration):
    """指定されたデバイスを一定時間ONにして自動OFF (非同期処理用)"""
    device.on()
    time.sleep(duration)
    device.off()

def update_status_leds():
    """システム状態に応じてLED表示を更新"""
    if not state.is_active:
        led_green.off()
        led_yellow.off()
        led_red.on()
    else:
        led_red.off()
        led_green.on()
        if state.is_ng_locked:
            led_yellow.on()
        else:
            led_yellow.off()

def cleanup_outputs():
    """終了時に全出力をOFF"""
    led_green.off()
    led_yellow.off()
    led_red.off()
    relay_stop.off()
    buzzer.off()

def invalidate_ng_auto_clear():
    """進行中のブザー自動クリアを無効化する（OFF / 再ロック時）"""
    global _ng_lock_generation
    _ng_lock_generation += 1

def clear_ng_lock(reason="ブザー完了による自動復帰", expected_generation=None):
    """NG一時ロックを解除して判定再開可能にする。

    expected_generation を渡した場合、現世代と一致するときだけ解除する。
    """
    if expected_generation is not None and expected_generation != _ng_lock_generation:
        logging.info(
            f"【自動復帰スキップ】世代不一致 (expected={expected_generation}, "
            f"current={_ng_lock_generation})"
        )
        return
    if not state.is_ng_locked:
        return
    state.is_ng_locked = False
    update_status_leds()
    logging.info(f"【自動復帰】NGロックを解除。判定を再開します（{reason}）。")
    write_csv_log("システム状態", "自動復帰", reason)

def _buzzer_then_auto_clear(generation):
    """警報ブザー後に、同一世代のNGロックだけ自動クリア"""
    pulse_output(buzzer, BUZZER_PULSE)
    clear_ng_lock(expected_generation=generation)

# ==========================================
# 4. 制御ロジック・イベントハンドラ
# ==========================================

def on_system_start():
    """押しボタン① (ON) 押下時"""
    if not state.is_active:
        invalidate_ng_auto_clear()
        state.is_active = True
        state.is_ng_locked = False
        update_status_leds()
        logging.info("【システム起動】監視を開始します（ビーム遮光待ち）。")
        write_csv_log("システム状態", "起動", "ボタン①押下により監視開始")

def on_system_stop():
    """押しボタン③ (OFF) 押下時"""
    if state.is_active:
        invalidate_ng_auto_clear()
        state.is_active = False
        state.is_ng_locked = False
        update_status_leds()
        relay_stop.off()
        buzzer.off()
        logging.info("【システム停止】監視を終了しました。")
        write_csv_log("システム状態", "停止", "ボタン③押下により監視停止")

def on_reset():
    """押しボタン②: v2.8.0 では無効（リセット不要）"""
    logging.info("【黄ボタン】v2.8.0 では無効です（リセット操作は不要）。")

def on_beam_released():
    """ビーム透過（遮光解除）で次製品の判定を再アーム"""
    global _beam_armed
    _beam_armed = True

def on_beam_pressed():
    """ビーム遮光。監視中のみ 1サイクル1判定 + 判定ロック。

    非監視中は disarm しない（解放エッジ欠落時に永遠に検知不能になるのを防ぐ）。
    """
    global _beam_armed
    if not state.is_active or state.is_ng_locked:
        return
    if not _beam_armed:
        return
    if not _judge_lock.acquire(blocking=False):
        return

    _beam_armed = False
    try:
        _judge_wafer_locked()
    finally:
        _judge_lock.release()

def judge_wafer():
    """互換用エントリ（直接呼び出し時）。通常は on_beam_pressed 経由。"""
    on_beam_pressed()

def _judge_wafer_locked():
    """透過ビームセンサ遮光時の判定本体（呼び出し側がロック取得済み）"""
    if not state.is_active or state.is_ng_locked:
        return

    # 1. C-MOS設置位置に到達するまでの時間待ち
    time.sleep(CHECK_DELAY)

    # 2. C-MOSセンササンプリング
    is_ok = cmos_out1.is_pressed

    # 3. 最終判定
    if is_ok:
        logging.info("【判定結果】OK (C-MOS出力1 ON: 規定枚数)")
        if SAVE_OK_LOG:
            write_csv_log("枚数判定", "OK", "適正厚み(C-MOS出力1 ON)")
    else:
        invalidate_ng_auto_clear()
        generation = _ng_lock_generation
        state.is_ng_locked = True
        reason = "枚数異常/厚み規格外 (C-MOS出力1 OFF)"
        logging.warning(
            f"【異常検出】製品通過(遮光検出)後にC-MOSが {reason} を検知。ラインを停止します。"
        )
        write_csv_log("枚数判定", "NG", reason)
        update_status_leds()
        threading.Thread(target=pulse_output, args=(relay_stop, RELAY_PULSE), daemon=True).start()
        threading.Thread(
            target=_buzzer_then_auto_clear, args=(generation,), daemon=True
        ).start()

# ==========================================
# 5. メインプログラム実行部
# ==========================================

def bind_handlers():
    """割り込みイベントの紐付け"""
    pb_on.when_pressed = on_system_start
    pb_off.when_pressed = on_system_stop
    pb_reset.when_pressed = on_reset
    beam_trig.when_pressed = on_beam_pressed
    beam_trig.when_released = on_beam_released

def initialize_runtime():
    """通電時の初期状態とハンドラ設定（出力は安全側へ）"""
    global _beam_armed, _shutting_down, _ng_lock_generation
    _shutting_down = False
    _beam_armed = True
    _ng_lock_generation = 0

    relay_stop.off()
    buzzer.off()

    update_status_leds()
    bind_handlers()
    logging.info("==============================================")
    logging.info(" 枚数検知監視 プログラムVer 2.8.0 (NG後自動復帰 / 黄ボタン無効) ")
    logging.info(" 保存先: " + LOG_DIR)
    logging.info(" ボタン①の入力を待っています... ")
    logging.info("==============================================")
    write_csv_log("システム状態", "通電起動", "プログラム初期化完了")

def _handle_shutdown(signum, frame):
    """SIGTERM / SIGINT で出力を落として終了"""
    global _shutting_down
    if _shutting_down:
        return
    _shutting_down = True
    signame = signal.Signals(signum).name if hasattr(signal, "Signals") else str(signum)
    logging.info(f"終了シグナルを受信しました ({signame})。出力を安全側にします。")
    write_csv_log("システム状態", "シグナル終了", signame)
    cleanup_outputs()
    sys.exit(0)

def main():
    initialize_runtime()
    signal.signal(signal.SIGTERM, _handle_shutdown)
    signal.signal(signal.SIGINT, _handle_shutdown)
    try:
        pause()
    except KeyboardInterrupt:
        logging.info("手動終了を検出しました。")
        write_csv_log("システム状態", "手動終了", "KeyboardInterrupt")
    finally:
        cleanup_outputs()

if __name__ == "__main__":
    main()
