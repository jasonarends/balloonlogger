# balloonlogger

Code to read data from a few sensors, log it, transmit it via a soundcard hooked up to a transmitter, take pictures and video, and blink a light to indicate what's happening.

LED colors:
* White: Ready
* Red: Stopped
* Green: Logging loop (waiting)
* Blue: Logging loop (reading sensor)
* Purple: Sending data beacon (there's a delay from when it asks for it to when it transmits)
* Yellow: Camera recording video or photo
