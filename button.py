#!/usr/bin/env python2.7
# button.py
# daemon to watch for button presses and flip value in shm temp file
# so the data gathering process knows whether it should run

import RPi.GPIO as GPIO
import math, threading, time, os, pickle, sys, signal, syslog
import bmp280, csv
from subprocess import call

def signalHandler(signal, frame):
	#signalHandler catches ctrl-C and cleanly exits
	GPIO.output(greenLED, False)
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
	global logData, whiteLED, redLED, greenLED

	syslog.syslog('Button pressed.')

	logData = not pickleReader('button.pickle') #since each button press flips it, we want opposite value of what's stored

	syslog.syslog('logData changed to %s' %logData)

	GPIO.output(whiteLED, logData)
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
	global buttonPin, redLED, whiteLED, greenLED

	#use broadcom numbers, not board pins
	GPIO.setmode(GPIO.BCM)

	buttonPin = 23
	redLED = 17
	whiteLED = 27
	greenLED = 22

	GPIO.setup(buttonPin, GPIO.IN, pull_up_down=GPIO.PUD_UP) # buttonPin is an input, with a pullup resistor to set it to high by default. pressing button changes it to low
	GPIO.setup(redLED, GPIO.OUT)
	GPIO.setup(whiteLED, GPIO.OUT)
	GPIO.setup(greenLED, GPIO.OUT)

	GPIO.output(greenLED, True)
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

def snapPhoto():
	syslog.syslog('snapPhoto')

def takeVid():
	syslog.syslog('takeVid')

def calcAlt(zeroPress, currPress):
	#syslog.syslog('calcAlt zeroPress: %s' % zeroPress)
	#syslog.syslog('calcAlt currPress: %s' % currPress)
	#altFt = (10**(math.log(float(currPress)/float(zeroPress))/5.2558797)-1(-6.8755856e-6))
	altFt = (10**(math.log10(currPress/zeroPress)/5.2558797)-1)/(-6.8755856e-6)
	return altFt

def xmitData(temp1,temp2,pres1,alt):
	#syslog.syslog('xmitData')
	xmitStr = 'Data={},{},{},{}'.format(temp1, temp2, pres1, alt)
	for i in range(1,3):
		call(['beacon', '-d', 'K0JAA', '-s', 'sm0', xmitStr])
		time.sleep(0.1)

def logLoop():
	global logData
	global zPress
	if logData:
		logFile = open('/home/pi/data.csv','a')
		csvWriter = csv.writer(logFile)
		zPress = initPressure()
	while logData:
		syslog.syslog('start log loop')
		GPIO.output(redLED, True)
		t1 = getDS18b20()
		p1, t2 = getBCM280()
		GPIO.output(redLED, False)
		alt = calcAlt(zPress, p1)
		timestamp = math.trunc(time.time())
		csvWriter.writerow([timestamp,t1,t2,p1,alt])
		logFile.flush()
		os.fsync(logFile.fileno())
		GPIO.output(redLED, True)
		xmitData(t1,t2,p1,alt)
		GPIO.output(redLED, False)
		snapPhoto()
		takeVid()
		time.sleep(60)

	logFile.close()

if __name__ == "__main__":
	global logData, zPress
	gpioSetup()
	logData = pickleReader('button.pickle')
	if logData:
		#zPress = initPressure()
		t = threading.Thread(target=logLoop)
		t.daemon = True
		t.start()
	while True:
		signal.pause()


