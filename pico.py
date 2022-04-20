#!/usr/bin/env python
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
# NOTES:
# - Intel HEX file docs: https://en.wikipedia.org/wiki/Intel_HEX
# - One line fw update: # i2cget -y 1 0x69 0x38 w && i2cset -y 1 0x6b 0x00 0xff && sleep 2 && ./upis_fw.py ups_pico4_main_testing1.hex && sleep 5 && i2cget -y 1 0x69 0x38 w
# AUTHOR:       Vit SAFAR <PIco@safar.info>
# VERSION:      POC release 6
# CREATED:      16.4.2022
# REVISION:     TBD
#
# TODO:         
# - Script pre-requisities verification & installation (configure boot params, enable I2C&serial, etc). /boot/config.txt: dtparam=i2c_arm=on dtparam=i2c1_baudrate=25000
# - Check that the FW in the file is newer than the one already running (overridable) 
# - Manage the pico_i2c.service
# - Enable RTC
# - Install pip2
#   wget https://bootstrap.pypa.io/pip/2.7/get-pip.py
#   python2 get-pip.py
#
#===============================================================================

from __future__ import print_function
import time
import sys
import logging
import re
import argparse
import hashlib


class picoUPS:
	args = None
	pico_serial = None
	orig_fw_version = None
	new_fw_version = None
	capability = {}

	def __init__(self):
		logging.basicConfig(level=logging.DEBUG, format='%(asctime)s [%(levelname)s] %(message)s' )
		self.parse_args()

	def parse_args(self):
		parser = argparse.ArgumentParser(description='PICO toolkit')
		parser.add_argument("-v", "--verbose", dest="verbose", help='', action="count", default=0)

		group_fwupdate = parser.add_argument_group('Firmware', 'Firmware update')
		group_fwupdate.add_argument("-f", "--fw-file", dest="fw_file", help='', type=str, action="store", default=None, metavar='firmware_file')
		group_fwupdate.add_argument("-p", "--serial-port", dest="serial_port", help='', type=str, action="store", default="/dev/serial0", metavar='serial_port_device')
		group_fwupdate.add_argument("-b", "--baudrate", dest="baud_rate", help='', type=int, action="store", default=9600, metavar='baud_rate')
		group_fwupdate.add_argument("-g", "--skip-fw-verify", dest="skip_fw_verify", help='', action="store_true")
		group_fwupdate.add_argument("-G", "--fw-verify-only", dest="fw_verify_only", help='', action="store_true")
		group_fwupdate.add_argument("-H", "--skip-fw-md5", dest="skip_fw_md5", help='', action="store_true")
		group_fwupdate.add_argument("-i", "--skip-i2c-fw", dest="skip_i2c_fw", help='', action="store_true")
		group_fwupdate.add_argument("-j", "--skip-i2c-bl", dest="skip_i2c_bl", help='', action="store_true")
		group_fwupdate.add_argument("-k", "--skip-i2c-reset", dest="skip_i2c_reset", help='', action="store_true")
		group_fwupdate.add_argument("-l", "--i2c-bl-local", dest="i2c_bl_local", help='', action="store_true")

		group_setup = parser.add_argument_group('Setup', 'Setup of the RPi for PICO UPS')
		group_setup.add_argument('-s', '--config-setup', dest="config_setup", help='', action="store_true")
		
		self.args = parser.parse_args()

		# NOTSET<DEBUG<INFO<WARNING<ERROR<CRITICAL
		if self.args.verbose > 1:
			logging.getLogger().setLevel(logging.DEBUG)
			logging.debug('Logging set to DEBUG')
		elif self.args.verbose > 0:
			logging.getLogger().setLevel(logging.INFO)
			logging.info('Logging set to INFO')
		elif self.args.verbose < 1:
			logging.getLogger().setLevel(logging.WARNING)

		self.get_capabilities()

		# FW upload action
		if self.args.fw_file:
			self.upload_firmware()
		# Config setup action
		elif self.args.config_setup:
			self.config_setup()
		# Show help action
		else:
			parser.print_help(sys.stderr)
			sys.exit(1)

	def get_capabilities(self):
		try:
			import progress.bar
			self.capability['progress'] = progress.bar
		except:
			self.capability['progress'] = None

		try:
			import serial
			self.capability['serial'] = serial
		except:
			self.capability['serial'] = None

		try:
			import smbus
			self.capability['smbus'] = smbus
		except:
			self.capability['smbus'] = None
		logging.info('Python capabilities: progress:{0} serial:{1} smbus:{2}'.format(self.capability['progress'] is not None, self.capability['serial'] is not None, self.capability['smbus'] is not None))

	def config_setup(self):
		pass

	def upload_firmware(self):
		if self.capability['serial'] is None:
			logging.error('Python module serial not available')
			return False

		if self.args.skip_fw_verify:
			logging.info('Skipping firmware verification')
		else:
			if self.validate_file():
				logging.warning('Firmware file verification OK')
			else:
				return False
		
		if self.args.fw_verify_only:
			return True

		if self.capability['smbus'] is not None:
			i2cbus = self.capability['smbus'].SMBus(1)
			if not self.args.skip_i2c_fw:
				self.orig_fw_version = i2cbus.read_word_data(0x69, 0x38) # get FW version
				logging.warning('Current firmware release: {0}'.format(hex(self.orig_fw_version)))

			if not self.args.skip_i2c_bl:
				if not self.args.i2c_bl_local:
					i2cbus.write_byte_data(0x6b, 0x00, 0xff) # local BL
				else:
					i2cbus.write_byte_data(0x6b, 0x00, 0xbb) # remote BL
				time.sleep(1)

		try:
			logging.debug('Opening serial port {0} with baudrate {1}bps'.format(self.args.serial_port,self.args.baud_rate))
			self.pico_serial = self.capability['serial'].Serial(port=self.args.serial_port, baudrate=self.args.baud_rate, timeout=0.001, rtscts=0, xonxoff=True)
			logging.debug('Serial port opened')
		except:
			logging.exception('Failed to open serial port')
			return False

		if self.send_line(":020000040000FA\r"):
			logging.warning('Serial link with PICO UPS verified')
		else:
			logging.error('Failed to establish serial communication with PICO UPS')
			return False

		if self.send_file():

			if self.capability['smbus'] is not None:
				time.sleep(1)
				if not self.args.skip_i2c_reset:
					i2cbus.write_byte_data(0x6b, 0x00, 0xdd) # factory reset
				if not self.args.skip_i2c_fw:
					self.new_fw_version = i2cbus.read_word_data(0x69, 0x38) # get FW version
					logging.warning('New firmware release: {0}'.format(hex(self.orig_fw_version)))			

			logging.warning('Firmware update completed')
			return True
		return False


	def validate_file(self):
		try:
			if not self.args.skip_fw_md5:
				with open(self.args.fw_file,"rb") as f:
					file_content = f.read() # read file as bytes
				logging.warning('MD5 of the firmware file: {0}'.format(hashlib.md5(file_content).hexdigest()))
			else:
				logging.info('Skipping MD5 checksum')

			eof = False
			with open(self.args.fw_file,"rb") as f:
				lnum = 0
				for line in f:
					line=line.strip()
					lnum += 1
					target = re.match( r"^:([a-fA-F0-9]{2})([a-fA-F0-9]{2})([a-fA-F0-9]{2})([a-fA-F0-9]{2})([a-fA-F0-9]*)([a-fA-F0-9]{2})$", line, re.M|re.I|re.DOTALL)
					if len(target.group(5))/2 != int(target.group(1),16):
						logging.error('Firmware file verification failed. Invalid data length on line {0}'.format(lnum))
						return False
					if sum(int(line[i:i+2],16) for i in range(1, len(line), 2)) % 256:
						logging.error('Firmware file verification failed. Invalid checksum on line {0}'.format(lnum))
						return False
					if target.group(4) == '01':
						return True
			logging.error('Firmware file verification failed. End Of File record not found')
			return False
		except:
			logging.exception('Failed to verify firmware file')
			return False

	def send_file(self):
		try:
			fw_lines_total = sum(1 for line in open(self.args.fw_file) if line.startswith(':'))
			if self.capability['progress'] is None:
				bar = simpleBar('Uploading firmware', fw_lines_total)
			else:                
				bar = self.capability['progress'].Bar('Uploading firmware', max=fw_lines_total, suffix='%(percent).1f%% - %(eta)ds')
			ret = True
			f = open(self.args.fw_file)
			lnum = 0
			for line in f:
				lnum += 1
				if not self.send_line(line.strip()+"\r"):
					logging.error('Failed to ack the line {0}'.format(lnum))
					ret = False
					break
				bar.next()
				if line[7:9]=='01':  # this is the last FW file line
					break
			bar.finish()
			return ret
		except:
			logging.exception('Failed to process firmware file')
			return False

	def send_line(self, line):
		try:
			for line in self.pico_serial:
				pass
			self.pico_serial.write(line.encode())
			return self.wait_ack()
		except:
			logging.exception('Failed to send data to PICO UPS')
			return False

	def wait_ack(self):
		try:
			wait_iter = 100
			lineack = False
			while wait_iter > 0:
				for line in self.pico_serial:
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
		except:
			logging.exception('Failed to recieve data ACK from UPIS')
			return False


