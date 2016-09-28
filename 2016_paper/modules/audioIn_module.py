'''
audioIn_module.py
This is for constantly listening though a microphone
and recording only when a set of given condition was
fulfilled such as RMS amplitude is over a threshold.
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
from copy import copy
from math import sqrt
from glob import glob

import numpy as np
from scipy.signal import lfilter, firwin
import pyaudio

from common_module import writeFile, chk_fps, get_time_stamp, chk_session_time, update_log_file_path

FLAG_INITIAL_DELAY = True # wait 1.5 minutes before actual function starting

FLAG_DEBUG = False
LOG = ''


#------------------------------------------------------------------------------------

def audioIn_run(ai_conn, log_file_name, output_folder, session_start_hour, session_end_hour):
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

    IAD_inst = Input_AudioData(cwd, output_folder) # Initialize the streaming-audio-data from the mic
    last_fps_timestamp = time()
    fps_cnt = 0
    flag_session_changed_to_off = False
    flag_session_changed_to_on = False

    while True:
        if chk_session_time(session_start_hour, session_end_hour) == False:
            if flag_session_changed_to_off == False: # 1st run after finishing the session-time
                flag_session_changed_to_off = True
                flag_session_changed_to_on = False
            if ai_conn.poll(): # check whether there's any message arrive through the pipe
                msg = ai_conn.recv() # receive the message
                if msg == 'q': break
            sleep(1)
            continue
        else:
            if flag_session_changed_to_on == False: # 1st run after starting the session-time
                flag_session_changed_to_off = False
                flag_session_changed_to_on = True
                LOG = update_log_file_path(output_folder, LOG)

        audioData = IAD_inst.listen() # Listen to the mic
        #if audioData != None: # some data returned
        if IAD_inst.rms_amplitude > IAD_inst.th_to_start_recording:
            IAD_inst.has_been_quiet_since = -1 # it's not quiet
            IAD_inst.flag_data_recording = True

        IAD_inst.last_audio_data.append(copy(IAD_inst.audio_data)) # keeping last data for a while
        if len(IAD_inst.last_audio_data) > 12: IAD_inst.last_audio_data.pop(0) # don't store more than 12 datasets(about a half second)

        if IAD_inst.flag_data_recording:
            IAD_inst.data_recording()
            if IAD_inst.rms_amplitude < IAD_inst.th_to_be_quiet: IAD_inst.quiet_now()

        ### FPS-check
        if FLAG_DEBUG:
            fps, fps_cnt, last_fps_timestamp = chk_fps(last_fps_timestamp, fps_cnt)
            if fps != -1: print "LoopPerSecond-check from audioIn module : %i"%fps

        if ai_conn.poll(): # check whether there's any message arrive through the pipe
            msg = ai_conn.recv() # receive the message
            if msg == 'q': break

#------------------------------------------------------------------------------------

class Input_AudioData:
    def __init__(self, cwd, output_folder):
        self.cwd = cwd
        self.output_folder = output_folder
        self.format = pyaudio.paInt16
        self.sampWidth = 2
        self.channels = 1
        self.sr = 44100 # sampler rate
        #self.sr = 22050
        self.nyq_rate = self.sr/2.0
        self.cutoff_hz = 500.0 # cut-off frequency of the FIR filter
        self.short_normalize = (1.0/32768.0)
        self.input_block_time = 0.02
        self.input_frames_per_block = int(self.sr*self.input_block_time)
        self.freq_res = self.sr/float(self.input_frames_per_block) # Frequency Resolution

        self.audio_tmp_data = None
        self.rms_amplitude = None
        self.pa = pyaudio.PyAudio()
        self.device_index = self.find_input_device()
        self.stream = self.open_mic_stream()

        self.th_to_start_recording = 0.04 # RMS amplitude to start recording
        self.th_to_be_quiet = 0.03 # RMS amplitude to be 'quiet' moment
        self.flag_data_recording = False
        self.audio_data = None # current audio-data
        self.last_audio_data = [] # audio-data from last readings
        self.recordingData = [] # audio-data accumulated with the audio_data for storing as a wave file later
        self.recordingData_startTime = None
        self.maximum_q_duration = 3 # in seconds. Recording persists for this amount of time even it has been quiet.
        self.has_been_quiet_since = -1 # To check how long it has been quiet.        

    #---------------------------------------------------------------------------------

    def stop(self):
        self.stream.close()
        self.pa.terminate()
        
    #---------------------------------------------------------------------------------

    def find_input_device(self):
        device_index = None            
        for i in range( self.pa.get_device_count() ):     
            devinfo = self.pa.get_device_info_by_index(i)   
            #print( "Device %d: %s"%(i,devinfo["name"]) )
            for keyword in ["input"]: # "microphone", "headset", "icecam"
                if keyword in devinfo["name"].lower():
                    print( "Found an audio-input: device %d - %s"%(i,devinfo["name"]) )
                    device_index = i
        if device_index == None:
            print( "No preferred input found; using default input device." )
        return device_index # use the last device

    #---------------------------------------------------------------------------------

    def open_mic_stream( self ):
        stream = self.pa.open(   format = self.format,
                                 channels = self.channels,
                                 rate = self.sr,
                                 input = True,
                                 input_device_index = self.device_index,
                                 frames_per_buffer = self.input_frames_per_block )
        return stream

    #---------------------------------------------------------------------------------

    def listen(self):
        try:
            self.audio_data = np.fromstring(self.stream.read(self.input_frames_per_block), dtype=np.short)
            self.audio_data = self.audio_data * self.short_normalize
            #self.audio_data = np.diff(self.audio_data, n = 1)
            self.audio_data = self.FIR_filter(self.audio_data)
            self.audio_data = self.audio_data * 32768         
            #self.audio_data = self.audio_data.tolist()
            self.rms_amplitude = self.get_rms()
            self.audio_data = self.audio_data.tolist()
        except IOError, e:
            print( "Error : %s"%(e) ) # When an error (such as buffer_overflow) occurs
            self.listen() # read the data from mic again.
    
    #---------------------------------------------------------------------------------

    '''
    def get_data(self):
        self.listen()
        return abs(np.fft.fft(self.audio_tmp_data))[:self.input_frames_per_block/2]
    '''

    #---------------------------------------------------------------------------------

    def FIR_filter(self, signal):
    # FIR High pass filter
        numtaps = 31 # length of the filter (number of coefficients; filter order + 1)
        fir_coeff = firwin(numtaps, [self.cutoff_hz/self.nyq_rate, 0.99], pass_zero=False) # Use firwin to create a lowpass FIR filter
        filtered_signal = lfilter(fir_coeff, 1.0, signal)
        return filtered_signal

    #---------------------------------------------------------------------------------

    def data_recording(self):
        if self.recordingData == []: # This is the beginning of storing the audio_data
            if FLAG_DEBUG: print "Sound-recording starts @ %s"%get_time_stamp()
            self.recordingData_startTime = time()
            self.wave_file_path = os.path.join(self.cwd, self.output_folder, "%s.wav"%get_time_stamp())
            writeFile(LOG, '%s, Start an audio-recording. Wave-file path:, %s'%(get_time_stamp(), self.wave_file_path))
            ### put last data into the recordingData
            for i in range(len(self.last_audio_data)):
                self.recordingData.append(self.last_audio_data[i])
        self.recordingData.append(self.audio_data) # append the current data

        sound_duration = time() - self.recordingData_startTime
        # if recording time passed over 10 seconds, generate the wave file at this point, and record again.
        if sound_duration > 10:
            self.data_write_to_wave(sound_duration)
            self.flag_data_recording = True
            writeFile(LOG, '%s, Generated a wave file in the middle of the recording:, %s'%(get_time_stamp(), self.wave_file_path))            

    #---------------------------------------------------------------------------------

    def quiet_now(self):
        curr_time = time()
        if self.has_been_quiet_since == -1: self.has_been_quiet_since = time()
        else:
            if curr_time - self.has_been_quiet_since > self.maximum_q_duration:
            # quiet moment is longer than maximum-quiet-duration
                writeFile(LOG, '%s, Finish the audio-recording'%get_time_stamp())
                sound_duration = self.recordingData_startTime - curr_time
                self.data_write_to_wave(sound_duration) # write the recorded sound to a wave file

    #---------------------------------------------------------------------------------

    def data_write_to_wave(self, sound_duration):
        if FLAG_DEBUG: print "Sound-recording ends @ %s"%get_time_stamp()

        snd_file = wave.open(self.wave_file_path, 'wb')
        durSamps = int(sound_duration*self.sr)
        snd_file.setparams((self.channels, self.sampWidth, self.sr, durSamps, 'NONE', 'noncompressed'))
        snd_file.writeframes(np.array(self.recordingData, dtype=np.int16).tostring())
        #snd_file.writeframes(self.recordingData.tostring())
        snd_file.close()

        self.flag_data_recording = False
        self.recordingData = []
        self.has_been_quiet_since = -1

    #---------------------------------------------------------------------------------

    def get_rms(self):
    # RMS Amplitude
        count = len(self.audio_data)/2
        sum_squares = 0.0
        n = self.audio_data * self.short_normalize
        n = n ** 2
        sum_squares = sum(n)
        rms = sqrt(sum_squares/count)
        return rms

#------------------------------------------------------------------------------------
