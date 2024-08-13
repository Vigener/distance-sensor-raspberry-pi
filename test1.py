# -------------------------------------------------
# インポート
from gpiozero import LED, DistanceSensor
from time import sleep

# -------------------------------------------------
# GPIOの設定
# -------------------------------------------------
# LED: 17番ピン
# DistanceSensor: echo=23, trigger=24
led = LED(17)
sensor = DistanceSensor(echo=23, trigger=24, max_distance=5)

# -------------------------------------------------
# 変数の定義
# -------------------------------------------------
# 誤差の許容範囲
tolerance = 0.001 # 1mm


# -------------------------------------------------
# 関数の定義
# -------------------------------------------------
# １秒間で５回距離を測定し、その平均値を返す関数
def measure_distance_to_lane():
    d = 0
    for i in range(5):
        d += sensor.distance
        sleep(0.2)
    return d / 5

# はじめに、正しい枚数の製品を流し、そのときの距離を測定する関数
# def measure_distance_to_product_(distance_to_lane):
#     d = 0
#     # distance_to_laneを下に、製品が流れてくるのを待ち、正しい枚数の製品が流れてきたときの距離の測定を行う
#     # 測定の方法
#     # - 測定は、0.2秒ごとに行う
#     # 1. widthが前後tolerance以内のときは、製品が流れてきていないとし、流れてくるまで待つ
#     while True:
#         distance = sensor.distance
#         width = distance_to_lane - distance
#         if abs(width) <= tolerance:
#             sleep(0.2)
#             continue
#         # 2. widthがtolerance以上の値であり、かつ直前のdistanceとの差がtolerance以内のときは、製品が流れてきたとし、そのときのdistanceを製品との距離の平均値計算に用いる
#         if abs(width) > tolerance and abs(distance - sensor.distance) <= tolerance:
#             for i in range(5):
#                 d += sensor.distance
#                 sleep(0.2)
#             return d / 5
#         # 3. それ以外のときは、製品が流れてきていないとし、流れてくるまで待つ
#         sleep(0.2)

# 製品が流れてきたときの距離を測定する関数
count_products = 0 # 5回になったら終了
d_prod_sum = 0
def measure_distance_to_product(prev_distance):
    while True:
        distance = sensor.distance
        width = distance_to_lane - distance
        # 製品が流れてきていると判定する条件
        # |width| > tolerance かつ 直前のdistanceとの差がtolerance以内
        # わかりやすく言うと、測定値distanceがレーンとの距離とは考えられず、かつ連続してほぼ同じ値が得られたときにそれは、商品の厚さを表していると考えられる。
        if abs(width) > tolerance and abs(distance - prev_distance) <= tolerance:
            # 「製品が流れてきている」のときは、distanceを加算し、countをインクリメントする
            d_prod_sum += distance + prev_distance / 2
            count_products += 1
            if count_products == 5:
                return d_prod_sum / 5
            else:
                sleep(0.2)
                return measure_distance_to_product(distance)
            
        else:
            # 再帰的に関数を呼び出す
            sleep(0.2)
            return measure_distance_to_product(distance)
# def measure_distance_to_product_ver_prev1(prev_distance):
#     while True:
#         distance = sensor.distance
#         width = distance_to_lane - distance
#         # 「製品が流れてきていない(= |width| <= tolerance)」 もしくは、「|width| > tolerance かつ直前のdistanceとの差がtolerance以上」のときは、現在のdistanceをprev_distanceの引数として、再帰的に関数を呼び出す
#         if abs(width) <= tolerance or (abs(width) > tolerance and abs(distance - prev_distance) > tolerance):
#             # 再帰的に関数を呼び出す
#             sleep(0.2)
#             return measure_distance_to_product(distance)
#         else:
#             # 「製品が流れてきている」のときは、distanceを加算し、countをインクリメントする
#             d_prod_sum += distance + prev_distance / 2
#             count_products += 1
#             if count_products == 5:
#                 return d_prod_sum / 5
#             else:
#                 sleep(0.2)
#                 return measure_distance_to_product(distance)

# メインの処理
def process_distance():
    while True:
        distance = sensor.distance
        width = distance_to_lane - distance
        print('{:3f} m'.format(width))
        if (abs(width) <= tolerance) or (abs(width - thickness) <= tolerance):
            distance_is_ok = True
        else:
            distance_is_ok = False
        if distance_is_ok:
            if led.is_lit:
                led.off()
        else:
            if not led.is_lit:
                led.on()
        sleep(0.2)

# -------------------------------------------------
# 実行パート
# -------------------------------------------------
# レーンまでの距離を測定
distance_to_lane = measure_distance_to_lane()
# レーンまでの距離を表示
print('distance_to_lane: {:3f} m'.format(distance_to_lane)) 
# 製品までの距離を測定
distance_to_product = measure_distance_to_product(distance_to_lane)
# 製品の厚さを決定
thickness = distance_to_lane - distance_to_product
# メインの処理を実行
process_distance()



# -------------------------------------------------
# メモ
# ------------------------------------------------
# distance_to_lane = 0.264 m
# 3枚のとき: distance = 0.247 m
# 0.264 - 0.247 = 0.017 m