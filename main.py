import time                   # to use delay_ms()
import pycom                  # to use basic pycom functionality
import machine                # Interfaces with hardware components
from machine import Pin       # to use lopy4 pins
from network import WLAN      # to use wifi
from umqtt import MQTTClient  # to talk to adafruit using uMQTT

### USER SETUP ###
WATER_CHECK_INTERVAL = 1000 # ms
WATER_SEND_INTERVAL  = 5*60*1000 # ms

# Wifi
WIFI_SSID = "Dummy"
WIFI_PASS = "Dummier" # No this is not my regular password. :)

# Adafruit keys and feeds
AIO_SERVER = "io.adafruit.com"
AIO_PORT = 1883 # Even though Lopy4 supports SSL the insecure port is used to prevent a bug
AIO_USER = "Dummiest"
AIO_KEY = "Dummiester"
AIO_CLIENT_ID = "f52cb932-11bc-4d4c-b316-7a11e868922c" # any random GUID, don't use this one
AIO_CONTROL_FEED = "Dummiest/feeds/poweron" # Change Dummiest to your own usernamen on Adafruit
AIO_WATER_FEED = "Dummiest/feeds/water" # Change Dummiest to your own usernamen on Adafruit
############################

### FUNCTION DEFINITIONS ###
def check_water(): # Get a reading of the sensor and return if above threshold
    water_level = water.value() # read sensor value
    if water_level == 1:
        print('water detected')
        return 1
    else:
        print('No water detected')
        return 0

def send_water(): # Publish water level status to Adafruit
    # Make variables usable across functions
    global WATER_CHECK_INTERVAL
    global WATER_SEND_INTERVAL
    global last_checked_ticks
    global last_sent_ticks
    global water_level_old
    # Only check water if enough time has passed since last check
    if ((time.ticks_ms() - last_checked_ticks) < WATER_CHECK_INTERVAL):
        return
    # function continues if it's time so check water level
    water_level  = check_water() # get water level
    last_checked_ticks  = time.ticks_ms() # update last time for checking
    # Publish water status if it has changed
    if water_level != water_level_old:
        water_level_old = water_level
    # otherwise, check if it's time to publish
    elif ((time.ticks_ms() - last_sent_ticks) < WATER_SEND_INTERVAL):
        return
    # function continous if check water status changed or it's time to send update
    # Start publishing and tell me how it goes
    print("Publishing: {0} to {1} ... ".format(water_level, AIO_WATER_FEED), end='')
    try:
        client.publish(topic=AIO_WATER_FEED, msg=str(water_level))
        print("DONE")
    except Exception as e:
        print("FAILED")
    finally:
        last_sent_ticks = time.ticks_ms()

def startup(): # ye old cranking the lever
    # Check if it is possible to start machine as there is water
    if check_water():
        print("Starting machine .", end='') # tell me how it goes
        relay1.value(0) # close first relay, general power
        time.sleep_ms(500) # separate the closing of relays in time for the relay board to work properly
        relay2.value(0) # close second relay, general power
        print(".", end='') # tell me how it goes
        time.sleep_ms(1000) # wait for the machine to be powered before turning on the pump
        relay3.value(0) # close third relay, pump and solenoid
        time.sleep_ms(500) # Separation for relay board functionality
        relay4.value(0) # close fourth relay, pump and solenoid
        print(".", end='') # tell me how it goes
        time.sleep_ms(5000) # Let the pump run for some time to ensure adequate water level in the machine
        relay3.value(1) # Open pump and solenoid circuit
        relay4.value(1) # Open pump and solenoid circuit
        print(" Machine started") # tell me how it goes

def poweroff(): # Shut off machine as you probably got nice coffee now
    print("Powering off ... ", end = '') # tell me how it goes
    # close everything, no need to separate as springs are helping now
    relay1.value(1)
    relay2.value(1)
    relay3.value(1)
    relay4.value(1)
    print("Shutted down")

# Adafruit response function
def sub_cb(topic, msg):          # callback subroutine
    print((topic, msg))          # tell me what you are doing
    if msg == b"ON":             # If message says "ON" run the startup sequence
        startup()
    elif msg == b"OFF":          # If message says "OFF" run the poweroff sequence
        poweroff()
    else:                        # If Adafruit is malconfigured or something weird got through ..
        print("Unknown message") # ..tell me so
#############################

### Initialization ###
relay1  = Pin('P20', mode = Pin.OPEN_DRAIN, value=1)
relay2  = Pin('P21', mode = Pin.OPEN_DRAIN, value=1)
relay3  = Pin('P22', mode = Pin.OPEN_DRAIN, value=1)
relay4  = Pin('P23', mode = Pin.OPEN_DRAIN, value=1)
water = Pin('P16', mode = Pin.IN)
water_level_old  = water.value() # used for detecting sensor changes
last_random_sent_ticks = 0  # ms
last_checked_ticks = 0 # ms
last_sent_ticks = 0 # ms
##################

### STARTUP CONNECTIVITY ###
pycom.heartbeat(False) # stop flashing of LED and use it for connectivity feedback instead
pycom.rgbled(0x110000)  # Signal for: No wifi or Adafruit connection

# Connect to wifi
wlan = WLAN(mode=WLAN.STA)
wlan.connect(WIFI_SSID, auth=(WLAN.WPA2, WIFI_PASS), timeout=5000)
while not wlan.isconnected():
    machine.idle()
print("Wifi connection established")
pycom.rgbled(0xffd7000) # Signal for: Wifi established but no adafruit connection yet

# Use the MQTT protocol to connect to Adafruit IO
client = MQTTClient(AIO_CLIENT_ID, AIO_SERVER, AIO_PORT, AIO_USER, AIO_KEY)
# Subscribed messages will be delivered to this callback
client.set_callback(sub_cb)
client.connect()
client.subscribe(AIO_CONTROL_FEED)
print("Connected to %s, subscribed to %s topic" % (AIO_SERVER, AIO_CONTROL_FEED))

pycom.rgbled(0x001100) # Status green: online to Adafruit IO
######################

### MAIN PROGRAM ###
try:
    while 1: # main loop of running the controller
        client.check_msg() # Check if user wants machine on or off
        send_water() # send water level status
finally:                  # If an exception is thrown ...
    client.disconnect()   # ... disconnect the client and clean up.
    client = None
    wlan.disconnect()
    wlan = None
    pycom.rgbled(0x000011)# Signal for: Lost adafruit connection and stopping program
    print("Disconnected from Adafruit")
#####################