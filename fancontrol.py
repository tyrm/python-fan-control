import asyncio
import aiohttp.web
import RPi.GPIO as GPIO
from time import sleep

debug = True

# Fan Globals
fan_min = 20
fan_max = 100

temp_lower = 40
temp_max = 55

fanpin = 32

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

def renormalize(n, range1, range2):
    delta1 = range1[1] - range1[0]
    delta2 = range2[1] - range2[0]
    return (delta2 * (n - range1[0]) / delta1) + range2[0]



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

    print('Starting webserver at {listen}:{port}'.format(listen=listen,port=port))

    site = aiohttp.web.TCPSite(runner, listen, port)
    await site.start()


def main():
    # Setup Hardware
    GPIO.setwarnings(False)			#disable warnings
    GPIO.setmode(GPIO.BOARD)		#set pin numbering system
    GPIO.setup(fanpin,GPIO.OUT)

    fan_pwm = GPIO.PWM(fanpin,100)		#create PWM instance with frequency
    fan_pwm.start(0)				#start PWM of required Duty Cycle 

    fan_pwm.ChangeDutyCycle(50)

    # Start Loops
    loop = asyncio.get_event_loop()
    asyncio.ensure_future(start_webserver())
    asyncio.ensure_future(start_fan_control(fan_pwm))
    loop.run_forever()


if __name__ == '__main__':
    main()

