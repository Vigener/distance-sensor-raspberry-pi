# raspberry pi 5
# 概要
# レーンに製品が流れてきたときに、製品の枚数を距離によって検知し、
# 3枚未満または4枚以上のときにはエラーを検知し、特定の電圧を流させる事によって機械を停止させるプログラム

# 仕様
# - 製品の枚数を検知するために、距離センサーを使用
# - 3枚未満または4枚以上のときにはエラーを検知
# - エラーを検知したときには、特定の電圧を流すことによって機械を停止させる
# - 3枚未満または4枚以上のときには、LEDを点灯させる
# - エラー検出中も、距離計測とチェックは継続する
# - エラーが発生したら、次の製品が流れてくるまで、led_redを点灯させ続ける


distance_to_lane = 10 # レーンまでの距離（仮）
distance = 0 # 検知する距離(センサーを用いる)

# GPIOの設定
import RPi.GPIO as GPIO
import time


while True:
    # 製品が流れてきていない状態（距離が'distance_to_lane'以上)のとき
    # もしくは
    # 枚数が3枚のとき
    if distance >= distance_to_lane or (distance_to_lane + 8) <= distance <= (distance_to_lane + 10):
        # 製品が流れてきていない状態のときの処理
        # 0.2秒後に再検知に戻る
        time.sleep(0.2)
        continue
        # LED 青（仮）
        GPIO.output(led_blue, GPIO.HIGH)
    else:
        # 製品が流れてきているかつ
        # 枚数が3枚未満または4枚以上のとき
        # LED 赤（仮）
        GPIO.output(led_red, GPIO.HIGH)
        # エラー検知
        # 特定の電圧を流すことによって機械を停止させる
        GPIO.output(voltage, GPIO.HIGH)
        # 0.5秒後に再検知に戻る
        time.sleep(0.2)
        while (distance > distance_to_lane):
            # 次の製品が流れてくるまでは、led_redを点灯させ続ける
            continue
        continue # 製品が流れてきたら、再検知に戻る

