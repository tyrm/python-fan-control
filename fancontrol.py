import asyncio
import aiohttp.web
import RPi.GPIO as GPIO

debug = True

# Fan Globals
fan_min = 20
fan_max = 100

temp_lower = 40
temp_max = 55

fan_pin = 32

# Hat Globals
presense_pin = 36

# Web Globals
app = aiohttp.web.Application()


def get_temp():
    """Get the core temperature.
    Read file from /sys to get CPU temp in temp in C *1000
    Returns:
        int: The core temperature in thousanths of degrees Celsius.
    """
    with open('/sys/class/thermal/thermal_zone0/temp') as f:
        temp_str = f.read()

    try:
        return int(temp_str) / 1000
    except (IndexError, ValueError,) as e:
        raise RuntimeError('Could not parse temperature output.') from e


def hat_present():
    if GPIO.input(presense_pin) == 1:
        return True
    return False


def renormalize(n, range1, range2):
    delta1 = range1[1] - range1[0]
    delta2 = range2[1] - range2[0]
    return (delta2 * (n - range1[0]) / delta1) + range2[0]


async def http_hat(request):
    data = {
        'hat': hat_present()
    }
    return aiohttp.web.json_response(data)


app.router.add_get('/hat', http_hat)


async def http_temp(request):
    data = {
        'temp': get_temp()
    }
    return aiohttp.web.json_response(data)


app.router.add_get('/temp', http_temp)


async def start_fan_control(fan_pwm):
    while True:
        temp = get_temp()

        cycles = 0

        if temp < temp_lower:
            cycles = fan_min
        elif temp > temp_max:
            cycles = fan_max
        else:
            cycles = int(renormalize(temp, [temp_lower, temp_max], [fan_min, fan_max]))

        fan_pwm.ChangeDutyCycle(cycles)
        if debug:
            print("{}C {}".format(temp, cycles))

        await asyncio.sleep(15)


async def start_webserver():
    runner = aiohttp.web.AppRunner(app)
    await runner.setup()
    listen = '0.0.0.0'
    port = 8080

    print('Starting webserver at {listen}:{port}'.format(listen=listen, port=port))

    site = aiohttp.web.TCPSite(runner, listen, port)
    await site.start()


def main():
    # Setup Hardware
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BOARD)

    GPIO.setup(fan_pin, GPIO.OUT)
    GPIO.setup(presense_pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

    fan_pwm = GPIO.PWM(fan_pin, 100)
    fan_pwm.start(0)

    if hat_present():
        print("Found Control Hat")

    # Start Loops
    loop = asyncio.get_event_loop()
    asyncio.ensure_future(start_webserver())
    asyncio.ensure_future(start_fan_control(fan_pwm))
    loop.run_forever()


if __name__ == '__main__':
    main()

