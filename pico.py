#!/usr/bin/env python
# -*- coding: utf8 -*-
#===============================================================================
#
# USAGE:        Firmware update: pico.py -f ups_pico4_main.hex
#
# DESCRIPTION:	Toolkit to manage RPi used with UPIS
# 
# UPDATES: 		Fetch the latest version from: https://github.com/maestrx/pimodules
#
# RETURN CODES: 0 - OK
#				1 - Wrong command line parameters
#				2 - FW update failed
#				3 - System setup failed
#
# REQUIREMENTS: pip3 install serial smbus progress
#
# BUGS:         TBD
# AUTHOR:       Vit SAFAR <PIco@safar.info>
# VERSION:      v0.2, 10.5.2022
# HISTORY:      - v0.2, 10.5/2022, I2C retry implemented, removed hardcoded sleep functions
#			 	- v0.1, 8.5.2022, Initial release
#
# VALIDATED ON: RPi4 with UPS Pico HV4.0B/C
# PYTHON:       python2 & python3
#
# TODO:         
# - Script pre-requisities verification & installation (configure boot params, enable I2C&serial, etc). /boot/config.txt: dtparam=i2c_arm=on dtparam=i2c1_baudrate=25000
# - Check that the FW in the file is newer than the one already running (overridable) 
# - Manage the pico_i2c.service
# - Enable RTC
# - Manage OS return codes properly
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
	i2cbus = None
	i2cbusid = 1
	pico_model_list = {ord('S'): 'BC Stack', ord('A'): 'BC Advanced', ord('P'): 'BC PPoE', ord('T'): 'B Stack', ord('B'): 'B Advanced', ord('Q'): 'B PPoE'}

	def __init__(self):
		logging.basicConfig(level=logging.DEBUG, format='%(asctime)s [%(levelname)s] %(message)s' )
		self.parse_args()

	# parse command args and run appropriate action
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

		# set output verbosity
		# NOTSET<DEBUG<INFO<WARNING<ERROR<CRITICAL
		if self.args.verbose > 1:
			logging.getLogger().setLevel(logging.DEBUG)
			logging.debug('Logging set to DEBUG')
		elif self.args.verbose > 0:
			logging.getLogger().setLevel(logging.INFO)
			logging.info('Logging set to INFO')
		elif self.args.verbose < 1:
			logging.getLogger().setLevel(logging.WARNING)

		# detect capabilities of teh system
		self.get_capabilities()

		# FW upload action
		if self.args.fw_file:
			if self.upload_firmware():
				sys.exit(0)
			else:
				sys.exit(2)

		# Config setup action
		elif self.args.config_setup:
			if self.config_setup():
				sys.exit(0)
			else:
				sys.exit(3)

		# Show help action
		else:
			parser.print_help(sys.stderr)
			sys.exit(1)

	# detect avaialble system features
	def get_capabilities(self):
		try:
			import progress.bar
			self.capability['progress'] = progress.bar
			logging.debug('Capability "progress" is available')
		except:
			self.capability['progress'] = None
			logging.debug('Capability "progress" is NOT available')

		try:
			import serial
			self.capability['serial'] = serial
			logging.debug('Capability "serial" is available')
		except:
			self.capability['serial'] = None
			logging.debug('Capability "serial" is NOT available')

		try:
			import smbus
			self.capability['smbus'] = smbus
			logging.debug('Capability "smbus" is available')
		except:
			self.capability['smbus'] = None
			logging.debug('Capability "smbus" is NOT available')

		logging.info('Python capabilities: progress:{0} serial:{1} smbus:{2}'.format(self.capability['progress'] is not None, self.capability['serial'] is not None, self.capability['smbus'] is not None))
		if self.capability['smbus'] is not None:
			try:
				self.pico_pcb_i2c = self.run_i2c_with_retry('rb', 0x69, 0x35)
				self.pico_model_i2c = self.run_i2c_with_retry('rb', 0x69, 0x36)
				if self.pico_model_i2c in self.pico_model_list:
					pico_model = self.pico_model_list[self.pico_model_i2c]
				else:
					pico_model = 'UNKNOWN({0})'.format(self.pico_model_i2c)
				logging.warning('PICO PCB version: {0} PICO model: {1}'.format(self.get_hex(self.pico_pcb_i2c), pico_model))			
			except:
				logging.exception('Unable to collect PICO release information')		

		try:
			self.rpi_model = open('/sys/firmware/devicetree/base/model', 'r').read()
		except:
			self.rpi_model = 'UNKNOWN'
		logging.warning('RPi model: {0}'.format(self.rpi_model))


	# setup system features, TODO
	def config_setup(self):
		logging.debug('Running "config setup" mode')
		return False

	# initiate FW update
	def upload_firmware(self):
		logging.debug('Running "firmware update" mode')
		logging.debug('FW upload params: fw_file:{0} serial_port:{1} baud_rate:{2} skip_fw_verify:{3} fw_verify_only:{4} skip_fw_md5:{5} skip_i2c_fw:{6} skip_i2c_bl:{7} skip_i2c_reset:{8} i2c_bl_local:{9}'.format(self.args.fw_file, self.args.serial_port, self.args.baud_rate, self.args.skip_fw_verify, self.args.fw_verify_only, self.args.skip_fw_md5, self.args.skip_i2c_fw, self.args.skip_i2c_bl, self.args.skip_i2c_reset, self.args.i2c_bl_local))
		
		# check serial is avaialble
		if self.capability['serial'] is None:
			logging.error('Python module serial not available')
			return False

		# validate integrity of the provided FW file
		if self.args.skip_fw_verify:
			logging.info('Skipping firmware verification')
		else:
			if self.validate_file():
				logging.warning('Firmware file verification OK')
			else:
				return False
		
		if self.args.fw_verify_only:
			logging.debug('Firmware file validation only mode')
			return True

		# set UPIS to bootloader mode before FW update
		if self.capability['smbus'] is not None:
			if not self.args.skip_i2c_fw:
				#self.orig_fw_version = i2cbus.read_word_data(0x69, 0x38) # get FW version
				self.orig_fw_version = self.run_i2c_with_retry('rw', 0x69, 0x38)
				if self.orig_fw_version is None:
					logging.exception('Failed to read current FW version from UPIS via I2C. Is UPIS in running mode?')
					return False
				logging.warning('Current firmware release: {0}'.format(hex(self.orig_fw_version)))

			if not self.args.skip_i2c_bl:
				if self.args.i2c_bl_local:
					logging.debug('Enabling local BL')
					# i2cbus.write_byte_data(0x6b, 0x00, 0xff) # local BL
					if self.run_i2c_with_retry('wb', 0x6b, 0x00, data=0xff) is None:
						logging.error('Failed to set local BL mode on UPIS via I2C. Is UPIS in running mode?')
						return False
				else:
					logging.debug('Enabling remote BL')
					#i2cbus.write_byte_data(0x6b, 0x00, 0xbb) # remote BL
					if self.run_i2c_with_retry('wb', 0x6b, 0x00, data=0xbb) is None:
						logging.error('Failed to set remote BL mode on UPIS via I2C. Is UPIS in running mode?')
						return False
			else:
				logging.debug('smbus capability not available, skipping bootloader config')
		else:
			logging.debug('smbus capability not available, skipping bootloader config')


		# connect to UPIS via Serial
		try:
			logging.debug('Opening serial port {0} with baudrate {1}bps'.format(self.args.serial_port,self.args.baud_rate))
			self.pico_serial = self.capability['serial'].Serial(port=self.args.serial_port, baudrate=self.args.baud_rate, timeout=0.001, rtscts=0, xonxoff=True)
			logging.debug('Serial port opened')
		except:
			logging.exception('Failed to open serial port')
			return False

		# test serial connectivity with UPIS
		if self.test_serial():
			logging.warning('Serial link with PICO UPS verified')
		else:
			logging.error('Failed to establish serial communication with PICO UPS')
			return False
		

		# do FW update
		if self.send_file():

			# perform UPIS factory reset
			if self.capability['smbus'] is not None:
				if not self.args.skip_i2c_reset:
					# i2cbus.write_byte_data(0x6b, 0x00, 0xff) # local BL
					if self.run_i2c_with_retry('wb', 0x6b, 0x00, data=0xdd) is None:
						logging.exception('Failed to perform factory reset on UPIS via I2C.')
						return False

				if not self.args.skip_i2c_fw:
					#self.new_fw_version = i2cbus.read_word_data(0x69, 0x38) # get FW version
					self.new_fw_version = self.run_i2c_with_retry('rw', 0x69, 0x38)
					if self.new_fw_version is None:
						logging.exception('Failed to read new FW version from UPIS via I2C. Is UPIS in running mode?')
						return False
					logging.warning('New firmware release: {0}'.format(hex(self.new_fw_version)))

			logging.warning('Firmware update completed')
			return True
		return False

	# verify bootloader is available of serial link
	def test_serial(self):
		logging.debug('Testing serial link with UPIS bootloader')
		attempts = 50
		while attempts > 0:
			if self.send_line(":020000040000FA\r", 50):
				return True
			time.sleep(0.1)
			attempts -= 1
		return False


	# test integrity of teh provided FW file
	def validate_file(self):
		try:
			if not self.args.skip_fw_md5:
				with open(self.args.fw_file,"rb") as f:
					file_content = f.read() # read file as bytes
				logging.warning('MD5 of the firmware file: {0}'.format(hashlib.md5(file_content).hexdigest()))
			else:
				logging.info('Skipping MD5 checksum')

			# read FW file content and validate its content based on https://en.wikipedia.org/wiki/Intel_HEX
			eof = False
			with open(self.args.fw_file,"rb") as f:
				lnum = 0
				for line in f:
					line=line.strip().decode('utf-8')
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

	# send FW file content to UPIS bootloader via Serial
	def send_file(self):
		try:
			fw_lines_total = sum(1 for line in open(self.args.fw_file) if line.startswith(':'))
			# use nicer progress module to show FW update process or fall back to embedded simple one
			if self.capability['progress'] is None:
				bar = simpleBar('Uploading firmware', fw_lines_total)
			else:                
				bar = self.capability['progress'].Bar('Uploading firmware', max=fw_lines_total, suffix='%(percent).1f%% - %(eta)ds')
			
			# run update process, send FW file line by line till the last valid command line
			ret = True
			f = open(self.args.fw_file)
			lnum = 0
			for line in f:
				lnum += 1
				# send line and wait for ack
				if not self.send_line(line.strip()+"\r"):
					logging.error('Failed to ack the line {0}'.format(lnum))
					ret = False
					break
				# dont show progress output with while debug output is eanbled
				if self.args.verbose<2:
					bar.next()
				# finish sending on last line
				if line[7:9]=='01':  
					break
			bar.finish()
			return ret
		except:
			logging.exception('Failed to process firmware file')
			return False

	# send line and wait for the ack form bootloader
	def send_line(self, line, ack_wait = 300):
		try:
			for line in self.pico_serial:
				pass
			self.pico_serial.write(line.encode())
			logging.debug('Serial line sent: {0}'.format(line))
			return self.wait_ack(ack_wait)
		except:
			logging.exception('Failed to send data to PICO UPS')
			return False

	# wait for the bootloader to send ACK
	def wait_ack(self, ack_wait = 300):
		try:
			wait_iter = 0
			lineack = False
			while wait_iter < ack_wait:
				# process all lines received via serial from UPIS
				for line in self.pico_serial:
					logging.debug('Received over serial: {0}'.format(line))
					try:
						if line.strip()[0] == 6:
							lineack=True
							break
					except:
						pass
					try:
						if ord(line.strip()[0])==6:
							lineack=True
							break
					except:
						pass
				# if for loop above completels without break, iterate next while
				else:
					wait_iter += 1
					time.sleep(0.01)
					continue						
				# in case for loop above terminated with break, break the loop
				break
			logging.debug('Result of waiting for serial ack: {0} loops: {1}'.format(lineack, wait_iter))
			return lineack
		except:
			logging.exception('Failed to recieve data ACK from UPIS')
			return False

	# execute I2I operation with retry
	def run_i2c_with_retry(self, op, device, address, *args, **kwargs):
		max_tries = kwargs.get('max_tries', 12)
		try_delay = kwargs.get('try_delay', 0.5)
		data = kwargs.get('data', None)
		if op.startswith('w') and data is None:
			logging.error('I2C write operation requires data field')
			return None	
	
		if self.i2cbus is None:
			try:
				logging.debug('Initializing I2C bus id: {0}'.format(self.i2cbusid))
				self.i2cbus = self.capability['smbus'].SMBus(self.i2cbusid)
			except:
				logging.exception('Failed to initialize I2C bus 1 on RPi.')
				return None

		logging.debug('I2C operation {0} on device {1} with address {2} and data {3}'.format(op, self.get_hex(device), self.get_hex(address), self.get_hex(data)))

		while max_tries > 0:
			try:
				if op == 'rb':
					return self.i2cbus.read_byte_data(device, address)
				elif op == 'rw':
					return self.i2cbus.read_word_data(device, address)
				elif op == 'wb':
					self.i2cbus.write_byte_data(device, address, kwargs.get('data', 10))
					return True
				elif op == 'ww':
					self.i2cbus.write_word_data(device, address, kwargs.get('data', 10))
					return True
				else:
					logging.error('Unsupported I2C operation')
					return None	
			except IOError as e:
				max_tries -= 1
				logging.debug('I2C IOError. Retring again in {0}s with {0} more attempts'.format(try_delay, max_tries, address, data))
				time.sleep(try_delay)
			except:
				logging.exception('Failed to perform I2C operation')
				return None
		logging.debug('Unexpected situation!')
		return None

	def get_hex(self, value):
		try:
			return hex(value)
		except:
			return value

# simple implementation fo the progress bar showing progress of teh FW update
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
	

if __name__ == "__main__":
	picoUPS()


