import machine
from machine import Pin
from machine import RTC
import ssd1306
import uasyncio

# Init pins
pinPump = machine.Pin(2, machine.Pin.OUT, value=1)
pinHeater = machine.Pin(0, machine.Pin.OUT, value=1)

# Init clock
rtc = RTC()

#Init screen
i2c = machine.I2C(-1, machine.Pin(5), machine.Pin(4))
oled = ssd1306.SSD1306_I2C(128, 32, i2c)
oled.text('Hello World',0,0)
oled.show()

loop = uasyncio.get_event_loop()
alarmTask = None
alarmTime = '--:--:--'

def main():
    loop.create_task(sync_time())
    loop.create_task(show_time())
    loop.create_task(uasyncio.start_server(handle_request, '192.168.0.87', 80))
    loop.run_forever()

async def delayN(n):
    while (True):
        print("This is infinite loop: delay for {} seconds".format(n))
        await uasyncio.sleep(n)

async def sync_time():
    while True:
        try:
            import ntptime
            ntptime.settime()
            currentTime = rtc.datetime()
            print('RTC time sync at: {:02d}:{:02d}:{:02d}'.format(currentTime[4], currentTime[5], currentTime[6]))
        except Exception:
            print('Time sync error')
            pass
        gc.collect()
        await uasyncio.sleep(3600)

async def show_time():
    while True:
        try:
            utcTime = rtc.datetime()
            dateString = 'Date: {:02d}.{:02d}.{:04d}'.format(utcTime[2], utcTime[1], utcTime[0])
            timeString = 'Time: {:02d}:{:02d}:{:02d}'.format(utcTime[4], utcTime[5], utcTime[6])
            oled.fill(0)
            oled.text(dateString,0,0)
            oled.text(timeString,0,10)
            global alarmTime
            oled.text('Alarm: ' + alarmTime,0,25)
            oled.show()
        except Exception:
            print('Show time error')
            pass
        gc.collect()
        await uasyncio.sleep(1)

async def handle_request(reader, writer):
    # Get request headers and body
    data = await reader.read(-1)
    message = data.decode()
    print(message)
    

    # Get request method, path and parameters
    (method, path) = message.split(' ',2)[0:2]
    attrDict = {}
    if path.find('?') >= 0 :
        (path, attr) = path.split('?',2)[0:2]
        attrList = attr.split('&')
        for attrPair in attrList:
            (key, value) = attrPair.split('=',2)[0:2]
            attrDict.update({key: value})
    
    print('\n\rMethod:' + method)
    print('\n\rPath:' + path)
    print('\n\rAttributes dict:' )
    print(attrDict)
    
    
    # Send response
    response = ("HTTP/1.0 200 OK\r\n\r\n")
    await writer.awrite(response)
    writer.close()
    await writer.wait_closed()

    # Route function
    if path == '/coffee' and method == 'POST':
        await make_coffee()
    elif path == '/alarm' and method == 'POST':
        set_alarm(attrDict)
    elif path == '/alarm' and method == 'DELETE':
        cancel_alarm()
    elif path == '/alarm' and method == 'PATCH':
        update_alarm(attrDict)
    elif path == '/reset':
        machine.reset()
    gc.collect()

async def make_coffee():
    pinHeater.value(0)          # push heater button
    await uasyncio.sleep(1)     # wait 1 sec
    pinHeater.value(1)          # release heater button
    await uasyncio.sleep(120)       # wait for a water to boil
    pinPump.value(0)            # push pump button
    await uasyncio.sleep(60)        # wait for a coffe to fill the mug
    pinPump.value(1)            # release pump button
    pinHeater.value(0)          # push heater button
    await uasyncio.sleep(1)     # wait 1 sec
    pinHeater.value(1)          # relesase heater button

def set_alarm(attrDict):
    hour = int(attrDict["hour"])
    minutes = int(attrDict["minutes"])
    global alarmTime
    alarmTime = '{:02d}:{:02d}:00'.format(hour, minutes)
    global alarmTask
    alarmTask = loop.create_task(make_coffee_at_time(hour, minutes))
    
async def make_coffee_at_time(alarmHour, alarmMinutes):
    print('Setting alarm')
    while True:
        currentTime = rtc.datetime()
        print('Current time: {:02d}:{:02d}:{:02d}'.format(currentTime[4], currentTime[5], currentTime[6]))
        timeToSleep = ((((24+alarmHour-currentTime[4])%24)*60+alarmMinutes-currentTime[5])*60-currentTime[6])
        print('Time to sleep: ' + str(timeToSleep))
        if timeToSleep <= 60:
            await uasyncio.sleep(timeToSleep)
            break
        else:
            await uasyncio.sleep(int(timeToSleep/2))
    
    currentTime = rtc.datetime()
    print('Making coffee at: {:02d}:{:02d}:{:02d}'.format(currentTime[4], currentTime[5], currentTime[6]))
    global alarmTime
    alarmTime = 'in progress'
    await make_coffee()
    alarmTime = '--:--:--'

def cancel_alarm():
    print('Cancelling alarm')
    global alarmTime
    alarmTime = '--:--:--'
    global alarmTask
    alarmTask.cancel()

def update_alarm(attrDict):
    cancel_alarm()
    set_alarm(attrDict)