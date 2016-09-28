'''
common_module.py
This module is for providing commonly used functions and classes
in other modules of CATOS_AA.
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

import os, serial, subprocess
from time import time, sleep
from datetime import datetime
from glob import glob

#------------------------------------------------------------------------------------

def writeFile(fileName, txt):
# Function for writing texts into a file
    txt += '\n'
    file = open(fileName, 'a')
    if file:
        file.write(txt)
        file.close()
    else:
        raise Exception("unable to open [" + fileName + "]")

#------------------------------------------------------------------------------------

def chk_fps(last_fps_timestamp, fps_cnt):
# checking 'Frame per Second'
    curr_time = time()
    fps = -1
    if curr_time - last_fps_timestamp > 1:
        fps = int(fps_cnt)
        fps_cnt = 0
        last_fps_timestamp = time()
    fps_cnt += 1
    return fps, fps_cnt, last_fps_timestamp

#------------------------------------------------------------------------------------

def get_time_stamp():
    ts = datetime.now()
    ts = ('%.4i_%.2i_%.2i_%.2i_%.2i_%.2i_%.6i')%(ts.year, ts.month, ts.day, ts.hour, ts.minute, ts.second, ts.microsecond)
    return ts

#------------------------------------------------------------------------------------

def get_log_file_path(output_folder):
    return os.path.join(os.getcwd(), output_folder, "%s.log"%get_time_stamp())

#------------------------------------------------------------------------------------

def update_log_file_path(output_folder, log_file_path):
    if not os.path.isfile(log_file_path):
        while not os.path.isfile(log_file_path): # if there's no log file (will be made in 'session_initialization' of 'AAS')
            for f in glob(os.path.join(output_folder, "*.log")): log_file_path = f # update the log file path
            sleep(0.1)
    return log_file_path

#------------------------------------------------------------------------------------

def chk_session_time(start_hour, end_hour):
# Check whether it's middle of the session time or not.
    if start_hour != -1 and end_hour != -1:
        curr_time = datetime.now()
        if start_hour < end_hour: # day schedule such as 10 ~ 22
            if start_hour > curr_time.hour or end_hour <= curr_time.hour: return False
        else: # night schedule such as 22 ~ 10
            if start_hour > curr_time.hour >= end_hour: return False
    return True

#-------------------------------------------------------------------------------------

def chk_resource_usage(program_log_path):
    ### Check & logging overall cpu & memory usage
    cmd = ["top", "-l", "1"]
    ps = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    (stdout, stderr) = ps.communicate()
    values = stdout.split("\n")
    log_msg = 'Resource Usage Check @ %s\n===========================\n---(Overall)-------------\n'%get_time_stamp()
    log_msg += '%s\n%s\n%s'%(values[3], values[6], values[7])
    writeFile(program_log_path, log_msg)

    ### Check & logging AA program's processes' resource usage
    colNames = ["command", "pid", "%cpu", "%mem", "vsize"]
    value_list = []
    base_cmd = ["ps", "-a"]
    for colName in colNames:
        cmd = base_cmd + ["-o", colName]
        ps = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        (stdout, stderr) = ps.communicate()
        values = stdout.split("\n")[1:]
        values = [token.strip() for token in values if token != '']
        value_list.append(values)

    my_result_idx = []
    for i in range(len(value_list[0])):
        filename = value_list[0][i].split(" ")[-1]
        if filename.startswith('AA.'): my_result_idx.append(i) # append the index, if this is the process caused by AA program
    ### write header
    log_msg = '---(AA\'s processes)-------------\n'
    for col_idx in range(1, len(colNames)): log_msg += colNames[col_idx] + ', '
    log_msg = log_msg.rstrip(', ')
    log_msg += "\n----------------"
    writeFile(program_log_path, log_msg)
    ### write resource-usage
    for i in range(len(my_result_idx)):
        log_msg = ''
        for col_idx in range(1, len(colNames)):
            log_msg += value_list[col_idx][my_result_idx[i]] + ', '
        log_msg = log_msg.rstrip(', ')
        writeFile(program_log_path, log_msg)
    writeFile(program_log_path, "===========================\n")

#------------------------------------------------------------------------------------




