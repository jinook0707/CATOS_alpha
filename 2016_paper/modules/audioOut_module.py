'''
audioOut_module.py
This is for playing auditory stimuli to subject(s)
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
import os, wave

from time import time, sleep
from glob import glob
from random import randint, uniform

import pyaudio

from common_module import writeFile, chk_fps, get_time_stamp, chk_session_time, update_log_file_path

FLAG_INITIAL_DELAY = False # wait 1.5 minutes before actual function starting

FLAG_DEBUG = False
LOG = ''

#------------------------------------------------------------------------------------

def audioOut_run(ao_conn, log_file_name, output_folder, snd_files, session_start_hour, session_end_hour):
    global LOG
    cwd = os.getcwd()
    LOG = log_file_name

    if FLAG_INITIAL_DELAY:
        func_start_time = time()
        while True:
            elapsed_time = time() - func_start_time
            #print "Elapsed time: %i (s)"%elapsed_time
            if elapsed_time > 90: # wait for 1.5 minutes before actual starting
                break

    OAD_inst = Output_AudioData(snd_files)
    last_fps_timestamp = time()
    fps_cnt = 0
    flag_session_changed_to_off = False
    flag_session_changed_to_on = False

    while True:
        if chk_session_time(session_start_hour, session_end_hour) == False:
            if flag_session_changed_to_off == False: # 1st run after finishing the session-time
                OAD_inst.close_output_streams()
                flag_session_changed_to_off = True
                flag_session_changed_to_on = False
            if ao_conn.poll(): # check whether there's any message arrive through the pipe
                msg = ao_conn.recv() # receive the message
                if msg == 'q': break
            sleep(1)
            continue
        else:
            if flag_session_changed_to_on == False: # 1st run after starting the session-time
                OAD_inst.open_output_streams()
                flag_session_changed_to_off = False
                flag_session_changed_to_on = True
                LOG = update_log_file_path(output_folder, LOG)

        ### FPS-check
        if FLAG_DEBUG:
            fps, fps_cnt, last_fps_timestamp = chk_fps(last_fps_timestamp, fps_cnt)
            if fps != -1: print "LoopPerSecond-check from audioOut module : %i"%fps

        if ao_conn.poll(): # check whether there's any message arrive through the pipe
            msg = ao_conn.recv() # receive the message
            if msg == 'q': break
            elif msg.startswith('play_sound:'):
                msg = msg.split(":")
                OAD_inst.play_sound(msg[1])
            elif msg == '4th_speaker_test':
                OAD_inst.flag_4th_speaker_test = True
            elif msg == 'SWS_test':
                OAD_inst.flag_SWS_test = True
            elif msg == 'NVS_test':
                OAD_inst.flag_NVS_test = True

        sleep(0.05)

#------------------------------------------------------------------------------------

class Output_AudioData:

    def __init__(self, snd_files):
        ### load the feeding-sound
        self.chunk = 1024

        self.wf = {}
        for k, v in snd_files.items():
            self.wf[k] = wave.open(snd_files[k], 'rb')
        '''
        self.wf["name"] = wave.open(snd_files["name"], 'rb')
        #self.wf["arbitrary_name_00"] = wave.open(snd_files["arbitrary_name_00"], 'rb')
        self.wf["button1"] = wave.open(snd_files["button1"], 'rb')
        self.wf["button2"] = wave.open(snd_files["button2"], 'rb')
        self.wf["button3"] = wave.open(snd_files["button3"], 'rb')
        self.wf["button1_SWS"] = wave.open(snd_files["button1_SWS"], 'rb')
        self.wf["button2_SWS"] = wave.open(snd_files["button2_SWS"], 'rb')
        self.wf["button3_SWS"] = wave.open(snd_files["button3_SWS"], 'rb')
        self.wf["button1_NVS"] = wave.open(snd_files["button1"], 'rb')
        self.wf["button2"] = wave.open(snd_files["button2"], 'rb')
        self.wf["button3"] = wave.open(snd_files["button3"], 'rb')
        self.wf["foil"] = wave.open(snd_files["foil"], 'rb')
        self.wf["neg_feedback1"] = wave.open(snd_files["neg_feedback1"], 'rb')
        self.wf["neg_feedback2"] = wave.open(snd_files["neg_feedback2"], 'rb')
        '''
        self.pa = pyaudio.PyAudio()
        self.stream = []

        self.flag_4th_speaker_test = False
        self.flag_SWS_test = False
        self.flag_NVS_test = False

    #---------------------------------------------------------------------------------

    def open_output_streams(self):
        # it assumes that all the wave files have the same format, channels, and sampler_rates
        # with the <name> sound
        self.built_in_output_idx, self.device_index_list = self.find_output_device()
        ### 1st stream is with the built-in output
        self.stream.append( self.pa.open(format = self.pa.get_format_from_width(self.wf["name"].getsampwidth()),
                                        channels = 1,
                                        rate = self.wf["name"].getframerate(),
                                        output_device_index = self.built_in_output_idx,
                                        output = True) )
        ### 3 streams using the usb-output
        for i in range(len(self.device_index_list)):
            try:
                self.stream.append( self.pa.open(format = self.pa.get_format_from_width(self.wf["name"].getsampwidth()),
                                                channels = 1,
                                                rate = self.wf["name"].getframerate(),
                                                output_device_index = self.device_index_list[i],
                                                output = True) )
            except:
                pass

    #---------------------------------------------------------------------------------

    def close_output_streams(self):
        if len(self.stream) > 0:
            for i in range(len(self.stream)):
                self.stream[i].close()
        self.stream = []

    #---------------------------------------------------------------------------------

    def find_output_device(self):
        built_in_output_idx = -1
        device_index_list = []            
        for i in range( self.pa.get_device_count() ):     
            devinfo = self.pa.get_device_info_by_index(i)
            if devinfo["maxOutputChannels"] > 0:
                if "output" in devinfo["name"].lower():
                    print( "Found the built-in audio-output: device %d - %s"%(i,devinfo["name"]) )
                    built_in_output_idx = int(i)
                if "via usb dongle" in devinfo["name"].lower():
                    print( "Found an usb-audio-output: device %d - %s"%(i,devinfo["name"]) )
                    device_index_list.append(i)
        if device_index_list == []:
            print( "No preferred input found; using default input device." )
        return built_in_output_idx, device_index_list

    #---------------------------------------------------------------------------------

    def play_sound(self, snd_key):
        '''
        if snd_key == 'button1' : stream = self.stream[1] #self.stream[1] # usb-output
        elif snd_key == 'button2': stream = self.stream[3] #self.stream[3] switched the position between button2 & 3
        elif snd_key == 'button3': stream = self.stream[2] #self.stream[2] # usb-output
        elif snd_key == 'foil':
            stream_idx = randint(1, 3)
            stream = self.stream[stream_idx] # randomly choose a stream if it's a foil sound
        else: stream = self.stream[0] # built-in output stream

        if self.flag_4th_speaker_test == True:
            stream = self.stream[0]
            self.flag_4th_speaker_test = False
        '''
        stream = self.stream[0]

        if self.flag_SWS_test == True:
            snd_key += '_SWS'
            self.flag_SWS_test = False
        elif flag_NVS_test == True:
            snd_key += '_NVS'
            self.flag_NVS_test = False

        audio_output_data = self.wf[snd_key].readframes(self.chunk)
        while audio_output_data != '':
            stream.write(audio_output_data)
            audio_output_data = self.wf[snd_key].readframes(self.chunk)
        self.wf[snd_key].rewind()

        if snd_key == 'foil':
            writeFile(LOG, '%s, Played the <%s> sound through a stream #%i'%(get_time_stamp(), snd_key, stream_idx))
        else:
            writeFile(LOG, '%s, Played the <%s> sound'%(get_time_stamp(), snd_key))

#------------------------------------------------------------------------------------
