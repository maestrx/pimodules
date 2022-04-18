#!/usr/bin/python
# -*- coding: utf8 -*-
#===============================================================================
#
# USAGE:        TBD
#
# DESCRIPTION:
#               This script uploads firmware to UPIS.
#
# RETURN CODES: TBD
#
# OPTIONS:      ---
# REQUIREMENTS: TBD
#
# BUGS:         ---
# NOTES:        TBD
# AUTHOR:       Vit SAFAR <PIco@safar.info>
# VERSION:      POC release 3
# CREATED:      16.4.2022
# REVISION:     TBD
#
# TODO:         TBD
#               https://python-future.org/compatible_idioms.html
# wget https://bootstrap.pypa.io/pip/2.7/get-pip.py
# python2 get-pip.py
# pi@rpi-upstest:~ $ i2cget -y 1 0x69 0x38 w
# 0x011d
# i2cset -y 1 0x6b 0 0xbb # remote bootloader, 0xff for local BL
#===============================================================================

from __future__ import print_function
import serial
import time
import sys
from progress.bar import Bar

class test:
  serial_port='/dev/serial0'
  serial_baudrate=9600
  filename = 'ups_pico4_main_Firmware_011D_29032022.hex'

  def __init__(self):
    self.filename = sys.argv[1]
    self.upis = serial.Serial(port=self.serial_port,baudrate=self.serial_baudrate,timeout=0.001,rtscts=0,xonxoff=True)
    self.sendfile()

  def sendfile(self):
    fw_lines_total = sum(1 for line in open(self.filename) if line.startswith(':'))
    bar = Bar('Uploading FW', max=fw_lines_total, suffix='%(percent).1f%% - %(eta)ds')
    f = open(self.filename)
    lnum = 0
    for line in f:
      lnum += 1
      if not self.sendline(line.strip()+"\r"):
        print('failed to ack the line {0}'.format(lnum))
        break
      bar.next()
      if line[7:9]=='01':  # this is the last FW file line
        break
    bar.finish()

  def sendline(self, line):
    for line in self.upis:
      pass
    self.upis.write(line.encode())
    return self.waitack()

  def waitack(self):
    # wait command reception confirmation
    wait_iter = 100
    lineack = False
    while wait_iter > 0:
      for line in self.upis:
        if line:
          try:
            if line.strip()[0] == 6:
              lineack=True
              wait_iter = 0
              break
          except:
            pass
          try:
            if ord(line.strip()[0])==6:
              lineack=True
              wait_iter = 0
              break
          except:
            pass

      wait_iter -= 1
    return lineack

test()
>>>>>>> cbcee4a (initial)