class simpleBar:
	def __init__(self, text, total):
		self.total = total
		self.step = total / 100
		self.current = 0
		self.step_count = 0
		print('{0} |'.format(text), end = '')
		sys.stdout.flush()
	
	def next(self):
		self.current += 1
		self.step_count += 1
		if self.step_count > self.step:
			print('.', end = '')
			sys.stdout.flush()
			self.step_count = 0

	def finish(self):
		print ('|')
		sys.stdout.flush()
	

picoUPS()



'''
sudo nano /lib/systemd/system/pico_i2c.service
[Unit]
Description=UPS PIco GPIO Free Raspberry Pi Interaction Service 
After=multi-user.target
[Service]
Type=idle
ExecStart=/usr/bin/python /home/pi/pico_i2c.py
StandardOutput=inherit
StandardError=inherit
Restart=always
[Install]
WantedBy=multi-user.target

sudo chmod 644 /lib/systemd/system/pico_i2c.service

sudo systemctl daemon-reload
sudo systemctl enable pico_i2c.service
sudo systemctl start pico_i2c.service

sudo reboot

sudo nano /boot/config.txt
# Added for PIco 
enable_uart=1
dtoverlay=i2c-rtc,ds1307
dtparam=i2c_arm=on
dtparam=i2c1_baudrate=25000



sudo apt-get -y install i2c-tools
sudo nano /etc/modules
i2c-bcm2708
i2c-dev
rtc-ds1307

sudo nano /etc/rc.local
6. and add the following line before “exit 0”
sleep 4; hwclock -s &


sudo nano /lib/udev/hwclock-set
10. and comment out these three lines:
#if [ -e /run/systemd/system] ; then
# exit 0
#fi


sudo hwclock -w

import argparse

my_parser = argparse.ArgumentParser()
my_parser.version = '1.0'
my_parser.add_argument('-a', action='store')
my_parser.add_argument('-b', action='store_const', const=42)
my_parser.add_argument('-c', action='store_true')
my_parser.add_argument('-d', action='store_false')
my_parser.add_argument('-e', action='append')
my_parser.add_argument('-f', action='append_const', const=42)
my_parser.add_argument('-g', action='count')
my_parser.add_argument('-i', action='help')
my_parser.add_argument('-j', action='version')

args = my_parser.parse_args()

print(vars(args))

, required=True

		'''