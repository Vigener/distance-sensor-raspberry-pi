from gpiozero import LED
from signal import pause

led = LED(17)

led.on()

pause()