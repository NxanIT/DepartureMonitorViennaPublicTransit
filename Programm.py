import network #type:ignore
from datetime import timedelta
from machine import Pin, SPI, idle #type:ignore
import time

from Monitors import Monitor
import DataConversion

#configuration data - displaying options
display_mode0 = {'flag_show_platform_nr': True, 'flag_show_line':False}
display_mode1 = {'flag_show_platform_nr': False, 'flag_show_line':True}
display_modes = [display_mode0,display_mode1]
display_text_spacing = 1 #unit: pixel(s)

#configuration data - time constants, all times are expressed in seconds
TIME_BETWEEN_API_REQUESTS = 120 #time between updates of departure data
MIN_TIME_BETWEEN_API_REQUESTS = 15 #minimum time between API requests
ADVANCED_PREVIEW_ANIMATION_PERIOD = 4
UPDATE_PERIOD = 1 #should be at least 0.5*#(monitors), meassured time for update of one monitor is ~300ms

#configuration data - for input
LINES = ['U1','U2','U3','U4','U5','U6']
Pin_in_selectLine = [5,6,7]
Pin_in_selectStation = [8,9,10,17,18]
Pin_in_selectAdvancedPreview = 21 #TODO: solder
Pin_in_select_displaymode = 44 #TODO: solder

#configuration data - Pins for display connections
Pin_SCK = 48
Pin_COPI = 38
Pins_CS = (1,2)
Pins_DC = (4,12)
Pins_RST = (3,11)

#configuration data - network credentials
ssid = 'wlan-ssid'
password = 'wlan-pw'

class Programm:
    def __init__(self):
        ''' - configures GPIO pins and spi connection to monitors
        '''
        #setup GPIO
        self.p_selAdvPrev = Pin(Pin_in_selectAdvancedPreview,Pin.IN,Pin.PULL_UP)

        self.pl_lineSelect = []
        for pin_nr in Pin_in_selectLine:
            self.pl_lineSelect.append(Pin(pin_nr,Pin.IN,Pin.PULL_UP))
            
        self.pl_stationSelect = []
        for pin_nr in Pin_in_selectStation:
            self.pl_stationSelect.append(Pin(pin_nr,Pin.IN,Pin.PULL_UP))

        self.p_setDisplayMode = Pin(Pin_in_select_displaymode,Pin.IN,Pin.PULL_UP)

        self.RED_LED = Pin(46,Pin.OUT, value = 0)
        self.GREEN_LED = Pin(0,Pin.OUT, value = 0)
        self.BLUE_LED = Pin(45,Pin.OUT, value = 0)

        #init Displays
        spi = SPI(1, baudrate=250000, sck=Pin(48), mosi=Pin(38))
        min_len = min(map(len,[Pins_CS,Pins_DC,Pins_RST]))
        self.Monitors:list[Monitor] = []
        for i in range(min_len):
            cs_i = Pins_CS[i]
            dc_i = Pins_DC[i]
            rst_i = Pins_RST[i]
            self.Monitors.append(Monitor(cs_i,dc_i,rst_i,spi,
                                         normal_spacing=display_text_spacing,
                                         period_advanced_preview=ADVANCED_PREVIEW_ANIMATION_PERIOD))
        
        self.departure_data = None

    def update_RGB(self,r=None,g=None,b=None):
        ''' sets light value of internal rgb-LED. 
            The LED is active low, hence the inverted values of r,g,b are used.
        '''
        if(r!=None):
            self.RED_LED.value(r-1)
        if(g!=None):
            self.GREEN_LED.value(g-1)
        if(b!=None):
            self.BLUE_LED.value(b-1)

    def connect_WLAN(self):
        # Connect to WLAN
        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)
        try:
            if not wlan.isconnected():
                wlan.connect(ssid, password)
                while not wlan.isconnected():
                    idle()
        except OSError as err:
            #TODO print to monitor
            print('An error occured while trying to connect to WLAN. Message:',err)
            return False
        print('connected to WLAN.')
        return True
        
    def read_pin_input(self): #all entries inverted because of pullup-resistors
        self.AdvancedPrev = True if self.p_selAdvPrev.value()==0 else False

        list_lineSelect = [1 - pin_id.value() for pin_id in self.pl_lineSelect]
        self.line_selected = LINES[int(''.join(map(str,list_lineSelect)),2)]

        list_stationSelect = [1 - pin_id.value() for pin_id in self.pl_stationSelect]
        self.station_index = int(''.join(map(str,list_stationSelect)),2)

        self.displaymode = display_modes[1 - self.p_setDisplayMode.value()]
        print('new input is: advanced Prev:',self.AdvancedPrev ,'line:',self.line_selected, 'station_index: ',self.station_index,'displaymode: ',self.displaymode)

    def show_displays(self):
        if(self.departure_data==None or time.time()-self.time_last_API_request>TIME_BETWEEN_API_REQUESTS):
            self.read_pin_input()
            data = DataConversion.fetch(self.line_selected,self.station_index)
            while(data==None):
                self.update_RGB(r=1)
                time.sleep(MIN_TIME_BETWEEN_API_REQUESTS)
                self.update_RGB(r=0)
                data = DataConversion.fetch(self.line_selected,self.station_index)
            self.time_last_API_request = time.time()
            self.update_RGB(g=1)
            self.ref_time = DataConversion.get_refTime(data)
            #TODO: implement other display modes, then change this to below
            self.departure_data, self.platforms = DataConversion.get_departures(data,
                                                                platform_mode=True,
                                                                number_of_monitors=len(self.Monitors))
          #self.departure_data, self.platforms = DataConversion.get_departures(data,
          #                                                      platform_mode=self.displaymode['flag_show_platform_nr'],
          #                                                      number_of_monitors=len(self.Monitors))
            self.update_RGB(g=0)
        number_of_monitors = len(self.Monitors)
        assert(number_of_monitors==len(self.departure_data)==len(self.platforms)) #TODO:remove
        for i in range(len(self.Monitors)):
            ticks1 = time.ticks_ms()
            Mo = self.Monitors[i]
            current_departure_data = self.departure_data[i]
            delta_time_fetched = int(time.time()-self.time_last_API_request)
            current_ref_time = self.ref_time + timedelta(seconds=delta_time_fetched)
            current_platform = self.platforms[i]#TODO: if platforms is None, this throws an error
            Mo.show_departures(current_departure_data,current_ref_time,
                               current_platform,self.displaymode['flag_show_line'],self.AdvancedPrev)
            
            ticks2 = time.ticks_ms()
            delta_ms = time.ticks_diff(ticks2,ticks1)
            time.sleep_ms(UPDATE_PERIOD*1000/number_of_monitors-delta_ms)
            
    def cleanup(self):
        for Mo in self.Monitors:
            Mo.cleanup()
        







    
