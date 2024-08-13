from gpiozero import LED, DistanceSensor
from time import sleep

led = LED(17)
sensor = DistanceSensor(echo=23, trigger=24, max_distance=5)

while True:
    print('{:3f} m'.format(sensor.distance)) # sensor.distanceは距離を返す
    if sensor.distance < 0.2:
        if not led.is_lit:
            led.on()
            print('LED ON')
    else:
        if led.is_lit:
            led.off()
            print('LED OFF')
    sleep(0.2)