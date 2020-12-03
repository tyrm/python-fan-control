"""This script monitors cpu temp and controls a fan with PWM on GPIO pin 12.
"""

import asyncio
import aiohttp.web
import os
import requests
import time
import RPi.GPIO as GPIO

DEBUG = True

FAN_MIN = 20
FAN_MAX = 255

TEMP_LOW = 35
TEMP_HIGH = 55

PRESENSE_PIN = 16

clock_pin = 6
data_pin  = 5
latch_pin = 12

def get_remote_temp(name):
    """Get the core temperature from remote fan agent.
    Parameters:
        name (str): hostname of the remote
    Returns:
        int: The core temperature in thousanths of degrees Celsius.
    """
    data = requests.get(url="http://{}:9768/temp".format(name)).json()
    return data["temp"]



def get_temp():
    """Get the core temperature.
    Read file from /sys to get CPU temp in temp in C *1000
    Returns:
        int: The core temperature in thousanths of degrees Celsius.
    """
    with open('/sys/class/thermal/thermal_zone0/temp') as temp:
        temp_str = temp.read()

    try:
        return int(temp_str) / 1000
    except (IndexError, ValueError,) as ex:
        raise RuntimeError('Could not parse temperature output.') from ex


def hat_present():
    """Detect control hat presense.
    Check that GPIO pin 16 is pulled high. This indicates the presence of the
    control hat.
    Returns:
        bool: Control hat present.
    """
    if GPIO.input(PRESENSE_PIN) == 1:
        return True
    return False


def renormalize(val, range1, range2):
    """Rescale value from range1 to range2.
    Parameters:
        val (float): value to be rescaled
        range1 (float[2]): initial value range
        range2 (float[2]): new range to scale value to
    Returns:
        float:
    """
    delta1 = range1[1] - range1[0]
    delta2 = range2[1] - range2[0]
    return (delta2 * (val - range1[0]) / delta1) + range2[0]

def shift_out(level):
    for x in range(0, 8):
        the_bit = (level >> 7-x) & 1

        if the_bit:
            GPIO.output(data_pin, GPIO.HIGH)
        else:
            GPIO.output(data_pin, GPIO.LOW)

        GPIO.output(clock_pin, GPIO.HIGH)
        time.sleep(.001)
        GPIO.output(clock_pin, GPIO.LOW)
        time.sleep(.001)

    GPIO.output(latch_pin, GPIO.LOW)
    time.sleep(.001)
    GPIO.output(latch_pin, GPIO.HIGH)
    time.sleep(.001)

async def http_hat(request):
    #pylint: disable=unused-argument
    data = {
        'hat': hat_present()
    }
    return aiohttp.web.json_response(data)


async def http_temp(request):
    #pylint: disable=unused-argument
    data = {
        'temp': get_temp()
    }
    return aiohttp.web.json_response(data)


async def start_fan_control():
    # get buddy config
    buddy_name = os.environ.get('BUDDY')

    while True:
        # Get Buddy's Temp
        buddy_temp = 0
        if buddy_name is not None:
            try:
                buddy_temp = get_remote_temp(buddy_name)
            except:
                if DEBUG:
                    print("could not get buddy temp")
                pass

        # Get my temp
        using_temp = "M"
        temp = get_temp()

        # Use Higher Value
        if buddy_temp > temp:
            using_temp = "B"
            temp = buddy_temp

        cycles = 0

        if temp < TEMP_LOW:
            cycles = FAN_MIN
        elif temp > TEMP_HIGH:
            cycles = FAN_MAX
        else:
            cycles = int(renormalize(temp, [TEMP_LOW, TEMP_HIGH], [FAN_MIN, FAN_MAX]))

        shift_out(cycles)
        if DEBUG:
            print("{} {}C {}".format(using_temp, temp, cycles))

        await asyncio.sleep(15)


async def start_webserver(app):
    runner = aiohttp.web.AppRunner(app)
    await runner.setup()
    listen = '0.0.0.0'
    port = 9768

    print('Starting webserver at {listen}:{port}'.format(listen=listen, port=port))

    site = aiohttp.web.TCPSite(runner, listen, port)
    await site.start()


def main():
    # Setup Hardware
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)

    GPIO.setup(PRESENSE_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

    GPIO.setup(clock_pin, GPIO.OUT)
    GPIO.setup(data_pin, GPIO.OUT)
    GPIO.setup(latch_pin, GPIO.OUT)

    GPIO.output(clock_pin, GPIO.LOW)
    GPIO.output(data_pin, GPIO.LOW)
    GPIO.output(latch_pin, GPIO.HIGH)


    # Web
    app = aiohttp.web.Application()
    app.router.add_get('/hat', http_hat)
    app.router.add_get('/temp', http_temp)

    # Start Loops
    loop = asyncio.get_event_loop()
    asyncio.ensure_future(start_webserver(app))
    if hat_present():
        print("Found Control Hat")
        asyncio.ensure_future(start_fan_control())
    loop.run_forever()


if __name__ == '__main__':
    main()
