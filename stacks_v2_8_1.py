# -*- coding: utf-8 -*-
"""
枚数検知センサシステム 制御プログラム (Ver 2.8.1)

v2.8.0 ベース + C-MOS チャンネル切替（機能フラグ）:
- ENABLE_MODE_SWITCH=False（既定）: 黄ボタン無効・常に GPIO16。v2.8.0 と同等
- True: 黄ボタンで GPIO16(3枚) / GPIO20(2枚) を切替
  - 切替時: ブザーと黄LEDを同期点滅（枚数回）
  - 3枚モード: 点滅後黄LED常時点灯 / 2枚モード: 点滅後消灯
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

# 後継機向け: True で黄ボタンによる 3枚/2枚 モード切替を有効化
ENABLE_MODE_SWITCH = False
MODE_BEEP_DURATION = 0.15  # 短いビープ（＝黄LED点灯幅）
MODE_BEEP_GAP = 0.15       # 無音／消灯ギャップ

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
pb_reset   = Button(22, pull_up=False, bounce_time=BOUNCE_TIME) # 押しボタン②: モード切替（フラグ時）
pb_off     = Button(6,  pull_up=False, bounce_time=BOUNCE_TIME) # 押しボタン③: OFF

# ビームは短パルスになり得るため bounce_time なし
beam_trig  = Button(12, pull_up=False) # ビームセンサ (EX-11EB-PN: 遮光時ON)
cmos_out1  = Button(16, pull_up=False) # C-MOS 出力1 (3枚ゾーン)
cmos_out2  = Button(20, pull_up=False) # C-MOS 出力2 (2枚ゾーン / 後継機)

# 出力デバイス
led_green  = LED(11)          # LED① 緑 (判定機能ON中)
led_yellow = LED(27)          # LED② 黄 (NG一時 / モード表示)
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
        self.sheet_mode = 3       # 3=GPIO16(3枚), 2=GPIO20(2枚)

state = SystemState()

# 判定の再入防止 & 1遮光=1判定
_judge_lock = threading.Lock()
_beam_armed = True
_shutting_down = False
_mode_feedback_busy = False
_mode_feedback_cancel = threading.Event()
# NG自動クリア用世代。OFF/再NGで進め、古いブザースレッドの clear を無効化する
_ng_lock_generation = 0

def pulse_output(device, duration):
    """指定されたデバイスを一定時間ONにして自動OFF (非同期処理用)"""
    device.on()
    time.sleep(duration)
    device.off()

def apply_mode_steady_yellow():
    """切替有効時の黄LED定常表示（3枚=点灯 / 2枚=消灯）"""
    if not ENABLE_MODE_SWITCH or not state.is_active or state.is_ng_locked:
        return
    if state.sheet_mode == 3:
        led_yellow.on()
    else:
        led_yellow.off()

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
        elif ENABLE_MODE_SWITCH:
            apply_mode_steady_yellow()
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
    """NG一時ロックを解除。expected_generation 指定時は世代一致時のみ。"""
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

def active_cmos():
    """判定に使う C-MOS 入力"""
    if ENABLE_MODE_SWITCH and state.sheet_mode == 2:
        return cmos_out2
    return cmos_out1

def cancel_mode_feedback():
    """モード切替フィードバックを中断要求"""
    _mode_feedback_cancel.set()

def _mode_switch_feedback():
    """枚数回の同期ビープ＋黄LED点滅のあと、モード定常表示"""
    global _mode_feedback_busy
    count = state.sheet_mode
    try:
        for _ in range(count):
            if _mode_feedback_cancel.is_set() or state.is_ng_locked:
                buzzer.off()
                break
            buzzer.on()
            led_yellow.on()
            time.sleep(MODE_BEEP_DURATION)
            if _mode_feedback_cancel.is_set() or state.is_ng_locked:
                buzzer.off()
                break
            buzzer.off()
            led_yellow.off()
            time.sleep(MODE_BEEP_GAP)
        if not state.is_ng_locked and not _mode_feedback_cancel.is_set():
            apply_mode_steady_yellow()
    finally:
        _mode_feedback_busy = False

def on_yellow_button():
    """押しボタン②: フラグ無効時は何もしない。有効時はモード切替"""
    global _mode_feedback_busy
    if not ENABLE_MODE_SWITCH:
        logging.info("【黄ボタン】モード切替は無効です（ENABLE_MODE_SWITCH=False）。")
        return
    if not state.is_active:
        return
    if state.is_ng_locked or _mode_feedback_busy:
        logging.info("【黄ボタン】NG処理中またはフィードバック中のため無視しました。")
        return

    state.sheet_mode = 2 if state.sheet_mode == 3 else 3
    label = f"{state.sheet_mode}枚モード (GPIO{'16' if state.sheet_mode == 3 else '20'})"
    logging.info(f"【モード切替】{label}")
    write_csv_log("システム状態", "モード切替", label)
    _mode_feedback_cancel.clear()
    _mode_feedback_busy = True
    threading.Thread(target=_mode_switch_feedback, daemon=True).start()

# ==========================================
# 4. 制御ロジック・イベントハンドラ
# ==========================================

def on_system_start():
    """押しボタン① (ON) 押下時"""
    if not state.is_active:
        cancel_mode_feedback()
        invalidate_ng_auto_clear()
        state.is_active = True
        state.is_ng_locked = False
        update_status_leds()
        logging.info("【システム起動】監視を開始します（ビーム遮光待ち）。")
        write_csv_log("システム状態", "起動", "ボタン①押下により監視開始")

def on_system_stop():
    """押しボタン③ (OFF) 押下時"""
    if state.is_active:
        cancel_mode_feedback()
        invalidate_ng_auto_clear()
        state.is_active = False
        state.is_ng_locked = False
        update_status_leds()
        relay_stop.off()
        buzzer.off()
        logging.info("【システム停止】監視を終了しました。")
        write_csv_log("システム状態", "停止", "ボタン③押下により監視停止")

def on_reset():
    """互換名: 黄ボタン処理へ委譲"""
    on_yellow_button()

def on_beam_released():
    """ビーム透過（遮光解除）で次製品の判定を再アーム"""
    global _beam_armed
    _beam_armed = True

def on_beam_pressed():
    """ビーム遮光。監視中のみ 1サイクル1判定 + 判定ロック。

    モード切替フィードバック中は判定しない（ブザー/黄LED競合防止）。
    """
    global _beam_armed
    if not state.is_active or state.is_ng_locked or _mode_feedback_busy:
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

    time.sleep(CHECK_DELAY)

    sensor = active_cmos()
    is_ok = sensor.is_pressed
    sensor_label = "C-MOS出力1(GPIO16)" if sensor is cmos_out1 else "C-MOS出力2(GPIO20)"

    if is_ok:
        logging.info(f"【判定結果】OK ({sensor_label} ON: 規定枚数)")
        if SAVE_OK_LOG:
            write_csv_log("枚数判定", "OK", f"適正厚み({sensor_label} ON)")
    else:
        cancel_mode_feedback()
        invalidate_ng_auto_clear()
        generation = _ng_lock_generation
        state.is_ng_locked = True
        reason = f"枚数異常/厚み規格外 ({sensor_label} OFF)"
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
    pb_reset.when_pressed = on_yellow_button
    beam_trig.when_pressed = on_beam_pressed
    beam_trig.when_released = on_beam_released

def initialize_runtime():
    """通電時の初期状態とハンドラ設定（出力は安全側へ）"""
    global _beam_armed, _shutting_down, _mode_feedback_busy, _ng_lock_generation
    _shutting_down = False
    _beam_armed = True
    _mode_feedback_busy = False
    _mode_feedback_cancel.clear()
    _ng_lock_generation = 0
    state.sheet_mode = 3

    relay_stop.off()
    buzzer.off()

    update_status_leds()
    bind_handlers()
    logging.info("==============================================")
    logging.info(" 枚数検知監視 プログラムVer 2.8.1 (自動復帰 + モード切替フラグ) ")
    logging.info(f" ENABLE_MODE_SWITCH={ENABLE_MODE_SWITCH}")
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
