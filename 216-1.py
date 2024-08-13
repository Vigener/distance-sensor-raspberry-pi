from gpiozero import PWMLED
from signal import pause

led = PWMLED(17)

led.blink(on_time=1, off_time=1)

pause()

