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
# VERSION:      v0.3, 22.5.2022
# HISTORY:      - v0.3, 22.5.2022, added setup feature, its configuring RPI to enable pico features
#				- v0.2, 10.5,2022, I2C retry implemented, removed hardcoded sleep functions
#			 	- v0.1, 8.5.2022, Initial release
#
# VALIDATED ON: RPi4 running Bullseye with UPS Pico HV4.0B/C
# PYTHON:       python2 & python3
#
# TODO:         
# - Check that the FW in the file is newer than the one already running (overridable) 
# - Manage OS return codes properly
# - Finish help in argparse
#
#===============================================================================

from __future__ import print_function
import sys
try:
	from future import standard_library
	standard_library.install_aliases()
except:
	if sys.version_info[0] < 3:
		print ("\n\nInstall future module first by running: sudo apt install python-future!\n\n")
		raise
from subprocess import getoutput, getstatusoutput
import time
import logging
import re
import argparse
import hashlib
import base64
import os.path
import stat


class picoUPS:
	args = None
	pico_serial = None
	orig_fw_version = None
	new_fw_version = None
	capability = {}
	i2cbus = None
	i2cbusid = 1
	pico_model_list = {ord('S'): 'BC Stack', ord('A'): 'BC Advanced', ord('P'): 'BC PPoE', ord('T'): 'B Stack', ord('B'): 'B Advanced', ord('Q'): 'B PPoE'}
    # base64.b64encode(x)
	upis_systemd = 'CltVbml0XQpEZXNjcmlwdGlvbj1VUFMgUEljbyBHUElPIEZyZWUgUmFzcGJlcnJ5IFBpIEludGVyYWN0aW9uIFNlcnZpY2UKQWZ0ZXI9bXVsdGktdXNlci50YXJnZXQKW1NlcnZpY2VdClR5cGU9aWRsZQpFeGVjU3RhcnQ9L3NiaW4vcGljb19pMmNfc2VydmljZS5weQpTdGFuZGFyZE91dHB1dD1pbmhlcml0ClN0YW5kYXJkRXJyb3I9aW5oZXJpdApSZXN0YXJ0PWFsd2F5cwpbSW5zdGFsbF0KV2FudGVkQnk9bXVsdGktdXNlci50YXJnZXQK'
	upis_systemd_path = '/lib/systemd/system/pico_i2c.service'
	upis_systemd_script = 'IyEvdXNyL2Jpbi9lbnYgcHl0aG9uCiMgLSotIGNvZGluZzogdXRmLTggLSotCiMgV3JpdHRlbiBieSBJb2FubmlzIEEuIE1vdXJ0c2lhZGlzIGluZm9AcGltb2R1bGVzLmNvbQojIHRpbWVyIGJhc2VkIGludGVycnVwdCBkYWVtb24gc3VwcG9ydGluZyBVUFMgUEljbyBIVjQuMAojIFZlcnNpb24gMi4wIFJlbGFzZSBEYXRlIDAxLjAxLjIwMjEKCgppbXBvcnQgc3lzCmltcG9ydCB0aW1lCmltcG9ydCBkYXRldGltZQppbXBvcnQgb3MKaW1wb3J0IHJlCmltcG9ydCBnZXRvcHQKaW1wb3J0IHNtYnVzCmltcG9ydCB0aW1lCmltcG9ydCBkYXRldGltZQppbXBvcnQgdGhyZWFkaW5nCgojWW91IGNhbiBpbnN0YWxsIHBzdXRpbCB1c2luZzogc3VkbyBwaXAgaW5zdGFsbCBwc3V0aWwKI2ltcG9ydCBwc3V0aWwKCmkyYyA9IHNtYnVzLlNNQnVzKDEpCgoKIyMjIyMjIyMjIyMjIyMjIEZVTkNUSU9OUyAjIyMjIyMjIyMjIyMjIyMjIyMjCgpkZWYgZGVjMkJDRChpbnB1dFZhbHVlKToKICAgIHg9c3RyKGlucHV0VmFsdWUpCiAgICBCQ0RPdXQgPSAwCiAgICBmb3IgY2hhciBpbiB4OgogICAgICAgIEJDRE91dCA9IChCQ0RPdXQgPDwgNCkgKyBpbnQoY2hhcikKICAgIHJldHVybiBCQ0RPdXQKCmRlZiBnZXRDUFV0ZW1wZXJhdHVyZSgpOgogICAgcmVzID0gb3MucG9wZW4oJ3ZjZ2VuY21kIG1lYXN1cmVfdGVtcCcpLnJlYWRsaW5lKCkKICAgIGNwdV9kYXRhPXJlcy5yZXBsYWNlKCJ0ZW1wPSIsIiIpLnJlcGxhY2UoIidDXG4iLCIiKQogICAgY3B1X2ludD1pbnQoZmxvYXQoY3B1X2RhdGEpKQogICAgcmV0dXJuIGZvcm1hdChjcHVfaW50LCIwMmQiKQoKZGVmIHRpbWVyX2ludCgpOgogICAgI3ByaW50ICgiLS0tLS0tLS0tLS0tLS0tIERFQlVHOiBUaW1lciBGaXJlZCAtLS0tLS0tLS0tLS0tLS0iKQogICAgdD10aHJlYWRpbmcuVGltZXIoMC4yNSwgdGltZXJfaW50KQogICAgdC5zdGFydCgpCiAgICB0cnk6CiAgICAgICAgZGF0YSA9IGkyYy5yZWFkX2J5dGVfZGF0YSgweDZiLCAweDAwKQogICAgICAgICNwcmludCAiaTJjLnJlYWRfYnl0ZV9kYXRhKDB4NmIsIDB4MDApPSIsZGF0YQogICAgZXhjZXB0IElPRXJyb3I6CiAgICAgICAgZGF0YSA9IDB4MDAKCiAgICBpZihkYXRhID09IDB4Y2MpOgogICAgICAgIGkyYy53cml0ZV9ieXRlX2RhdGEoMHg2YiwgMHgwMCwgMHgwMCkKICAgICAgICBvcy5zeXN0ZW0oInN1ZG8gc2h1dGRvd24gLWggbm93IikKICAgICAgICB0aW1lLnNsZWVwKDYwKQoKICAgIGNwdV90bXA9ZGVjMkJDRChpbnQoZ2V0Q1BVdGVtcGVyYXR1cmUoKSwxMCkpCiAgICAjcHJpbnQoIkRFQlVHIGRlYzJCQ0QoaW50KGdldENQVXRlbXBlcmF0dXJlKCksMTApKToiLGRlYzJCQ0QoaW50KGdldENQVXRlbXBlcmF0dXJlKCksMTApKSkKICAgICNwcmludCgiREVCVUcgaW50KGdldENQVXRlbXBlcmF0dXJlKCksMTApOiIsaW50KGdldENQVXRlbXBlcmF0dXJlKCksMTApKQoKICAgIHRyeToKICAgICAgICBpMmMud3JpdGVfYnl0ZV9kYXRhKDB4NjksIDB4MWEsIGNwdV90bXApCiAgICBleGNlcHQgSU9FcnJvcjoKICAgICAgICBkYXRhID0gMHgwMAoKCiMjIyMjIyMjIyMjIyMjIyBNQUlOICMjIyMjIyMjIyMjIyMjIyMjCnQgPSB0aHJlYWRpbmcuVGltZXIoMC40MCwgdGltZXJfaW50KQp0LnN0YXJ0KCkKCndoaWxlIFRydWU6CiAgICNwcmludCgiREVCVUc6IGluc2lkZSBvZiB0aGUgbG9vcCIpCiAgIHRpbWUuc2xlZXAoMzApCgoK'
	upis_systemd_script_path = '/sbin/pico_i2c_service.py'


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
		group_setup.add_argument("-u", "--skip-setup-systemd", dest="skip_setup_systemd", help='', action="store_true")
		group_setup.add_argument("-w", "--skip-setup-progress", dest="skip_setup_progress", help='', action="store_true")
		group_setup.add_argument("-x", "--skip-setup-rtc", dest="skip_setup_rtc", help='', action="store_true")
		group_setup.add_argument("-y", "--skip-setup-serial", dest="skip_setup_serial", help='', action="store_true")
		group_setup.add_argument("-z", "--skip-setup-i2c", dest="skip_setup_i2c", help='', action="store_true")
		
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
			assert (serial.Serial)	# make sure its the serial port communication module, not data serialisation module
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
		
		if os.getuid() != 0:
			logging.error('Setup mode must be executed with sudo or as root!')
			return None

		# verify pip is installed
		#if sys.version_info[0] < 3:
		cmdret = self.runcmd('which pip')
		if cmdret[0] is not None:
			if cmdret[0]==0:
				logging.debug('pip ok')
			else:
				logging.warning('pip not installed, installing it')
				cmdret = self.runcmd('sudo apt update')
				if sys.version_info[0] < 3:
					cmdret = self.runcmd('sudo apt install -y python-pip')
				else:
					cmdret = self.runcmd('sudo apt install -y python3-pip')
				if cmdret[0] is not None:
					if cmdret[0]==0:
						logging.debug('pip installed')
					else:
						logging.error('Failed to install pip')
						return False
				else:
					logging.error('Error running pip install command')
					return False
		else:
			logging.error('Error checking pip presence')
			return False

		if not self.args.skip_setup_serial:
			if self.capability['serial'] is None:
				logging.warning('module pyserial not installed, installing it')
				self.install_module('pyserial')
			else:
				logging.debug('pyserial ok')

		if not self.args.skip_setup_i2c:
			if self.capability['smbus'] is None:
				logging.warning('module smbus not installed, installing it')
				self.install_module('smbus')
			else:
				logging.debug('smbus ok')

		if not self.args.skip_setup_progress:
			if self.capability['progress'] is None:
				logging.warning('module progress not installed, installing it')
				self.install_module('progress')
			else:
				logging.debug('smbus ok')
		
		if not self.args.skip_setup_i2c:
			try:
				self.capability['smbus'].SMBus(self.i2cbusid)
			except IOError as e:
				if e.errno == 2:
					logging.warning('seems that smbus is not configured, configuring it')

					# enable_uart= in /boot/config.txt and serial0 in /boot/cmdline.txt
					# sudo raspi-config nonint do_serial 2 # disable serial console, enable serial HW
					ret = self.get_service('get_serial')
					if ret is None or not ret:
						self.set_service('do_serial', 2)

					# raspi-config nonint get_i2c return 0
					# sudo raspi-config nonint do_i2c 0 # enable i2c
					ret = self.get_service('get_i2c')
					if ret is None or not ret:
						self.set_service('do_i2c', 0)

				else:
					logging.exception('Failed to verify smbus is working')	
			except:
				logging.warning('smbus module not available')

		if not self.args.skip_setup_rtc:
			self.set_in_file('dtoverlay=i2c-rtc,ds1307', 'dtoverlay=i2c-rtc,ds1307', '/boot/config.txt')
			self.set_in_file('dtparam=i2c1_baudrate=', 'dtparam=i2c1_baudrate=25000', '/boot/config.txt')

		if not self.args.skip_setup_systemd:

			if not os.path.exists(self.upis_systemd_script_path):
				logging.warning('pico systemd script does not exist, creating it at {0}'.format(self.upis_systemd_script_path))
				try:
					open('{0}'.format(self.upis_systemd_script_path), 'wb').write(base64.b64decode(self.upis_systemd_script))
					logging.warning('pico systemd script created at {0}'.format(self.upis_systemd_script_path))

					file_status = os.stat(self.upis_systemd_script_path)
					new_chmod = file_status.st_mode | stat.S_IXOTH | stat.S_IXGRP | stat.S_IXUSR
					logging.warning('Changing chmod of file {0} to {1}'.format(self.upis_systemd_script_path, oct(new_chmod)))
					os.chmod(self.upis_systemd_script_path, new_chmod)

				except:
					logging.exception('Failed to install pico systemd script to {0} and setup chmod'.format(self.upis_systemd_script_path))
			else:
				logging.warning('pico systemd script ok at {0}'.format(self.upis_systemd_script_path))
				
			if not os.path.exists(self.upis_systemd_path):
				logging.warning('pico systemd service definition does not exist, creating it at {0}'.format(self.upis_systemd_path))
				try:
					open('{0}'.format(self.upis_systemd_path), 'wb').write(base64.b64decode(self.upis_systemd))
					logging.warning('pico systemd service definition created at {0}'.format(self.upis_systemd_path))

					cmdret = self.runcmd("sudo systemctl daemon-reload")
					if cmdret[0] is not None:
						if cmdret[0]==0:
							logging.debug('systemcl reloaded')
						else:
							logging.error('Failed to reload systemcl')
							return False
					else:
						logging.error('Error reloading systemcl')
						return False

					cmdret = self.runcmd("sudo systemctl enable pico_i2c")
					if cmdret[0] is not None:
						if cmdret[0]==0:
							logging.debug('systemcl service pico_i2c enabled')
						else:
							logging.error('Failed to enable service pico_i2c')
							return False
					else:
						logging.error('Error enabling service pico_i2c')
						return False

					cmdret = self.runcmd("sudo systemctl start pico_i2c")
					if cmdret[0] is not None:
						if cmdret[0]==0:
							logging.debug('systemcl service pico_i2c started')
						else:
							logging.error('Failed to start service pico_i2c')
							return False
					else:
						logging.error('Error starting service pico_i2c')
						return False
				
				except:
					logging.exception('Failed to install pico systemd service definition to {0}'.format(self.upis_systemd_path))
			else:
				logging.warning('pico systemd service definition ok at {0}'.format(self.upis_systemd_path))

	def set_service(self, servicename, value):
		cmdret = self.runcmd("sudo raspi-config nonint {0} {1}".format(servicename, value))
		if cmdret[0] is not None:
			if cmdret[0]==0:
				logging.debug('Service {0} was set to {1}'.format(servicename, value))
				return True
			else:
				logging.error('Failed to set status of service {0} to {1}'.format(servicename, value))
				return None
		else:
			logging.error('Failed to set status of service {0} to {1}'.format(servicename, value))
			return None	

	# cmd output value: 0 -> enabled, 1 -> disabled
	def get_service(self, servicename):
		cmdret = self.runcmd("sudo raspi-config nonint {0}".format(servicename))
		if cmdret[0] is not None:
			if cmdret[0]==0:
				if cmdret[1].startswith('0'):
					logging.debug('Status of service {0} is {1}, True'.format(servicename, cmdret[1]))
					return True
				else:
					logging.debug('Status of service {0} is {1}, False'.format(servicename, cmdret[1]))
					return False
			else:
				logging.error('Failed to check status of service: {0}'.format(servicename))
				return None
		else:
			logging.error('Failed to check status of service:  {0}'.format(servicename))
			return None	

	def set_in_file(self, file_str, file_fullstr, file_name):
		cmdret = self.runcmd("grep -q '^{0}' {1}".format(file_str, file_name))
		if cmdret[0] is not None:
			if cmdret[0]==0:
				logging.debug('{0} ok in {1}'.format(file_str, file_name))
			else:
				logging.warning('configuring {0} in {1}'.format(file_fullstr, file_name))
				cmdret = self.runcmd("echo '{0}' | sudo tee -a {1}".format(file_fullstr, file_name))
				if cmdret[0] is not None:
					if cmdret[0]==0:
						logging.debug('{0} configured in {1}'.format(file_str, file_name))
					else:
						logging.error('Failed to configure {0} in {1}'.format(file_str, file_name))
						return False
				else:
					logging.error('Error configuring for {0} in {1}'.format(file_str, file_name))
					return False
		else:
			logging.error('Error checking for {0} in {1}'.format(file_str, file_name))
			return False

	def runcmd(self, cmd):
		try:
			logging.debug('Running command: "{0}"'.format(cmd))
			ret = getstatusoutput(cmd)
			logging.debug('Command finished with result code {0} and output "{1}"'.format(ret[0],ret[1]))
			return ret
		except:
			logging.exception('Failed to execute command')
			return (None, None)

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
