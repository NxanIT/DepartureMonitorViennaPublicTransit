from datetime import datetime
from machine import Pin, SPI #type:ignore
import math, time

from micropython_ssd1322.xglcd_font import XglcdFont
from micropython_ssd1322.ssd1322 import Display

def delta_minutes(dtime_1:datetime, dtime_2:datetime):
    cutoff_expired = -2
    in_station_time = 30
    delta_time = (dtime_2-dtime_1).total_seconds()
    if delta_time<cutoff_expired: return -1
    if delta_time<in_station_time: return 0
    return int(delta_time+in_station_time)//60


class Monitor:
    def __init__(self, cs, dc, rst, spi, normal_spacing = 1, period_advanced_preview = 4):
        self.normal_spacing = normal_spacing

        #create display:
        CS = Pin(cs, Pin.OUT)
        DC = Pin(dc, Pin.OUT)
        RS = Pin(rst, Pin.OUT)
        self.Display = Display(spi, CS, DC, RS)
        
        #load font:
        self.font = XglcdFont('fonts/default_font.c', 10, 16)

        #variables for data displayed on monitor
        self.towards_data_displayed = {} #key - y-coordinate of text, value: text
        self.folding_ramp_displayed = {}
        self.countdown_displayed = {}
        
        #variables for 'in-station animation' and 'advanced-preview animation'
        self.in_station_animation_index = 0
        self.period_advanced_preview = period_advanced_preview
        
    
    def show_departures(self, departures, ref_time, platform=None, display_line=False, advanced_preview=False):
        max_char_towards = 19 if platform == None else 16
        text_start = [0, 8]
        if (platform!=None):
            platform_path = f'img/Gleis{platform}.mono'
            self.Display.draw_bitmap_mono(platform_path, 0, 0, 36, 64, invert=True)#TODO: catch no file in directory error
            text_start[0] = 40
        
        for i in range(len(departures)):
            departure = departures[i]
            countdown = delta_minutes(ref_time, departure['time'])
            
            if (countdown<0):
                continue #train no longer in station, continue
            
            grayscale_this_departure = 15
            if (advanced_preview and text_start[1]>=32 and len(departures)-1>i): 
                #we are in second line, advanced preview is enabled and a next departure exists

                t = time.ticks_ms() % (self.period_advanced_preview*math.pi*2000)
                grayscale_this_departure = max(math.floor(15.9*math.cos(t)), 0)
                grayscale_next_departure = -min(math.floor(15.9*math.cos(t)), 0)

                #display next_departure 
                next_departure = departures[i+1]
                self.__print_towards(*text_start, next_departure, display_line, 
                                     max_len=max_char_towards, gs=grayscale_next_departure)
                self.__print_foldingRamp(text_start[1], next_departure, gs=grayscale_next_departure)
                next_countdown = delta_minutes(next_departure['time'], ref_time)
                self.__print_countdown(text_start[1], next_countdown, gs=grayscale_next_departure)
            
            self.__print_towards(*text_start, departure, display_line, 
                                 max_len=max_char_towards, gs=grayscale_this_departure)
            self.__print_foldingRamp(text_start[1], departure, gs=grayscale_this_departure)
            self.__print_countdown(text_start[1], countdown, gs=grayscale_this_departure)

            text_start[1] += 32
            if (text_start[1]>=64):#breaks after second entry
                break
        
        self.Display.present()
        pass

    def __print_towards(self, x_start:int, y_start:int, departure, display_line, max_len=16, gs=15):
        towards = departure['towards'][:max_len]
        if (display_line):
            towards = (departure['line'] + ' ' + towards)[:max_len]
        if(y_start not in self.towards_data_displayed 
           or self.towards_data_displayed[y_start] != towards):
            self.Display.fill_rectangle(x_start, y_start, 215-x_start, 16, gs=0) #clear old data
            self.Display.draw_text(x_start, y_start, towards, self.font, gs=gs, spacing=self.normal_spacing)
            self.towards_data_displayed['y_start'] = towards
            return
        print("i did save resources. (towards)") #TODO: remove

    def __print_foldingRamp(self, y_start:int, departure, gs=15):
        flag_folding_ramp = departure['foldingRamp']
        #TODO: check if same text already displayed
        self.Display.fill_rectangle(216, y_start, 10, 16, gs=0) #clear old data
        if (flag_folding_ramp):
            self.Display.draw_text(216, y_start, '-', self.font, gs=gs)

    def __print_countdown(self, y_start:int, countdown:int, gs=15):
        self.Display.fill_rectangle(230, y_start, 256-230, 16, gs=0) #clear old data
        str_countdown = str(countdown)
        if (countdown==0):
            currently_in_station = ['*', '* '] #without leading spaces
            t = self.in_station_animation_index #old implementation: t = int(time.time()) % 2
            self.in_station_animation_index = 1 - self.in_station_animation_index
            str_countdown = currently_in_station[t]
        #TODO: check if same text already displayed
        if (len(str_countdown)<=1):
            self.Display.draw_text(240+self.normal_spacing, y_start, str_countdown, 
                                   self.font, gs=gs, spacing=self.normal_spacing)
            return
        self.Display.draw_text(230, y_start, str_countdown, 
                               self.font, gs=gs, spacing=self.normal_spacing)

    def cleanup(self):
        self.Display.cleanup()