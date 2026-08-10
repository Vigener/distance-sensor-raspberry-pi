# -*- coding: utf-8 -*-
"""
枚数検知センサシステム 制御プログラム (Ver 2.7.2)
追加機能: CSV形式の稼働・判定履歴ログ保存機能
"""

import time
import threading
import logging
import os
import csv
from datetime import datetime
from gpiozero import Button, LED, OutputDevice
from signal import pause

# ==========================================
# 1. 現場調整パラメータ & ログ設定
# ==========================================
CHECK_DELAY = 0.05    # ビーム遮光検知(ON)からC-MOSサンプリングまでの遅延時間 (秒)
RELAY_PULSE = 1.0     # 包装機 定停止リレーの導通時間 (秒)
BUZZER_PULSE = 3.0    # 警報ブザーの鳴動時間 (秒)
BOUNCE_TIME = 0.05     # ボタンのチャタリング防止用マスク時間 (秒)

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
            # 新規ファイル作成時はヘッダーを書き込む
            if not file_exists:
                writer.writerow(["日時", "イベント種別", "判定結果", "詳細"])

            writer.writerow([time_str, event_type, result, detail])
    except Exception as e:
        logging.error(f"CSV書き込み失敗: {e}")

# ==========================================
# 2. GPIO 割り当て設定 (Ver 2.4仕様準拠)
# ==========================================
pb_on      = Button(13, pull_up=False, bounce_time=BOUNCE_TIME) # 押しボタン①: ON
pb_reset   = Button(22, pull_up=False, bounce_time=BOUNCE_TIME) # 押しボタン②: リセット
pb_off     = Button(6,  pull_up=False, bounce_time=BOUNCE_TIME) # 押しボタン③: OFF

beam_trig  = Button(12, pull_up=False) # ビームセンサ (EX-11EB-PN: 遮光時ON)
cmos_out1  = Button(16, pull_up=False) # C-MOS 出力1 (適正厚みゾーン内でON / ゾーン外でOFF)
# cmos_out2 = Button(20, pull_up=False) # C-MOS 出力2 (次回別品種切替拡張用：今回は未使用)

# 出力デバイス
led_green  = LED(11)          # LED① 緑 (判定機能ON中)
led_yellow = LED(27)          # LED② 黄 (NG検出時保持)
led_red    = LED(9)           # LED③ 赤 (システム停止中)
relay_stop = OutputDevice(4)  # 包装機 定停止リレー (NO回路)
buzzer     = OutputDevice(17) # 警報ブザー

# ==========================================
# 3. 状態管理クラス
# ==========================================
class SystemState:
    def __init__(self):
        self.is_active = False    # システムが監視中かどうか
        self.is_ng_locked = False # NGを検知して停止ロック中かどうか

state = SystemState()

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

# ==========================================
# 4. 制御ロジック・イベントハンドラ
# ==========================================

def on_system_start():
    """押しボタン① (ON) 押下時"""
    if not state.is_active:
        state.is_active = True
        state.is_ng_locked = False
        update_status_leds()
        logging.info("【システム起動】監視を開始します（ビーム遮光待ち）。")
        write_csv_log("システム状態", "起動", "ボタン①押下により監視開始")

def on_system_stop():
    """押しボタン③ (OFF) 押下時"""
    if state.is_active:
        state.is_active = False
        state.is_ng_locked = False
        update_status_leds()
        relay_stop.off()
        buzzer.off()
        logging.info("【システム停止】監視を終了しました。")
        write_csv_log("システム状態", "停止", "ボタン③押下により監視停止")

def on_reset():
    """押しボタン② (リセット) 押下時"""
    if state.is_active and state.is_ng_locked:
        state.is_ng_locked = False
        update_status_leds()
        logging.info("【リセット受付】NG保持を解除。判定を再開します。")
        write_csv_log("システム状態", "リセット", "ボタン②押下によりNG解除")

def judge_wafer():
    """透過ビームセンサ遮光(ON/HIGH入力)時の判定ロジック"""
    if not state.is_active or state.is_ng_locked:
        return

    # 1. C-MOS設置位置に到達するまでの時間待ち
    time.sleep(CHECK_DELAY)

    # 2. C-MOSセンササンプリング (出力1がON ➔ 適正範囲OK / 出力1がOFF ➔ 規格外NG)
    is_ok = cmos_out1.is_pressed

    # 3. 最終判定
    if is_ok:
        # 正常処理 (適正範囲内)
        logging.info("【判定結果】OK (C-MOS出力1 ON: 規定枚数)")
        if SAVE_OK_LOG:
            write_csv_log("枚数判定", "OK", "適正厚み(C-MOS出力1 ON)")
    else:
        # 異常処理 (枚数不足または枚数過多により C-MOS出力1 OFF)
        state.is_ng_locked = True
        reason = "枚数異常/厚み規格外 (C-MOS出力1 OFF)"
        logging.warning(f"【異常検出】製品通過(遮光検出)後にC-MOSが {reason} を検知。ラインを停止します。")

        # CSVログ記録 (NG時)
        write_csv_log("枚数判定", "NG", reason)

        # 表示・出力更新
        update_status_leds()
        threading.Thread(target=pulse_output, args=(relay_stop, RELAY_PULSE)).start()
        threading.Thread(target=pulse_output, args=(buzzer, BUZZER_PULSE)).start()

# ==========================================
# 5. メインプログラム実行部
# ==========================================

def bind_handlers():
    """割り込みイベントの紐付け"""
    pb_on.when_pressed = on_system_start
    pb_off.when_pressed = on_system_stop
    pb_reset.when_pressed = on_reset
    beam_trig.when_pressed = judge_wafer

def initialize_runtime():
    """通電時の初期状態とハンドラ設定"""
    update_status_leds()
    bind_handlers()
    logging.info("==============================================")
    logging.info(" 枚数検知監視 プログラムVer 2.7.2 (C-MOSゾーン判定仕様) ")
    logging.info(" 保存先: " + LOG_DIR)
    logging.info(" ボタン①の入力を待っています... ")
    logging.info("==============================================")
    write_csv_log("システム状態", "通電起動", "プログラム初期化完了")

def main():
    initialize_runtime()
    try:
        pause()
    except KeyboardInterrupt:
        logging.info("手動終了を検出しました。")
        write_csv_log("システム状態", "手動終了", "KeyboardInterrupt")
    finally:
        cleanup_outputs()

if __name__ == "__main__":
    main()
