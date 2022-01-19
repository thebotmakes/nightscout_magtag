# SPDX-FileCopyrightText: 2022 Tim C, written for Adafruit Industries
#
# SPDX-License-Identifier: Unlicense
"""
MagTag status display for James Webb Telescope
"""
import time
import json
import ssl
import board
import displayio
import terminalio
import supervisor
from adafruit_bitmap_font import bitmap_font
from adafruit_display_text import bitmap_label
import wifi
import socketpool
import alarm
import adafruit_requests as requests
from adafruit_magtag.magtag import MagTag

try:
    from secrets import secrets
except ImportError:
    print("WiFi secrets are kept in secrets.py, please add them there!")
    raise

# Set up where we'll be fetching data from
DATA_SOURCE = secrets['nightscout_url']

aio_username = secrets["aio_username"]
aio_key = secrets["aio_key"]
location = secrets.get("timezone", None)
TIME_URL = "https://io.adafruit.com/api/v2/%s/integrations/time/strftime?x-aio-key=%s" % (aio_username, aio_key)
TIME_URL += "&fmt=%25Y-%25m-%25d+%25H%3A%25M%3A%25S.%25L+%25j+%25u+%25z+%25Z"
CHEERLIGHTS_URL = "http://api.thingspeak.com/channels/1417/field/2/last.json"
COLOR_LOCATION = ['field2']

#comment all but one of the following SLEEP_TIME lines out, depending how often you want to update

# Update every minute
SLEEP_TIME = 1 * 60  # seconds

# Update every 5 minutes
#SLEEP_TIME = 5 * 60  # seconds

# Update once per hour
#SLEEP_TIME = 60 * 60  # seconds

# Update once per day
# SLEEP_TIME = 60 * 60 * 24 # seconds

# Whether to fetch live data or use cached
TEST_RUN = False
# Cached data, helpful when developing interface
# pylint: disable=line-too-long
FAKE_DATA = '{"date":1642418780116,"sgv":187,"delta":0,"sysTime":"2022-01-17T19:24:34.454Z","_id":"QsDUTF9eomzqcMZbfiPoVBay","device":"tomato","direction":"Flat","utcOffset":0, "mills": 1642447474454,"type": "sgv"'



def text_transform_direction(val):

    '''This was borrowed & adapted from Scott Hanselman's Pyportal code for Nighscout
    Displays the direction using an arrow instead of the wording'''

    if val == "Flat":
        new_val = "→"
    elif val == "SingleUp":
        new_val = "↑"
    elif val == "DoubleUp":
        new_val = "↑↑"
    elif val == "DoubleDown":
        new_val = "↓↓"
    elif val == "SingleDown":
        new_val = "↓"
    elif val == "FortyFiveDown":
        new_val = "→↓"
    elif val == "FortyFiveUp":
        new_val = "→↑"
    else:
        new_val = "---"
    return new_val

def neo_flash(times):

    '''This is used as an alarm if the blood sugar is too low'''

    x = 0
    while x < times:
        magtag.peripherals.neopixel_disable = False
        magtag.peripherals.neopixels.fill((255, 0, 0))
        time.sleep(0.1)
        magtag.peripherals.neopixel_disable = True
        time.sleep(0.1)
        x+=1

# Set up the MagTag with the JSON data parameters
magtag = MagTag(
    url=CHEERLIGHTS_URL,
    json_path=(COLOR_LOCATION),
)

if not TEST_RUN:
    print("Connecting to AP...")
    try:
        # wifi connect
        wifi.radio.connect(secrets["ssid"], secrets["password"])

        # Create Socket, initialize requests
        socket = socketpool.SocketPool(wifi.radio)
        requests = requests.Session(socket, ssl.create_default_context())
    except OSError:
        print("Failed to connect to AP. Rebooting in 3 seconds...")
        time.sleep(3)
        supervisor.reload()


if not TEST_RUN:
    try:
        print("Fetching JSON data from %s" % DATA_SOURCE)
        response = requests.get(DATA_SOURCE, timeout=30)
    except (RuntimeError, OSError) as e:
        print(e)
        print("Failed GET request. Rebooting in 3 seconds...")
        time.sleep(3)
        supervisor.reload()

    print("-" * 40)
    text_data = response.text

    json_data = text_data.split("\t")

    print("JSON Response: ", json_data)
    print("-" * 40)
    response.close()
else:
    json_data = json.loads(FAKE_DATA)

# update the labels to display values
bg_val_int = round(int(json_data[2])/18,1) #Nightscout send sgv data, this converts it to values I recognise
bg_val = str(bg_val_int)

if bg_val_int < 4.5:  #sound alarm if blood sugar is too low
    neo_flash(5)
else:
    pass

direction_get = json_data[3][1:-1]
direction_val = text_transform_direction(direction_get)


# set the_time
print("Fetching text from", TIME_URL)
try:
    current_time = requests.get(TIME_URL)
    print("-" * 40)
    print(current_time.text)
    print(current_time.text[11:16])
    print("-" * 40)

    time_val = str(current_time.text[11:16])
    print(time_val)

except (RuntimeError, OSError) as e:
    print(e)
    print("Failed GET request. Rebooting in 3 seconds...")
    time.sleep(3)
    supervisor.reload()


magtag.graphics.set_background("/bmps/nightscout.bmp")

magtag.add_text(
    text_font="/fonts/Impact-30.pcf",
    text_position=(200, 100),
    is_data=False,
)
# Display heading text below with formatting above
magtag.set_text(time_val,0)

# Formatting for the BG Headline
magtag.add_text(
    text_font="/fonts/Impact-24.pcf",
    text_position=(40, 25),
    is_data=False,
)

magtag.set_text("Blood Glucose",1)

# Formatting for the BG value
magtag.add_text(
    text_font="/fonts/Impact-24.pcf",
    text_position=(200, 25),
    is_data = False,
)

magtag.set_text(bg_val,2)


# Formatting for the direction label
magtag.add_text(
    text_font="/fonts/Impact-24.pcf",
    text_position=(40, 60),
    is_data = False,
)

magtag.set_text("Direction",3)

# Formatting for the direction value text
magtag.add_text(
    text_font="/fonts/Arial-BoldItalic-12-Complete.bdf",
    text_position=(200, 50),
    is_data = False,
)

magtag.set_text(direction_val,4)

try:
    value = magtag.fetch()
    print("Response is", value)
    magtag.peripherals.neopixel_disable = False
    color = int(value[1:], 16)
    magtag.peripherals.neopixels.fill(color)
    time.sleep(3)

except (ValueError, RuntimeError) as e:
    print("Some error occured, retrying! -", e)


# Create a an alarm that will trigger to wake us up
time_alarm = alarm.time.TimeAlarm(monotonic_time=time.monotonic() + SLEEP_TIME)

# Exit the program, and then deep sleep until the alarm wakes us.
alarm.exit_and_deep_sleep_until_alarms(time_alarm)
# Does not return, so we never get here.