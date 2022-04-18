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
# NOTES:
# - Intel HEX file docs: https://en.wikipedia.org/wiki/Intel_HEX
# - One line fw update: # i2cget -y 1 0x69 0x38 w && i2cset -y 1 0x6b 0x00 0xff && sleep 2 && ./upis_fw.py ups_pico4_main_testing1.hex && sleep 5 && i2cget -y 1 0x69 0x38 w
# AUTHOR:       Vit SAFAR <PIco@safar.info>
# VERSION:      POC release 4
# CREATED:      16.4.2022
# REVISION:     TBD
#
# TODO:         
# - Script pre-requisities verification & installation (configure boot params, enable I2C&serial, etc). /boot/config.txt: dtparam=i2c_arm=on dtparam=i2c1_baudrate=25000
# - Script parametrization of: verbosity, serial port, serial baudrate, progress bar type, fw file, etc (accept script arguments)
# - Input FW file consistency verification (can be disabled)
# - Switch to bootloader mode in the script instead of the bash command line (can be disabled)
# - Check that the FW in the file is newer than the one already running (overridable) Is it possible to get the FW version via I2C? Or only via serial?
# - Make it py2 & py3 compatible (https://python-future.org/compatible_idioms.html)
# - Manage the pico_i2c.service
# - Enable RTC
# - Install pip2
#   wget https://bootstrap.pypa.io/pip/2.7/get-pip.py
#   python2 get-pip.py
# - get current FW
#   pi@rpi-upstest:~ $ i2cget -y 1 0x69 0x38 w
#   0x011d
# - i2cset -y 1 0x6b 0 0xbb # remote bootloader, 0xff for local BL
#
#===============================================================================

from __future__ import print_function
import serial
import time
import sys
import logging
from progress.bar import Bar

class upsPico:
    serial_port = None 
    serial_baudrate = None
    firmware_filename = None

    def __init__(self):
        logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s' )
        self.firmware_filename = sys.argv[1]
        self.serial_baudrate = 9600 
        self.serial_port = '/dev/serial0'
        
        try:
            self.upis = serial.Serial(port=self.serial_port,baudrate=self.serial_baudrate,timeout=0.001,rtscts=0,xonxoff=True)
        except:
            logging.exception('Failed to open serial port')

        if self.send_line(":020000040000FA\r"):
            logging.info('Serial link with UPIS verified')
            self.send_file()
        else:
            logging.error('Failed to confirm serial communication with UPIS')

    """
    4) Verify the content of the provided FW file by:
            a) validating crc
            b) validating format
            c) validating passed data syntax
    """
    def validate(self):
        valid=False
        #count number of lines
        lnum=1
        # open the FW file
        f = open(self.firmware_filename)
        # for each file line
        for line in f:
            #static  LEN ADDR1 ADDR2 TYPE  DATA     CKSUM
            #:       04  05    00    00    50EF2EF0 9A
            # parse the line
            target = re.match( r"^:([a-fA-F0-9]{2})([a-fA-F0-9]{2})([a-fA-F0-9]{2})([a-fA-F0-9]{2})([a-fA-F0-9]*)([a-fA-F0-9]{2}).$", line, re.M|re.I|re.DOTALL)
            # in case the data field does not have correct size
            if len(target.group(5))%2!=0:
                print "KO\nLine",lnum,': Invalid bytecode message!'
                sys.exit(4)
            # get the CRC valucalculate CRC
            crc1=int(line[-4:-1],16)
            # calculate the CRC value of the data read
            crc2=0    
            for i in range(1, len(line)-5, 2):
                #print line[i:i+2] 
                crc2+=int(line[i:i+2],16)
            # python cannot simulate byte overruns, so ugly math to be done 
            crc2%=256
            crc2=255-crc2+1
            crc2%=256
            # validate the CRC :)
            if crc1!=crc2:
                print "KO\nLine",lnum,': Invalid bytecode checksum! Defined:', crc1,'Calculated:', crc2
                sys.exit(4)
        
            # in case that the done command is detected, than finish
            if target.group(4)=='01':
                valid=True
                break
            lnum+=1
        # close the FW file
        f.close()
        if not valid:
            print "KO\n Termination signature not found in the firmware file."
            sys.exit(4)
        else:
            print 'OK'

    def send_file(self):
        try:
            fw_lines_total = sum(1 for line in open(self.firmware_filename) if line.startswith(':'))
            bar = Bar('Uploading firmware', max=fw_lines_total, suffix='%(percent).1f%% - %(eta)ds')
            f = open(self.firmware_filename)
            lnum = 0
            for line in f:
                lnum += 1
                if not self.send_line(line.strip()+"\r"):
                    logging.error('failed to ack the line {0}'.format(lnum))
                    break
                bar.next()
                if line[7:9]=='01':  # this is the last FW file line
                    break
            bar.finish()
        except:
            logging.exception('Failed to process firmware file')
            return False

    def send_line(self, line):
        try:
            for line in self.upis:
                pass
            self.upis.write(line.encode())
            return self.wait_ack()
        except:
            logging.exception('Failed to send data to UPIS')
            return False

    def wait_ack(self):
        try:
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
        except:
            logging.exception('Failed to recieve data ACK from UPIS')
            return False

upsPico()



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


''