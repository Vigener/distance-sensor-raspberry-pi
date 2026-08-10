# -*- coding: utf-8 -*-
"""gpiozero の最小フェイク（実機GPIOなしで stacks を import / 試験するため）"""


class FakeDigitalOutput:
    def __init__(self, pin, *args, **kwargs):
        self.pin = pin
        self.is_active = False
        self.on_count = 0
        self.off_count = 0

    def on(self):
        self.is_active = True
        self.on_count += 1

    def off(self):
        self.is_active = False
        self.off_count += 1


class FakeLED(FakeDigitalOutput):
    pass


class FakeOutputDevice(FakeDigitalOutput):
    pass


class FakeButton:
    def __init__(self, pin, pull_up=False, bounce_time=None, **kwargs):
        self.pin = pin
        self.pull_up = pull_up
        self.bounce_time = bounce_time
        self.is_pressed = False
        self.when_pressed = None
        self.when_released = None

    def press(self):
        """遮光/押下の立ち上がりを模擬"""
        was = self.is_pressed
        self.is_pressed = True
        if not was and self.when_pressed is not None:
            self.when_pressed()

    def release(self):
        """透過/離しの立ち下がりを模擬"""
        was = self.is_pressed
        self.is_pressed = False
        if was and self.when_released is not None:
            self.when_released()


# gpiozero 互換名
Button = FakeButton
LED = FakeLED
OutputDevice = FakeOutputDevice
