import machine
import uasyncio
import ssd1306

# Init clock
rtc = machine.RTC()

# Init screen
oled = ssd1306.SSD1306_I2C(128, 32, machine.I2C(-1, machine.Pin(5), machine.Pin(4)))

# Define global variables (to be refactored?)
alarmTask = None
alarmTime = '--:--'

def main():
    # Create and run tasks in event loop. Every task is an async operation performed by module.
    # Need to be invoked manually each time after module restart via web repel.
    # This is because running event loop blocks option to send any command via web repel.

    loop = uasyncio.get_event_loop()
    loop.create_task(sync_time())
    loop.create_task(show_time())
    loop.create_task(uasyncio.start_server(handle_request, '192.168.0.87', 80))
    loop.run_forever()


async def sync_time():
    # Endless task function that sync RTC with NTP every one hour.

    while True:
        try:
            import ntptime
            import utime

            t = ntptime.time()
            t = t + (2* 3600) # Convert UTC to CEST
            tm = utime.localtime(t)
            rtc.datetime((tm[0], tm[1], tm[2], 0, tm[3], tm[4], tm[5], 0))
            
            currentTime = rtc.datetime()
            print('RTC time sync at: {:02d}:{:02d}:{:02d}'.format(currentTime[4], currentTime[5], currentTime[6]))
        except Exception:
            print('Time sync error')
            pass
        
        gc.collect()
        await uasyncio.sleep(3600)


async def show_time():
    # Endless task function that show time on the oled screen every one second.

    while True:
        try:
            global alarmTime
            currentTime = rtc.datetime()
            dateString = 'Date: {:02d}.{:02d}.{:04d}'.format(currentTime[2], currentTime[1], currentTime[0])
            timeString = 'Time: {:02d}:{:02d}:{:02d}'.format(currentTime[4], currentTime[5], currentTime[6])
            alarmString = 'Alarm: ' + alarmTime

            oled.fill(0)
            oled.text(dateString,0,0)
            oled.text(timeString,0,10)
            oled.text(alarmString,0,25)
            oled.show()
        except Exception:
            print('Show time error')
            pass
        
        gc.collect()
        await uasyncio.sleep(1)


async def handle_request(reader, writer):
    # Task function that host HTTP server, parse requests, and rout them to concrete functions (to be refactored).

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
    
    # Log request
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


def set_alarm(attrDict):
    # Function that add a new alarm task to the event loop.

    global alarmTime
    global alarmTask

    if alarmTask == None:
        hour = int(attrDict["hour"])
        minutes = int(attrDict["minutes"])
    
        loop = uasyncio.get_event_loop()
        alarmTime = '{:02d}:{:02d}'.format(hour, minutes)
        alarmTask = loop.create_task(make_coffee_at_time(hour, minutes))
    else:
        print('There is a running alarm already')
    
    gc.collect()


def cancel_alarm():
    # Function that remove existing alarm task from the event loop.

    global alarmTime
    global alarmTask

    if alarmTask != None:
        alarmTime = '--:--'
        alarmTask.cancel()
        alarmTask = None
    else:
        print('There is no running alarm')


def update_alarm(attrDict):
    cancel_alarm()
    set_alarm(attrDict)


async def make_coffee_at_time(alarmHour, alarmMinutes):
    # Task function that turn on coffee maker at next occurance of alarm hour.
    
    # Function calculate time diff between current hour and alarm hour. 
    # Then task is put into sleep for the calculated time diff. 
    # After wake up, it fire make_coffe() function.
    
    # While loop ensure that sleep time will not drift during a long period.

    while True:
        currentTime = rtc.datetime()
        timeToSleep = ((((24+alarmHour-currentTime[4])%24)*60+alarmMinutes-currentTime[5])*60-currentTime[6])
        
        if timeToSleep <= 60:
            await uasyncio.sleep(timeToSleep)
            break
        else:
            await uasyncio.sleep(int(timeToSleep/2))

    await make_coffee()

    global alarmTime
    global alarmTask
    alarmTime = '--:--'
    alarmTask = None

    gc.collect()


async def make_coffee():
    # Function that execute sequence of 'pushing' coffe maker's buttons. 
    # It's specific for my hardware setup.
    
    pinPump = machine.Pin(2, machine.Pin.OUT, value=1)
    pinHeater = machine.Pin(0, machine.Pin.OUT, value=1)

    pinHeater.value(0)          # push heater button
    await uasyncio.sleep(1)     # wait 1 sec
    pinHeater.value(1)          # release heater button
    await uasyncio.sleep(120)       # wait 2 min for a water to boil
    pinPump.value(0)            # push pump button
    await uasyncio.sleep(60)        # wait 1 min for a coffe to fill the mug
    pinPump.value(1)            # release pump button
    pinHeater.value(0)          # push heater button
    await uasyncio.sleep(1)     # wait 1 sec
    pinHeater.value(1)          # relesase heater button
    
    gc.collect()