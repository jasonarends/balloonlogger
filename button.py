#!/usr/bin/env python2.7
# button.py
# daemon to watch for button presses and flip value in shm temp file
# so the data gathering process knows whether it should run

import RPi.GPIO as GPIO
import math, threading, time, os, pickle, sys, signal, syslog
import bmp280, csv, string, random
from subprocess import call
from picamera import PiCamera

def signalHandler(signal, frame):
	#signalHandler catches ctrl-C and cleanly exits
	GPIO.output(blueLED, False)
	GPIO.cleanup()
	syslog.syslog('Caught SIGTERM, exiting.')
	sys.exit(0)

#signal.signal(signal.SIGINT, signalHandler)
signal.signal(signal.SIGTERM, signalHandler)

def pickleReader(f):
	#read a variable dumped to a pickle file stored in shared memory
	try:
		with open('/dev/shm/' + f,'r') as pkl_file:
			data = pickle.load(pkl_file)

	except IOError as e:
		data = False
		syslog.syslog('Pickle error: %s' %e)

	return data

def pickleWriter(f, data):
	#dump a variable to a pickle file
	try:
		with open('/dev/shm/' + f, 'w') as pkl_file:
			pickle.dump(data, pkl_file)

	except IOError as e:
		syslog.syslog('Pickle write error: %s' %e)

def handle(pin):
	#handles a button press on a gpio pin, and flips logData to start/stop logging
	global logData, greenLED, redLED, blueLED

	syslog.syslog('Button pressed.')

	logData = not pickleReader('button.pickle') #since each button press flips it, we want opposite value of what's stored

	syslog.syslog('logData changed to %s' %logData)
	GPIO.output(blueLED, False) #no blue, just green or red after button
	GPIO.output(greenLED, logData)
	GPIO.output(redLED, not logData)

	pickleWriter('button.pickle',logData)

	if logData:
		# start the logLoop in a separate thread so this one can go back to handling button presses
		t = threading.Thread(target=logLoop)
		t.daemon = True
		t.start()
		#logLoop()

def gpioSetup():
	#init for GPIO
	global buttonPin, redLED, greenLED, blueLED

	#use broadcom numbers, not board pins
	GPIO.setmode(GPIO.BCM)

	buttonPin = 23
	redLED = 17
	greenLED = 27
	blueLED = 22

	GPIO.setup(buttonPin, GPIO.IN, pull_up_down=GPIO.PUD_UP) # buttonPin is an input, with a pullup resistor to set it to high by default. pressing button changes it to low
	GPIO.setup(redLED, GPIO.OUT)
	GPIO.setup(greenLED, GPIO.OUT)
	GPIO.setup(blueLED, GPIO.OUT)

	GPIO.output([greenLED,redLED,blueLED], True) #white on init
	GPIO.add_event_detect(23, GPIO.FALLING, handle, bouncetime=250)

def initPressure():
	#syslog.syslog('initPressure')
	pklPress = pickleReader('zeroPress.pickle')
	if not pklPress: # pickle reader should return 'False' if it's not set yet, so read it
		zeroPress, temp = getBCM280()
		pickleWriter('zeroPress.pickle',zeroPress)
	else:
		zeroPress = pklPress

	return zeroPress

def getDS18b20():
	#syslog.syslog('getDS18b20')
	with open('/sys/bus/w1/devices/28-041671cf40ff/w1_slave', 'r') as f:
		lines = f.readlines()
	if lines[0].strip()[-3:] == 'YES':
		equals_pos = lines[1].find('t=')
		if equals_pos != -1:
			temp_string = lines[1][equals_pos + 2:]
			temp_c = float(temp_string) / 1000.0
		else:
			temp_c = 99
	else:
		temp_c = 99

	return temp_c

def getBCM280():
	#syslog.syslog('getBCM280')
	sensor = bmp280.BMP280(bus = 1, address = 0x77)
	press, temp = sensor.getReading(preset = 4)
	sensor.close()
	return press, temp

