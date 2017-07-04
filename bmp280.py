#!/usr/bin/env python3
#coding=utf-8

import time
import pigpio

#python class for BMP280 Temp-Pressure Sensor

class BMP280:

   #registers
   idReg       =   0xD0    #chip id - p 24
   resetReg    =   0xE0   #reset register - p 24
   statusReg   =   0xF3   #status register - p 25
   overModeReg   =   0xF4   #The “ctrl_meas” register sets the data acquisition options of the device - p 25
   configReg   =   0xF5   #The “config” register sets the rate, filter and interface options of the device - p 26
   #three regs for raw pressure data: _msb, _lsb, _xlsb - p 26
   rawBar_msb   =   0xF7
   rawBar_lsb   =   0xF8
   rawBar_xlsb   =   0xF9
   #three regs for raw temperature data: _msb, _lsb, _xlsb - p 27
   rawTemp_msb   =   0xFA
   rawTemp_lsb   =   0xFB
   rawTemp_xlsb=   0xFC

   #these are standard configs suggested:
   # name            P over      T over      Timing
   # ultraLowPower      1x   (1)      1x   (1)      6.4
   # lowPower         2x   (2)      1x   (1)      8.7
   # stdRes         4x   (3)      1x   (1)      13.3
   # highRes         8x   (4)      1x   (1)      22.5
   # ultraHighRes      16x   (5)      2x   (2)      43.2
   ulSet   =   (1,1,6.4)
   lSet   =   (2,1,8.7)
   sSet   =   (3,1,13.3)
   hSet   =   (4,1,22.5)
   uhSet   =   (5,2,43.2)
   presets   =   (ulSet,lSet,sSet,hSet,uhSet)

   #calibration registers
   # Name   Addr1   Addr2   Format
   # dig_T1   0x88   0x89   unsigned short
   # dig_T2   0x8A   0x8B   signed short
   # dig_T3   0x8C   0x8D   signed short
   # dig_P1   0x8E   0x8F   unsigned short
   # dig_P2   0x90   0x91   signed short
   # dig_P3   0x92   0x93   signed short
   # dig_P4   0x94   0x95   signed short
   # dig_P5   0x96   0x97   signed short
   # dig_P6   0x98   0x99   signed short
   # dig_P7   0x9A   0x9B   signed short
   # dig_P8   0x9C   0x9D   signed short
   # dig_P9   0x9E   0x9F   signed short
   # reserved   0xA0   0xA1
   dig_T1 = 0x88
   dig_T2 = 0x8A
   dig_T3 = 0x8C
   dig_P1 = 0x8E
   dig_P2 = 0x90
   dig_P3 = 0x92
   dig_P4 = 0x94
   dig_P5 = 0x96
   dig_P6 = 0x98
   dig_P7 = 0x9A
   dig_P8 = 0x9C
   dig_P9 = 0x9E

   def __init__(self, bus=1, address=0x77, debug=False):
      self.debug = debug
      self.pi = pigpio.pi()
      self.i2c = self.pi.i2c_open(bus, address, 0)

   def getOverMode(self):
      #returns contents of the oversampling - mode reg
      regValue = self.pi.i2c_read_byte_data(self.i2c, self.overModeReg)
      presOverCfg = (regValue >> 2) & 0b111
      tempOverCfg = (regValue >> 5) & 0b111
      powerModeCfg = (regValue) & 0b11
      return presOverCfg,tempOverCfg,powerModeCfg

   def setPresOver(self,value):
      #Oversampling for pressure. This accepts 5 level, equivalent to 1x - 2x - 4x - 8x - 16x oversampling
      if value not in range(1,6): raise ValueError("Oversampling value {} unsupported (accepted 1-5)".format(value))
      #get actual value
      regValue = self.pi.i2c_read_byte_data(self.i2c, self.overModeReg)
      #bitwising 3 bit value. for pressure we have bits 4,3 and 2
      regValue = self.setBit(regValue,(value>>2)&1,4)
      regValue = self.setBit(regValue,(value>>1)&1,3)
      regValue = self.setBit(regValue,(value>>0)&1,2)
      #writing back value to register
      self.pi.i2c_write_byte_data(self.i2c, self.overModeReg, regValue)

   def setTempOver(self,value):
      #Oversampling for temperature. This accepts 5 level, equivalent to 1x - 2x - 4x - 8x - 16x oversampling
      if value not in range(1,6): raise ValueError("Oversampling value {} unsupported (accepted 1-5)".format(value))
      #get actual value
      regValue = self.pi.i2c_read_byte_data(self.i2c, self.overModeReg)
      #bitwising 3 bit value. for temperature we have bits 7,6 and 5
      regValue = self.setBit(regValue,(value>>2)&1,7)
      regValue = self.setBit(regValue,(value>>1)&1,6)
      regValue = self.setBit(regValue,(value>>0)&1,5)
      #writing back value to register
      self.pi.i2c_write_byte_data(self.i2c, self.overModeReg, regValue)

   def setPowerMode(self,value):
      #Power mode. This accepts 3 values, equivalent to 0 - Sleep, 1 - Forced and 3 - normal
      if value not in range(0,3): raise ValueError("Power mode {} unsupported (accepted 0,1,2)".format(value))
      #value 2 (normal) should be 3 for register
      if value == 2: value = 3
      #get actual value
      regValue = self.pi.i2c_read_byte_data(self.i2c, self.overModeReg)
      #bitwising 2 bit value. for power mode we have bits 1 and 0
      regValue = self.setBit(regValue,(value>>1)&1,1)
      regValue = self.setBit(regValue,(value>>0)&1,0)
      #writing back value to register
      self.pi.i2c_write_byte_data(self.i2c, self.overModeReg, regValue)

   def getConfig(self):
      #returns contents of the config reg
      regValue = self.pi.i2c_read_byte_data(self.i2c, self.configReg)
      iirFilterCfg = (regValue >> 2) & 0b111
      standbyCfg = (regValue >> 5) & 0b111
      return iirFilterCfg,standbyCfg

   def setIirFilter(self,value):
      #IIR filter. This accepts 5 level, equivalent to off - 2 - 4 - 8 - 16 filter coefficient
      if value not in range(0,5): raise ValueError("Oversampling value {} unsupported (accepted 0-4)".format(value))
      #get actual value
      regValue = self.pi.i2c_read_byte_data(self.i2c, self.configReg)
      #bitwising 3 bit value. for filter we have bits 4,3 and 2
      regValue = self.setBit(regValue,(value>>2)&1,4)
      regValue = self.setBit(regValue,(value>>1)&1,3)
      regValue = self.setBit(regValue,(value>>0)&1,2)
      #writing back value to register
      self.pi.i2c_write_byte_data(self.i2c, self.configReg, regValue)

   def setStandby(self,value):
      #Standby in normal mode. This accepts 8 level, equivalent to standby between 0.5ms and 4000ms
      if value not in range(0,8): raise ValueError("Standby value {} unsupported (accepted 0-7)".format(value))
      #get actual value
      regValue = self.pi.i2c_read_byte_data(self.i2c, self.configReg)
      #bitwising 3 bit value. for standby we have bits 7,6 and 5
      regValue = self.setBit(regValue,(value>>2)&1,7)
      regValue = self.setBit(regValue,(value>>1)&1,6)
      regValue = self.setBit(regValue,(value>>0)&1,5)
      #writing back value to register
      self.pi.i2c_write_byte_data(self.i2c, self.configReg, regValue)

   def getReading(self,preset=4):
      #this is a proxy to other functions to manage reading and compensation all in one. This uses 5 presets from datasheet (values from 0 to 4, increasing oversampling). For different settings you have to do direct functions call
      if preset not in range(0,5): raise ValueError("Preset {} unknown unsupported (accepted 0,1,2,3,4)".format(preset))
      #writing oversample settings to device
      self.setPresOver(self.presets[preset][0])
      self.setTempOver(self.presets[preset][1])
      #toggle a reading by writing the "forced" power mode
      self.setPowerMode(1)
      #waiting for the reading to complete.
      time.sleep(self.presets[preset][2]/1000)
      #now i can read the raw values from device
      (msbPress,lsbPress,xlsbPress,msbTemp,lsbTemp,xlsbTemp) = self.getRawValues()
      #joining values
      pValue = (msbPress << 12) + (lsbPress << 4) + (xlsbPress >> 4)
      tValue = (msbTemp << 12) + (lsbTemp << 4) + (xlsbTemp >> 4)
      #compensation
      (pValue,tValue) = self.compensateValues(pValue,tValue)
      #formatting
      pValue = pValue / 256.0 / 100.0
      tValue = tValue / 100.0
      return pValue,tValue

   def compensateValues(self,rawPressure,rawTemp):
      #this compensates Temp data
      dig_T1_value = self.readUnsigned(self.dig_T1)
      dig_T2_value = self.readSigned(self.dig_T2)
      dig_T3_value = self.readSigned(self.dig_T3)
      t1 = (((rawTemp >> 3) - (dig_T1_value << 1)) * dig_T2_value) >> 11
      t2 = (((rawTemp >> 4) - dig_T1_value) * ((rawTemp >> 4) - dig_T1_value) >> 12) * dig_T3_value >> 14
      tRaw = t1 + t2
      tValue = (tRaw * 5 + 128) >> 8

      #this compensates Pressure data
      dig_P1_value = self.readUnsigned(self.dig_P1)
      dig_P2_value = self.readSigned(self.dig_P2)
      dig_P3_value = self.readSigned(self.dig_P3)
      dig_P4_value = self.readSigned(self.dig_P4)
      dig_P5_value = self.readSigned(self.dig_P5)
      dig_P6_value = self.readSigned(self.dig_P6)
      dig_P7_value = self.readSigned(self.dig_P7)
      dig_P8_value = self.readSigned(self.dig_P8)
      dig_P9_value = self.readSigned(self.dig_P9)
      p1 = tRaw - 128000
      p2 = p1 * p1 * dig_P6_value
      p2 = p2 + ((p1*dig_P5_value)<<17)
      p2 = p2 + ((dig_P4_value)<<35)
      p1 = ((p1 * p1 * dig_P3_value)>>8) + ((p1 * dig_P2_value)<<12)
      p1 = ((((1)<<47)+p1))*(dig_P1_value)>>33
      if (p1 == 0): pValue = 0
      pValue = 1048576-rawPressure
      pValue = int((((pValue<<31)-p2)*3125)/p1)
      p1 = ((dig_P9_value) * (pValue>>13) * (pValue>>13)) >> 25
      p2 = ((dig_P8_value) * pValue) >> 19
      pValue = ((pValue + p1 + p2) >> 8) + ((dig_P7_value)<<4)

      return pValue,tValue;

   def getRawValues(self):
      #this starts a burst read to raw registers and return them in order
      (n,data) = self.pi.i2c_read_i2c_block_data(self.i2c, self.rawBar_msb, 6)
      return data[0],data[1],data[2],data[3],data[4],data[5]

   def resetSensor(self):
      self.pi.i2c_write_byte_data(self.i2c, self.resetReg, 0xB6)

   def getSensorId(self):
      return self.pi.i2c_read_byte_data(self.i2c, self.idReg)

   def getSensorStatus(self):
      value = self.pi.i2c_read_byte_data(self.i2c, self.statusReg)
      #Bit 3 measuring - Bit 0 im_update
      measuring = (value)>>3&1
      im_update = (value)&1
      return measuring,im_update

   def setBit(self,byte,bit,index):
      #Set the index:th bit of byte to bit, and return the new value.
      mask = 1 << index
      byte &= ~mask
      if bit:
         byte |= mask
      return byte

   def readUnsigned(self, reg):
      value = self.pi.i2c_read_word_data(self.i2c, reg)
      return value

   def readSigned(self, reg):
      value = self.pi.i2c_read_word_data(self.i2c, reg)
      if value > 32767:
         value -= 65536
      return value

   def close(self):
      self.pi.i2c_close(self.i2c)
      self.pi.stop()

if __name__ == "__main__":
   sensor = BMP280()
   print("Sensor Id: {:8b}".format(sensor.getSensorId()))
   (measuring,im_update) = sensor.getSensorStatus()
   print("Status: Measuring {} - im_update {}".format(measuring,im_update))
   (iirFilterCfg,standbyCfg) = sensor.getConfig()
   print("Config: IIR Filter {:03b} - Standby {:03b}".format(iirFilterCfg,standbyCfg))
   (presOverCfg,tempOverCfg,powerModeCfg) = sensor.getOverMode()
   print("Config: Pressure Oversampling {:03b} - Temperature Oversampling {:03b} - Power Mode {:02b}".format(presOverCfg,tempOverCfg,powerModeCfg))
   (pressure,temperature) = sensor.getReading()
   print("Pressure: {:.2f}hPa - Temperature: {:.2f}°C".format(pressure,temperature))
   sensor.close()

