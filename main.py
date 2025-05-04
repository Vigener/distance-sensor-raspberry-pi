from gpiozero import LED
from time import sleep

# -------------------------------------------------
# GPIOデバイスの初期化
# -------------------------------------------------
class GPIODevices:
    def __init__(self):
        self.leds = {
            "orange": LED(10),
            "green": LED(14),
            "blue": LED(18),
            "red": LED(24)
        }
        self.relays = {
            "relay1": LED(4),
            "relay2": LED(17)
        }
        self.sensors = {
            "sensor1": LED(5),
            "sensor2": LED(6)
        }
        self.buzzer = LED(21)
        self.toggle_switch = LED(8)

# -------------------------------------------------
# メイン処理
# -------------------------------------------------
def main():
    gpio = GPIODevices()
    standby(gpio)
    wait_for_activation(gpio.toggle_switch)
    
    gpio.relays["relay1"].on()
    gpio.leds["green"].on()
    sleep(1)
    
    run_main_process(gpio)

# -------------------------------------------------
# サブ関数群
# -------------------------------------------------
def standby(gpio):
    gpio.leds["orange"].on()
    sleep(1)

def wait_for_activation(device):
    while not device.is_active:
        sleep(0.1)

def wait_for_deactivation(device):
    while device.is_active:
        sleep(0.1)

def handle_error(gpio):
    gpio.leds["blue"].off()
    gpio.relays["relay2"].on()
    gpio.buzzer.on()
    gpio.leds["red"].on()
    sleep(1)
    
    gpio.relays["relay2"].off()
    sleep(1)
    
    gpio.buzzer.off()
    sleep(3)
    gpio.leds["red"].off()

def run_main_process(gpio):
    while True:
        if gpio.sensors["sensor1"].is_active:
            sleep(0.1)
            
            if gpio.sensors["sensor2"].is_active:
                gpio.leds["blue"].on()
                wait_for_deactivation(gpio.sensors["sensor1"])
            else:
                handle_error(gpio)
                wait_for_deactivation(gpio.sensors["sensor1"])

# -------------------------------------------------
if __name__ == "__main__":
    main()