def snapPhoto(annotation):
	#syslog.syslog('snapPhoto')
	global uniqueID, redLED
	with PiCamera() as camera:
		camera.resolution = (3280, 2464)
		camera.annotate_text = annotation
		time.sleep(2)
		GPIO.output(redLED, True)
		timestr = time.strftime("%Y%m%d-%H%M%S")
		filename = '/home/pi/balloonlogger/photo/' + uniqueID + '_img_' + timestr + '.jpg'
		camera.capture(filename)
		GPIO.output(redLED, False)

def takeVid(annotation):
	#syslog.syslog('takeVid')
	global uniqueID, redLED
	with PiCamera() as camera:
		camera.resolution = (1640, 922)
		camera.framerate = 30
		camera.annotate_text = annotation
		time.sleep(2)
		GPIO.output(redLED, True)
		timestr = time.strftime("%Y%m%d-%H%M%S")
		filename = '/home/pi/balloonlogger/video/' + uniqueID + '_vid_' + timestr + '.h264'
		camera.start_recording(filename)
		camera.wait_recording(50)
		camera.stop_recording()
		GPIO.output(redLED, False)

def calcAlt(zeroPress, currPress):
	#syslog.syslog('calcAlt zeroPress: %s' % zeroPress)
	#syslog.syslog('calcAlt currPress: %s' % currPress)
	#altFt = (10**(math.log(float(currPress)/float(zeroPress))/5.2558797)-1(-6.8755856e-6))
	altFt = (10**(math.log10(currPress/zeroPress)/5.2558797)-1)/(-6.8755856e-6)
	return altFt

def xmitData(temp1,temp2,pres1,alt):
	#syslog.syslog('xmitData')
	xmitStr = 'Data={:.1f},{:.1f},{:.1f},{:.1f}'.format(temp1, temp2, pres1, alt)
	for i in range(0,3):
		call(['beacon', '-d', 'K0JAA', '-s', 'sm0', xmitStr])
		time.sleep(0.1)

def logLoop():
	global logData, zPress, uniqueID
	global redLED, greenLED, blueLED
	if logData:
		logFile = open('/home/pi/balloonlogger/data/' + uniqueID + '_data.csv','a')
		csvWriter = csv.writer(logFile)
		zPress = initPressure()
	while logData:
		GPIO.output([redLED, greenLED], False)
		timestamp = math.trunc(time.time())
		syslog.syslog('start log loop %s' % timestamp)

		#gather data from DS18b20 temp sensor
		GPIO.output(blueLED, True)
		t1 = getDS18b20()

		#gather data from BCM280 temp and pressure sensor
		p1, t2 = getBCM280()
		GPIO.output(greenLED, True)
		GPIO.output(blueLED, False)

		#convert pressure to altitude
		alt = calcAlt(zPress, p1)

		#write data to csv
		csvWriter.writerow([timestamp,t1,t2,p1,alt])
		logFile.flush()
		os.fsync(logFile.fileno())

		#transmit data using beacon command
		GPIO.output([blueLED,redLED], True)
		GPIO.output(greenLED, False)
		xmitData(t1,t2,p1,alt)

		#take photo and video
		GPIO.output([redLED,blueLED],False)
		GPIO.output(greenLED, True)
		annotation = "{:.1f}C {:.1f}C {:.1f}hPa {:,.0f}ft".format(t1, t2, p1, alt)
		snapPhoto(annotation)
		takeVid(annotation)
		GPIO.output([blueLED, redLED], False)
		loopDuration = math.trunc(time.time()) - timestamp
		if loopDuration < 60:
			t = 60 - loopDuration
		else:
			t = 0
		time.sleep(t)
		GPIO.output(redLED, True) #when the loop ends and stops, stay red

	logFile.close()

if __name__ == "__main__":
	global logData, zPress, uniqueID
	gpioSetup()
	uniqueID = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(4))
	logData = pickleReader('button.pickle')
	if logData:
		#zPress = initPressure()
		t = threading.Thread(target=logLoop)
		t.daemon = True
		t.start()
	while True:
		signal.pause()


