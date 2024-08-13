# 距離を測定するプログラム

from gpiozero import DistanceSensor
from time import sleep

sensor = DistanceSensor(echo=23, trigger=24, max_distance=5)
# echoは距離を受信するピン、triggerは距離を送信するピン、max_distanceは最大距離

while True:
    print('{:3f} m'.format(sensor.distance)) # sensor.distanceは距離を返す
    sleep(1)