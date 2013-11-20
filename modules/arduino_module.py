'''
arduino_module.py
This is for CATOS_AA for sending and receiving 
messages to Arduino-chip to control sensors and actuators.
--------------------------------------------------------------------
Copyright (C) 2013 Jinook Oh (jinook.oh@univie.ac.at)

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
'''

import os, serial
from glob import glob
from time import time, sleep

from common_module import writeFile, get_time_stamp, update_log_file_path
from error_handler_module import AOException

#-------------------------------------------------------------------------------------

class Arduino_module(object):
    def __init__(self, output_folder):
        self.output_folder = output_folder
        self.log_file_path = ''
        ARDUINO_USB_GLOB = "/dev/cu.usbmodem*"
        ARDUINO_PORT = ''
        for aConn in self.serial_scan(ARDUINO_USB_GLOB):
            ARDUINO_PORT = aConn.name
        if str(ARDUINO_PORT) == '':
            msg = 'Failed to find the Arduino chip.'
            raise AOException(msg)
        msg = str(ARDUINO_PORT) + " connected."
        print msg
        self.aConn = aConn

    #---------------------------------------------------------------------------------

    def try_open(self, port):
    # function for Arduino-chip connection
        try:
            port = serial.Serial(port, 9600, timeout = 0)
        except serial.SerialException:
            return None
        else:
            return port

    #---------------------------------------------------------------------------------

    def serial_scan(self, ARDUINO_USB_GLOB):
    # function for Arduino-chip connection
        for fn in glob(ARDUINO_USB_GLOB):
            port = self.try_open(fn)
            if port is not None:
                yield port

    #---------------------------------------------------------------------------------

    def send(self, msg=''):
        self.aConn.write(msg) # send a message to Arduino
        sleep(0.2)
        self.aConn.flushOutput() # flush the serial connection
        self.log_file_path = update_log_file_path(self.output_folder, self.log_file_path)
        if os.path.isfile(self.log_file_path): writeFile(self.log_file_path, "%s, Message - '%s' was sent to Arduino"%(get_time_stamp(), msg))          

    #---------------------------------------------------------------------------------

    def receive(self, header, timeout):
    # receive an intended(header-matching) message from the Arduino-chip for timeout-time
        startTime = time()
        while True:
            ### try to get the intended message only for timeout-time
            if timeout != None:
                currTime = time()
                if currTime - startTime > timeout:
                    msg = None
                    break
            msg = self.receive_a_msg(timeout)
            if msg == None: break # 'msg = None' means 'receive_a_msg' function tried to get a message for timeout-time
            else:
                msg = msg.strip("\r\n")
                msg = msg.split(",")
                if header == 'button':
                    if msg[0].startswith('button'): break
                else:
                    if msg[0] == header: break # Only if the header matches, quit the loop. Otherwise, keep receiving message.
        if msg != None:
            self.aConn.flushInput()
            if msg[len(msg)-1] == 'EOM': msg.pop(len(msg)-1) # delete 'EOM'
        return msg

    #---------------------------------------------------------------------------------

    def receive_a_msg(self, timeout):
    # receive a message from the Arduino-chip for timeout-time
        startTime = time()
        msg = self.aConn.read()
        while msg[-3:] != "EOM": # End Of Message
            ### try to get the intended message for 1 second
            if timeout != None:
                currTime = time()
                if currTime - startTime > timeout:
                    msg = None
                    break
            msg += self.aConn.read()
        return msg

#------------------------------------------------------------------------------------
