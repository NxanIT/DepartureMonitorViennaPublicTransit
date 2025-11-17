import time
import sys
from machine import Pin #type:ignore

from Programm import Programm


WLM = Programm()
incr_val = 1
while not WLM.connect_WLAN():
    WLM.update_RGB(r = incr_val%2)
    incr_val += 1
    time.sleep(10)
WLM.update_RGB(r = 0)

def turn_off(_):
    WLM.update_RGB(r = 1,b = 1)
    WLM.cleanup()
    time.sleep(2)
    sys.exit(0)

while True:
    #TODO: add interrupt option via jumper GND - GPIO13
    P_Interrupt = Pin(13,Pin.IN,Pin.PULL_UP)
    P_Interrupt.irq(handler = turn_off, trigger = Pin.IRQ_FALLING)
    WLM.show_displays()