import wave, Queue
from os import path, mkdir
from time import time, sleep
from datetime import datetime
from copy import copy
from glob import glob

import numpy as np
import pyaudio

from modules.misc_funcs import writeFile, get_time_stamp, chk_fps, chk_msg_q 

# ===========================================================

class AudioIn:
    def __init__(self, parent):
        self.parent = parent
        self.input_block_time = 0.1
        self.fps = int(1.0/self.input_block_time)
        self.buff_sz = self.fps * 3 # buffer size is equivalent to number of frame for 3 seconds  
        self.pa = pyaudio.PyAudio()
        self.dev_keyword = "USB Dongle" # keyword to find the audio device
        self.dev_idx, self.dev_info = self.find_input_dev()
        self.rp = dict(format=pyaudio.paInt16, sampWidth=2, channels=1, sampleRate=int(self.dev_info['defaultSampleRate'])) # parameters for recording
        self.rp["input_frames_per_block"] = int(self.rp["sampleRate"] * self.input_block_time)
        self.rp["freq_res"] = self.rp["sampleRate"] / float(self.rp["input_frames_per_block"]) # frequency resolution
        self.dMax = 2 ** (8*self.rp["sampWidth"]) # max data value
        self.cutoff_hz = 1000
        self.stop_latency = 1 # time (seconds) of no valid data to record (to stop recording)
        self.msg_q = Queue.Queue()
        writeFile(self.parent.log_file_path, '%s, [audioIn], audioIn mod init.\n'%(get_time_stamp()))
        
    # --------------------------------------------------

    def run(self):
        aDataBuff = [] # buffer for audio data
        r_cnt = 0 # counting how many new frames were appended after last writing to WAV
        last_valid_time = -1 # last time when data was valid to record
        # writing to WAV file occurs once per second
        snd_file = None
        is_recording = False
        fps=0; prev_fps=[]; prev_fps_time=time()
        stream = self.open_mic_stream()
        writeFile(self.parent.log_file_path, "%s, [audioIn], 'run' starts.\n"%(get_time_stamp()))
        num_of_IOErr = 0
        while True:
            fps, prev_fps, prev_fps_time = chk_fps('audioIn', fps, prev_fps, prev_fps_time, self.parent.log_file_path)
            
            msg_src, msg_body, msg_details = chk_msg_q(self.msg_q) # listen to a message
            if msg_src == 'main':
                if msg_body == 'quit':
                    if is_recording == True and r_cnt > 0:
                        snd_file = self.finish_rec(aDataBuff, snd_file, r_cnt, prev_fps)
                        is_recording = False
                    break
            
            try:
                ### get audio data
                aDataBuff.append( np.fromstring(stream.read(self.rp["input_frames_per_block"], exception_on_overflow=False),dtype=np.short).tolist() )
                if len(aDataBuff) > self.buff_sz: aDataBuff.pop(0)
                
                ### record to file
                if is_recording == True:
                    r_cnt += 1
                    if r_cnt > (self.fps*2):
                        snd_file.writeframes( np.array(aDataBuff[-(self.fps*2):], dtype=np.int16).tostring() )
                        r_cnt = 0
            
                ### check data to record
                _fData = np.asarray( abs(np.fft.fft(aDataBuff[-1]))[:self.rp["input_frames_per_block"]/2] )
                _d = _fData / self.dMax * 100 # data range 0~100
                _d = _d[self.cutoff_hz/self.rp["freq_res"]:] # cut off low frequency data
                if np.sum(_d) > _d.shape[0] and np.average(_d) > (np.median(_d)*1.5):
                # Sum of data is bigger than the length of data : each data is bigger than 1 on average
                # Average is bigger than median*1.5 : amplitude is more concentrated in some areas
                    last_valid_time = time()
                    if is_recording == False: # not recording
                        ### start recording
                        is_recording = True
                        r_cnt = 0
                        n_ = datetime.now()
                        folder = path.join(self.parent.output_folder, '%.4i_%.2i_%.2i'%(n_.year, n_.month, n_.day))
                        if path.isdir(folder) == False: mkdir(folder)
                        wav_fp = path.join( folder, '%s.wav'%(get_time_stamp()) )
                        snd_file = wave.open(wav_fp, "wb")
                        snd_file.setparams( (self.rp["channels"], self.rp["sampWidth"], self.rp["sampleRate"], 0, "NONE", "noncompressed") )
                        snd_file.writeframes( np.array(aDataBuff[-(self.fps*2):], dtype=np.int16).tostring() )
                        writeFile(self.parent.log_file_path, '%s, [audioIn], start to write WAV, %s.\n'%(get_time_stamp(), wav_fp))
                else:
                    if is_recording == True: # currently recording
                        if time()-last_valid_time > self.stop_latency: # there was no valid data to record for some time
                            ### stop recording
                            is_recording = False
                            snd_file = self.finish_rec(aDataBuff, snd_file, r_cnt, prev_fps) 

            except IOError, e:
                if num_of_IOErr < 10:
                    msg_ = "%s, [audioIn], IOError : %s\n"%(get_time_stamp(), e)
                    writeFile(self.parent.log_file_path, msg_)
                num_of_IOErr += 1
                sleep(self.input_block_time/2)
        stream.close()
        self.stop()
        writeFile(self.parent.log_file_path, "%s, [audioIn], 'run' stopped.\n"%(get_time_stamp()))

    # --------------------------------------------------
    
    def finish_rec(self, aDataBuff, snd_file, r_cnt, prev_fps):
        if r_cnt > 0:
            snd_file.writeframes( np.array(aDataBuff[-r_cnt:],dtype=np.int16).tostring() )
        snd_file.close()
        writeFile(self.parent.log_file_path, '%s, [audioIn], finished writing WAV, recent-fps %s.\n'%(get_time_stamp(), str(prev_fps)))
        snd_file = None
        return snd_file

    # --------------------------------------------------
    
    def stop(self):
        self.pa.terminate()
        writeFile(self.parent.log_file_path, '%s, [audioIn], audioIn mod stopped.\n'%(get_time_stamp()))
    
    # --------------------------------------------------    

    def find_input_dev(self):
        dev_idx = None
        for i in range(self.pa.get_device_count()):
            devinfo = self.pa.get_device_info_by_index(i)
            print("Device %d: %s"%(i,devinfo["name"]))
            if (self.dev_keyword.lower() in devinfo["name"].lower()) and (devinfo["maxInputChannels"]>0):
                print("Found an audio-input: device %d - %s"%(i,devinfo["name"]))
                dev_idx = i
                break
        if dev_idx == None:
            print("No preferred audio-input found; Using the device 0 [%s]"%(self.pa.get_device_info_by_index(0)["name"]))
            dev_idx = 0
        dev_info = self.pa.get_device_info_by_index(dev_idx)
        return dev_idx, dev_info

    # --------------------------------------------------    

    def open_mic_stream(self):
        stream = self.pa.open( format=self.rp["format"], 
                               channels=self.rp["channels"], 
                               rate=self.rp["sampleRate"],
                               input=True,
                               input_device_index=self.dev_idx,
                               frames_per_buffer=self.rp["input_frames_per_block"] )
        return stream

# ===========================================================



