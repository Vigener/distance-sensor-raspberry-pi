# -------------------------------------------------
# インポート
from gpiozero import LED, DistanceSensor
from time import sleep

# -------------------------------------------------
# GPIOの設定
# -------------------------------------------------
LED_ORANGE = LED(10) # LED 橙: 10番ピン
LED_GREEN = LED(14) # LED 緑: 14番ピン
LED_BLUE = LED(18) # LED 青: 18番ピン
LED_RED = LED(24) # LED 赤: 24番ピン

RELAY_1 = LED(4) # リレー1: 4番ピン
RELAY_2 = LED(17) # リレー2: 17番ピン

# 製品が流れてきたことを検知するための距離センサー
# 0or1のみなのでLEDに接続
SENSOR_1 = LED(5)
SENSOR_2 = LED(6)

BUZZER = LED(21) # ブザー: 22番ピン

TOGGLE_SWITCH = LED(8) # トグルスイッチ: 8番ピン

# -------------------------------------------------


# -------------------------------------------------
# メイン処理
# -------------------------------------------------
# LED 橙を点灯
# ラズパイ スタンバイ表示
def main():
    LED_ORANGE.on() # ラズパイ スタンバイ表示
    sleep(1)
    wait_for_sensor_activation(TOGGLE_SWITCH) # トグルスイッチがONになるまで待機
    RELAY_1.on() # リレー1をONにする
    LED_GREEN.on() # ラズパイ 動作中表示
    sleep(1)
    run_main_process() # 動作中のメイン処理を実行

# --------------------------------------------------


# -------------------------------------------------
# 関数の定義
# -------------------------------------------------
# GPIO8がHIGHになったら次の処理にすすむ
def wait_for_sensor_activation(sensor):
    while True:
        if sensor.is_active:
            break
        sleep(0.1)

def wait_for_sensor_deactivation(sensor):
    while True:
        if not sensor.is_active:
            break
        sleep(0.1)
    
def sensor_is_active(sensor):
    return sensor.is_active

# エラー時の処理
def handle_error():
    LED_BLUE.off() # LED 青を消灯させる
    RELAY_2.on() # リレー2をONにする
    BUZZER.on() # ブザーをONにする
    LED_RED.on() # LED 赤を点灯させる
    sleep(1) # 1秒待機
    RELAY_2.off() # リレー2をOFFにする
    sleep(1) # 1秒待機
    BUZZER.off() # ブザーをOFFにする
    sleep(3) # 3秒待機
    LED_RED.off() # LED 赤を消灯させる

def run_main_process():
    while True:
        # センサー1がアクティブなとき
        if sensor_is_active(SENSOR_1):
            
            sleep(0.1) # 0.1秒待機
            
            if sensor_is_active(SENSOR_2):
                # 正しく製品が流れてきたときの処理
                
                # LED 青を点灯させ続ける
                LED_BLUE.on() 
                
                # センサー1がオフになったことを確認したら最初に戻る
                wait_for_sensor_deactivation(SENSOR_1)
            else:
                # 流れてきた製品が2枚以下のときの処理
                
                # エラー検知時の処理を実行
                handle_error()
                
                # センサー1がオフになったことを確認したら最初に戻る
                wait_for_sensor_deactivation(SENSOR_1)

if __name__ == "__main__":
    main()
