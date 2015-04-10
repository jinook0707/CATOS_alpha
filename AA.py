'''
CATOS_AA
Computer Aided Training/Observing System; Agent on Animals

This program is for getting percepts from the environment
and determining whether it records the video and/or auditory data.
It will also deal with some other possible sensors and actuators.
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

import os, sys #, multiprocessing
from billiard import Process, Pipe, forking_enable

from shutil import rmtree
from time import time, localtime, sleep
from random import randint, uniform, choice, shuffle
from copy import copy

import smtplib
from email.MIMEMultipart import MIMEMultipart
from email.MIMEBase import MIMEBase
from email.MIMEText import MIMEText
from email.Utils import COMMASPACE, formatdate
from email import Encoders
from email.mime.text import MIMEText

from numpy import median ###

from modules.common_module import writeFile, chk_fps, get_time_stamp, chk_session_time, get_log_file_path, update_log_file_path, chk_resource_usage
from modules.audioIn_module import audioIn_run
from modules.audioOut_module import audioOut_run
from modules.videoIn_module import videoIn_run
from modules.arduino_module import Arduino_module
from utils import Util_video_converter as uvc
from utils import Util_snd_tag as ust
from utils import Util_m_drawer as umd
from utils import Util_MoveF as umf

### parameters
CWD = os.getcwd()
OUTPUT_FOLDER = '/Users/catos01/catos/output'
PROGRAM_LOG_PATH = '/Users/catos01/catos/log.txt' # this log is only for checking programming issues, not for training/observing/recording issues.
NUMBER_OF_CAMERAS = 1
FLAG_FFMPEG_ON_THE_RUN = False # if this is True. JPEG files will be made into one mp4 movie file on the run
FLAG_RTOI = False # Repeat Trial On Incorrect-response (For button-press trials)
FLAG_BALANCE_CORRECTNESS = True # If True, correct responses will be guided for animal to reach equal amount of correct response by eliminating choices already corrected more.

FROZEN_TIME_ON_INCORRECT = 40 # (Punishment time) When the response was incorrect, 
# the feeding-system doesn't react for this amount of time. (in seconds)
# Works only when RTOI is True.

TRIAL_LENGTH = 60 # in seconds
TRIAL_INTERVAL = [10, 25] # Inter-Trial Interval (in minutes). 1st int = minimum ITI, 2nd int = maximum ITI
MAX_FEEDING_CNT = 30 # maximum number feeding per session
MAX_TRIAL_CNT = 50 # maximum number of trials including correct + incorrect trials. (but not timeout)

RESULT_CSV_HEADER = 'Trial#, Trial_start_time, Correct_response, Response, Response_time, Correctness, Actively_Involved_Individual, Additional_Info'

#OBSOLETE# FLAG_EMAIL_NOTIFICATION = False # sending a log file through email?
EMAIL_SENDER = 'ohj4@univie.ac.at'
EMAIL_RECEIVER = 'ohj4@univie.ac.at'

SOUND_FILES = {}
SOUND_FILES["name"] = "/Users/catos01/catos/input/media/c_hindung_kkamang.wav"
SOUND_FILES["button1"] = "/Users/catos01/catos/input/media/button1_donggran.wav"
SOUND_FILES["button2"] = "/Users/catos01/catos/input/media/button2_samgak.wav"
SOUND_FILES["button3"] = "/Users/catos01/catos/input/media/button3_nemo.wav"
SOUND_FILES["button1_SWS"] = "/Users/catos01/catos/input/media/button1_donggran_SWS.wav"
SOUND_FILES["button2_SWS"] = "/Users/catos01/catos/input/media/button2_samgak_SWS.wav"
SOUND_FILES["button3_SWS"] = "/Users/catos01/catos/input/media/button3_nemo_SWS.wav"
SOUND_FILES["button1_NVS"] = "/Users/catos01/catos/input/media/button1_donggran_NVS.wav"
SOUND_FILES["button2_NVS"] = "/Users/catos01/catos/input/media/button2_samgak_NVS.wav"
SOUND_FILES["button3_NVS"] = "/Users/catos01/catos/input/media/button3_nemo_NVS.wav"
SOUND_FILES["foil"] = "/Users/catos01/catos/input/media/button4_yukgak.wav"
SOUND_FILES["neg_feedback1"] = "/Users/catos01/catos/input/media/AudFB_Neg1.wav"
SOUND_FILES["neg_feedback2"] = "/Users/catos01/catos/input/media/AudFB_Neg2.wav"
SND_NAME_IDX = 0
SND_BUTTON1_IDX = 1
SND_BUTTON2_IDX = 2
SND_BUTTON3_IDX = 3
SND_FOIL_IDX = 4
BUTTON_TEXT = [None, 'button1', 'button2', 'button3', 'foil']

# If SESSION_START_HOUR or SESSION_END_HOUR is -1, the program will start and keep running.
# (After short period of time-currently 2 min.-, the session starts.)
SESSION_START_HOUR = 8
SESSION_END_HOUR = 20

### if output folder doesn't exist, make one
OUTPUT_PATH = os.path.join(CWD, OUTPUT_FOLDER)
if not os.path.isdir(OUTPUT_PATH): os.mkdir(OUTPUT_PATH)

### FUNCTIONs -----------------------------------------------------------------------

def GNU_notice(idx=0):
    if idx == 0:
        print '''
This program comes with ABSOLUTELY NO WARRANTY; for details run this program with the option `-w'.
This is free software, and you are welcome to redistribute it under certain conditions; run this program with the option `-c' for details.
'''
    elif idx == 1:
        print '''
THERE IS NO WARRANTY FOR THE PROGRAM, TO THE EXTENT PERMITTED BY APPLICABLE LAW. EXCEPT WHEN OTHERWISE STATED IN WRITING THE COPYRIGHT HOLDERS AND/OR OTHER PARTIES PROVIDE THE PROGRAM "AS IS" WITHOUT WARRANTY OF ANY KIND, EITHER EXPRESSED OR IMPLIED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE. THE ENTIRE RISK AS TO THE QUALITY AND PERFORMANCE OF THE PROGRAM IS WITH YOU. SHOULD THE PROGRAM PROVE DEFECTIVE, YOU ASSUME THE COST OF ALL NECESSARY SERVICING, REPAIR OR CORRECTION.
'''
    elif idx == 2:
        print '''
You can redistribute this program and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.
'''

def save_movie(command, log_file_path):
# OBSOLETE;; saving a movie file on the run
    tmp_img_dir_path = command.split(",")[1]
    command = command.split(",")[0]
    writeFile(log_file_path, '%s, ffmpeg command execution started'%get_time_stamp())
    os.system(command)
    writeFile(log_file_path, '%s, ffmpeg command execution finished'%get_time_stamp())
    rmtree(tmp_img_dir_path)

#------------------------------------------------------------------------------------

def send_email(to=[EMAIL_RECEIVER], subject='test', text='test', files=[], server="localhost", log_file_path=''):
# send an email
    msg = MIMEMultipart()
    msg['From'] = EMAIL_SENDER
    msg['To'] = COMMASPACE.join(to)
    msg['Date'] = formatdate(localtime=True)
    msg['Subject'] = subject

    msg.attach( MIMEText(text) )

    for file in files:
        part = MIMEBase('application', "octet-stream")
        part.set_payload( open(file,"rb").read() )
        Encoders.encode_base64(part)
        part.add_header('Content-Disposition', 'attachment; filename="%s"'
                   % os.path.basename(file))
        msg.attach(part)

    try:
        mailserver = smtplib.SMTP(server)
        mailserver.ehlo()
        mailserver.starttls()
        mailserver.ehlo()
        mailserver.login("ohj4", "38321234")
        mailserver.sendmail(EMAIL_SENDER, to, msg.as_string() )
        mailserver.quit()
        if len(log_file_path) > 0 : writeFile(log_file_path, '\n%s, *** Email, <%s> was sent.\n'%(get_time_stamp(), subject))
    except:
        '''
        try: mailserver.quit()
        except: pass
        '''
        if len(log_file_path) > 0 : writeFile(log_file_path, "Failed to send an email.")
        pass
    msg = None
    mailserver = None

#------------------------------------------------------------------------------------

def msgB_run(msgB_conn):
# 'msgB' is for sending/recieving messages from/to Arduino-chip and Video module
# specifically for 'scheduled_feeding' part of AAS.
# * Message from Arduino chip can be lost or incomplete.
# * Messaging with VM is only for organization purpose.

    flag_chk_ARD_msg = False # checking message from Arduino-chip ?
    flag_chk_vm_msg = False # checking message from the video module ?
    vm_msg_chk_start = None # time when the VM message check started
    msg_from_Arduino = ""
    msg_from_vm = ""
    while True:
        if chk_session_time(SESSION_START_HOUR, SESSION_END_HOUR) == False:
            if msgB_conn.poll(): # check whether there's any message arrive through the pipe
                msg = msgB_conn.recv() # receive the message
                if msg == 'q': break
            sleep(1)
            continue

        ### Chekcing Arduino-chip message
        if flag_chk_ARD_msg == True:
            msg = ARD_M.receive('button', 0.1) # Try to receive any 'button'-msg for 0.1 second.
            if msg == None: msg_from_Arduino = ""
            else: msg_from_Arduino = str(msg).replace("[","").replace("]","").replace("'","").replace(" ","")

        ### Checking Video-module message (VM -> AAO)
        if flag_chk_vm_msg == True:
            for i in range(NUMBER_OF_CAMERAS):
                if AAO.main_vi_conn[i].poll():
                    msg_from_vm = AAO.main_vi_conn[i].recv() # receive the message

        if flag_chk_ARD_msg == True and msg_from_Arduino != "":
            msgB_conn.send("ARDUINO:" + msg_from_Arduino)
            msg_from_Arduino = ""

        ### As soon as a message arrived from VM or TRIAL_LENGTH is up, finish checking.
        if flag_chk_vm_msg == True:
            if msg_from_vm != "":
                msgB_conn.send("V:" + msg_from_vm)
                flag_chk_vm_msg = False
                msg_from_vm = ""
            elif time() - vm_msg_chk_start > TRIAL_LENGTH:
                flag_chk_vm_msg = False

        ### msg checking for the msgB. (AAO or AAS -> msgB)
        if msgB_conn.poll(): # check whether there's any message arrive through the pipe
            msg = msgB_conn.recv() # receive the message

            if msg.startswith('chk_ARD_msg:'):
                msg = msg.split(":")[1]
                if msg == 'start':
                    flag_chk_ARD_msg = True

                    ### initialize message. (get rid of possible remained message)
                    msg_from_Arduino = ''
                    msg = ARD_M.receive('button', 0.1) # Try to receive any 'button'-msg for 0.1 second.
                    msg = ''
                    
                    ARD_M.send('chk_b_start') # Start checking the button-press in Arduino-chip
                elif msg == 'end':
                    flag_chk_ARD_msg = False
                    ARD_M.send('chk_b_end') # Stop checking the button-press in Arduino-chip
            elif msg.startswith('chk_vm_msg:'):
                msg = msg.split(":")[1]
                if msg == 'start':
                    ### initialize the 'msg_from_vm'
                    for i in range(NUMBER_OF_CAMERAS):
                        if AAO.main_vi_conn[i].poll():
                            msg_from_vm = AAO.main_vi_conn[i].recv() # receive the message
                    msg_from_vm = ''

                    flag_chk_vm_msg = True
                    for i in range(NUMBER_OF_CAMERAS): AAO.main_vi_conn[i].send('check_motion_at_feeder')
                    vm_msg_chk_start = time()
            elif msg == 'q': break

        sleep(0.05)

#------------------------------------------------------------------------------------

def schema_run(schema_conn, AAS, AAO):
# Running a schema which AA runs on thought a session
    writeFile(PROGRAM_LOG_PATH, "%s, ***** Staring of the program.\n\n"%get_time_stamp())
    chk_resource_usage(PROGRAM_LOG_PATH) # check the resource (cpu, memory) usage
    last_chk_resource_time = time()

    flag_session_changed_to_off = False
    flag_session_changed_to_on = False
    while True:
        if time()-last_chk_resource_time > 60 * 30: # every a half an hour
            chk_resource_usage(PROGRAM_LOG_PATH) # check the resource (cpu, memory) usage
            last_chk_resource_time = time()

        # If the session time is over, archive all the data
        # If the session time is resumed, update the log-file and csv-result-file.
        if chk_session_time(SESSION_START_HOUR, SESSION_END_HOUR) == False:
            if flag_session_changed_to_off == False: # 1st run after finishing the session-time
                if AAS.feeding_snd_play_time != -1: # if it's middle of a trial
                    AAS.terminate_trial() # terminate it.

                if flag_session_changed_to_on == True:
                # The session was on before
                # If this is True here, this means it's the very 1st time after staring the program.
                # Therefore, there will be nothing to archive.
                    print '*** The session is over.'
                    uvcInst = uvc.VideoConverter()
                    uvcInst.run()
                    #ustInst = ust.WaveFileRecognizer(OUTPUT_PATH)
                    #ustInst.run()
                    umdInst = umd.M_drawer(OUTPUT_PATH)
                    umdInst.run()
                    folder_name = get_time_stamp()[:10]
                    archive_folder_path = os.path.join('archive', folder_name)
                    umf.run(folder_name, archive_folder_path)
                    print '-------------------------------------------------------------'
                    print 'Archiving process is finished at %s.'%get_time_stamp()
                    print '-------------------------------------------------------------'

                flag_session_changed_to_off = True
                flag_session_changed_to_on = False

            if schema_conn.poll(): # check whether there's any message arrive through the pipe
                msg = schema_conn.recv() # receive the message
                if msg == 'q': break
            sleep(1)
            continue
        else:
            if flag_session_changed_to_on == False: # 1st run after starting the session-time
                print '-------------------------------------------------------------'
                print 'Session starts at %s.'%get_time_stamp()
                print '-------------------------------------------------------------'
                flag_session_changed_to_off = False
                flag_session_changed_to_on = True
                AAS.session_initialization() # Initialize the log-file and result-file

        msg = ""
        if AAO.main_msgB_conn.poll(): # any message from message board
            msg = AAO.main_msgB_conn.recv() # receive
        AAS.run(msg)

        ### msg checking for exiting the program
        if schema_conn.poll(): # check whether there's any message arrive through the pipe
            msg = schema_conn.recv() # receive the message
            if msg == 'q': break



### CLASSes -------------------------------------------------------------------------

class AA_Schema:
    def __init__(self):
        self.session_start_time = None
        self.log_file_path = ''
        self.result_file_path = ''
        self.result_header = str(RESULT_CSV_HEADER)
        self.trial_cnt = 0
        self.trial_cnt_without_timeout = 0
        self.feeding_cnt = 0
        self.arduino_msg = ""
        self.msg_from_vi_conn = ""

        ### variables for scheduled_feeding()
        self.last_feeding_time = -1 # last feeding time in minute
        self.waiting_time_for_feeding = -1 # after this amount of time(in seconds), play the feeding sound
        self.flag_feeding = False
        self.feeding_snd_play_time = -1

        ### variables for button_familiarization()
        self.button1_snd_played_time = 0
        self.button1_pressed_time = 0
        self.flag_send_msg_to_vi_conn = True

        self.chosen_random_snd = -1
        self.past_correct_snd_idx = []

        self.modulated_snd_trials = ['None', 'None', 'None', 'None', 'None', 'None', 'None', 'None', 'None', 'None']
        self.currMST = []

        self.incorrect_response_time = -1

        self.trial_correctness = 'NONE'

    #---------------------------------------------------------------------------------
    
    def session_initialization(self):
        self.session_start_time = time()
        self.log_file_path = get_log_file_path(OUTPUT_FOLDER)
        writeFile(self.log_file_path, '\n%s, ***** Session starts\n'%get_time_stamp())
        self.result_file_path = self.log_file_path.replace(".log", ".csv")
        writeFile(self.result_file_path, self.result_header + "\n-----------------------------------------\n")
        self.flag_first_feeding = True

    #---------------------------------------------------------------------------------

    def run(self, msg_from_msgB):
        if msg_from_msgB != "":
            msg = msg_from_msgB.split(":")
            if msg[0] == 'ARDUINO': self.arduino_msg = msg[1]
            elif msg[0] == 'V': self.msg_from_vi_conn = msg[1]

            if self.msg_from_vi_conn.startswith('ffmpeg'): self.save_movie_processing(self.msg_from_vi_conn)

        self.scheduled_feeding()
        #self.button_familiarization()

        self.arduino_msg = ""
        self.msg_from_vi_conn = ""

    #---------------------------------------------------------------------------------

    def save_movie_processing(self, msg_from_vi_conn):
    ### OBSOLETE
        # save the movie file
        sm_p = Process(target=save_movie, args=(msg_from_vi_conn, self.log_file_path, ))
        sm_p.start()

    #---------------------------------------------------------------------------------

    def button_familiarization(self):
    # This is for familiarizing button-press for cats
        arduino_msg = ARD_M.receive('Button1', 0.1) # Try to receive a 'Button1'-msg for 0.1 second.
        if arduino_msg == ['Button1', 'HIGH']:
            #main_ao_conn.send('play_sound:button1') # play a sound for the button1
            writeFile(self.log_file_path, '%s, Button1 was pressed'%get_time_stamp())
            self.button1_pressed_time = time()
            self.flag_send_msg_to_vi_conn = True # after certain time, it has to seek for the movement at feeder again

        if time()-self.button1_pressed_time > 120: # wait for 2 minutes after button is pressed
            if time()-self.button1_snd_played_time > 10: # 10 sec passed after last button1 snd play
                if self.flag_send_msg_to_vi_conn == True:
                    AAO.main_vi_conn[1].send('check_motion_at_feeder')
                    self.flag_send_msg_to_vi_conn = False
                if self.msg_from_vi_conn == "motion_at_feeder":
                    AAO.main_ao_conn.send('play_sound:button1')
                    self.button1_snd_played_time = time()
                    self.flag_send_msg_to_vi_conn = True

    #---------------------------------------------------------------------------------

    def scheduled_feeding(self):
        curr_time = time()

        if self.flag_first_feeding == True and curr_time - self.session_start_time > 60 * 2: # seconds * minutes
        # Feeding hasn't started yet and
        # feeding starts some seconds(typically 120 sec) after the program started
            self.flag_first_feeding = False # turn off the flag
            self.flag_feeding = True # Start feeding
            self.last_feeding_time = time()
            self.waiting_time_for_feeding = -1 # At the very beginning, feed at once.

        if self.flag_feeding:
            if curr_time - self.last_feeding_time > self.waiting_time_for_feeding:
            # it's a feeding time
                '''
                ### OBSOLETE
                ### Simply choose the button with certain probabilities.
                chosen_number = uniform(0,1)
                ### 0;SND_NAME_IDX, 1;SND_BUTTON1_IDX, 2;SND_BUTTON2_IDX, 3;SND_BUTTON3_IDX
                if chosen_number < 0.3333: self.chosen_random_snd = 1
                elif 0.3333 <= chosen_number < 0.6666: self.chosen_random_snd = 2
                else: self.chosen_random_snd = 3
                '''

                #self.flag_4th_speaker_test = False
                #chosen_number = uniform(0,1)
                #if chosen_number < 1.1:
                AAO.main_ao_conn.send('4th_speaker_test')
                self.flag_4th_speaker_test = True

                '''
                chosen_number = uniform(0,1)
                if chosen_number < 0.3:
                    if chosen_number < 0.15:
                        AAO.main_ao_conn.send('SWS_test')
                        self.flag_SWS_test = True
                    else:
                        AAO.main_ao_conn.send('NVS_test')
                        self.flag_NVS_test = True
                '''
            
                button_indices = range(SND_BUTTON1_IDX, SND_BUTTON3_IDX+1) # make the list of numbers for the buttons(1~3)

                if FLAG_BALANCE_CORRECTNESS == True:
                    # if certain button_index has 1 more correct trials than
                    # the button index which has the minimum number of correct trials,
                    # then exclude it,
                    # to balance out that the cat getting the reward from which button.
                    if len(self.past_correct_snd_idx) >= 1:
                        correct_trial_cnt = []
                        for idx in button_indices:
                            correct_trial_cnt.append(self.past_correct_snd_idx.count(idx))
                        min_correct_trial_cnt = min(correct_trial_cnt)
                        button_index_removal = []
                        for i in range(len(button_indices)):
                            if correct_trial_cnt[i] - min_correct_trial_cnt > 0: button_index_removal.append(button_indices[i])
                        for i in range(len(button_index_removal)): button_indices.remove(button_index_removal[i])
                        '''
                        if self.past_correct_snd_idx[0] == self.past_correct_snd_idx[1]:
                        # if the past 2 trials were the same button-trials
                            button_indices.remove(self.past_correct_snd_idx[0]) # get rid of that number from the list
                        '''

                '''
                ### store the button numbers for the 2 recent trials
                self.past_correct_snd_idx.append(copy(self.chosen_random_snd))
                if len(self.past_correct_snd_idx) > 2: self.past_correct_snd_idx.pop(0)
                '''
                self.chosen_random_snd = choice(button_indices)
                #self.chosen_random_snd = 2

                if self.currMST == []:
                    self.currMST = copy(self.modulated_snd_trials)
                    shuffle(self.currMST)

                self.flag_SWS_test = False
                self.flag_NVS_test = False
                if len(button_indices) > 1:
                # Only 1 sound left, meaning it should be solved by the cat.
                # Since the cat can abuse the modified sound to avoid to press certain button,
                # Modulated sound happens when there're more than one sound is in the choice-list.
                    if self.currMST[0] == 'SWS':
                        AAO.main_ao_conn.send('SWS_test')
                        self.flag_SWS_test = True
                    elif self.currMST[0] == 'NVS':
                        AAO.main_ao_conn.send('NVS_test')
                        self.flag_NVS_test = True
                    self.currMST.pop(0)

                # very 1st feeding: button3 trial
                #if self.waiting_time_for_feeding == -1: self.chosen_random_snd = 3

                if self.chosen_random_snd == SND_NAME_IDX:
                    AAO.main_ao_conn.send('play_sound:name') # Send a message to play a sound
                elif SND_NAME_IDX < self.chosen_random_snd: # button (and a foil)
                    #AAO.main_ao_conn.send('play_sound:name') # name call
                    #sleep(3) # name call: 2.5s + pause: 0.5s
                    writeFile(self.log_file_path, '%s, Sound for the trial starts.'%get_time_stamp())
                    AAO.main_ao_conn.send('play_sound:%s'%BUTTON_TEXT[self.chosen_random_snd]) # play a sound for the button#
                    ### initialization
                    self.motion_was_detected = False
                    self.result_csv = copy(self.result_header)

                    _add_info_txt = ''
                    if self.flag_4th_speaker_test == True: _add_info_txt += '4s_test'
                    if self.flag_SWS_test == True:  _add_info_txt += '/SWS'
                    if self.flag_NVS_test == True: _add_info_txt += '/NVS'
                    
                    if _add_info_txt == '': self.result_csv = self.result_csv.replace('Additional_Info', '_')
                    else: self.result_csv = self.result_csv.replace('Additional_Info', _add_info_txt)

                    self.trial_correctness = 'NONE'
                '''
                elif self.chosen_random_snd == 1:
                    writeFile(self.log_file_path, '%s, Trial for <arbitrary_name_00> starts'%get_time_stamp())
                    AO.main_ao_conn.send('play_sound:arbitrary_name_00')
                '''
                self.flag_process_after_snd_play = True # Initial process after the sound play has to be done
                self.feeding_snd_play_time = time()
                self.last_feeding_time = self.feeding_snd_play_time
                ARD_M.aConn.flushInput() # flush the serial connection
                self.arduino_msg = ""

                self.waiting_time_for_feeding = randint(TRIAL_INTERVAL[0], TRIAL_INTERVAL[1])*60 # randomly determine the next feeding-time
                
            elapsed_time_after_feeding_snd = time() - self.feeding_snd_play_time
            if self.feeding_snd_play_time != -1: # feeding sound was already played.
                if elapsed_time_after_feeding_snd > 1: # wait for 1 second (wait for a bit for sound-playing)

                    if elapsed_time_after_feeding_snd < TRIAL_LENGTH + 1: # it hasn't been TRIAL_LENGTH yet after play
                        
                        # Initial behavior after feeding sound play
                        # ; Send a message to check for the movements around the feeder
                        if self.flag_process_after_snd_play:
                            AAO.main_msgB_conn.send('chk_vm_msg:start')
                            if SND_BUTTON1_IDX <= self.chosen_random_snd <= SND_BUTTON3_IDX: # any button-trial
                                AAO.main_msgB_conn.send('chk_ARD_msg:start')                             
                                sleep(0.2)
                            self.flag_process_after_snd_play = False

                        if FLAG_RTOI == True: # Trial is repeated on the wrong response
                            if self.trial_correctness == 'INCORRECT': # there was already an incorrect-response
                                if time() - self.incorrect_response_time < FROZEN_TIME_ON_INCORRECT:
                                # FRONZEN_TIME meaning punishment-time is not over yet
                                    ### Keep playing the neg_feedback1 for some time
                                    if time() - self.incorrect_response_time < 1:
                                        AAO.main_ao_conn.send('play_sound:neg_feedback1')
                                        sleep(0.6) # length of neg_feedback1 is 0.56 sec.
                                    return # exit the function
                                else:
                                    if TRIAL_LENGTH - elapsed_time_after_feeding_snd > FROZEN_TIME_ON_INCORRECT-1:
                                    # if the left time is long enough (here longer than the punishment time)
                                        # play a sound for the button#; (beginning of the same trial again)
                                        AAO.main_ao_conn.send('play_sound:%s'%BUTTON_TEXT[self.chosen_random_snd])
                                        self.trial_correctness = 'NONE'
                                        ARD_M.aConn.flushInput() # flush the serial connection
                                        self.arduino_msg = ""
                                    else:
                                        self.terminate_trial(flag_timeout_record=True)

                        if self.msg_from_vi_conn == "motion_at_feeder": # there was a motion around the feeder

                            if self.chosen_random_snd == SND_NAME_IDX: # name sound was played
                                self.feeding_cnt += 1
                                self.activate_feeder()
                                writeFile(self.log_file_path, '%s, Trial for <name> finished'%get_time_stamp())                          
                                self.feeding_snd_play_time = -1

                            elif self.chosen_random_snd == SND_FOIL_IDX:
                                AAO.main_ao_conn.send('play_sound:neg_feedback1')
                                AAO.main_ao_conn.send('play_sound:neg_feedback2')
                                self.incorrect_response_time = time()
                                self.record_incorrect_button_press(['MOTIOIN'])
                                self.trial_correctness = 'INCORRECT'
                                writeFile(self.log_file_path, '%s, Incorrect response(motion detection) on the foil stimulus.'%(get_time_stamp()))
                                if FLAG_RTOI == False: # RTOI: Repeat Trial On Incorrect-response
                                    self.terminate_trial()
                                else: # Trial will be repeated
                                    ARD_M.send('led_on') # turn the red LED light on (will be automatically off after certain time by Arduino chip itself)

                            elif 0 < self.chosen_random_snd < 4: # button-press trial
                                writeFile(self.log_file_path, '%s, Motion detected at feeder after <%s> sound-play'%(get_time_stamp(), BUTTON_TEXT[self.chosen_random_snd]))
                                if self.motion_was_detected == False:
                                # After playing a stimulus, the motion was detected for the 1st time
                                    if self.flag_4th_speaker_test == True: AAO.main_ao_conn.send('4th_speaker_test')
                                    if self.flag_SWS_test == True: AAO.main_ao_conn.send('SWS_test')
                                    if self.flag_NVS_test == True: AAO.main_ao_conn.send('NVS_test')
                                    AAO.main_ao_conn.send('play_sound:%s'%BUTTON_TEXT[self.chosen_random_snd]) # play a sound for the button#
                                    self.record_trial_start()
                                    self.motion_was_detected = True
                            '''
                            elif self.chosen_random_snd == 1: # arbitrary_name_00 sound was played
                                writeFile(self.log_file_path, '%s, Motion detected around the feeder after playing <arbitrary_name_00> sound'%get_time_stamp())
                                AAO.main_ao_conn.send('play_sound:neg_feedback')
                                writeFile(self.log_file_path, '%s, Trial for <arbitrary_name_00> finished'%get_time_stamp())
                                self.feeding_snd_play_time = -1
                            '''                            

                        if self.chosen_random_snd >= SND_BUTTON1_IDX: # button-press trial
                            if self.arduino_msg != "": # there is some message from Arduino
                                arduino_msg = self.arduino_msg.split(",")
                                if arduino_msg == [BUTTON_TEXT[self.chosen_random_snd], 'HIGH']:
                                # correct button was pressed                               
                                    #AAO.main_ao_conn.send('play_sound:%s'%BUTTON_TEXT[self.chosen_random_snd]) # play a sound for the button#
                                    writeFile(self.log_file_path, '%s, %s was pressed.'%(get_time_stamp(), arduino_msg[0]))
                                    sleep(0.3)
                                    self.feeding_cnt += 1
                                    self.activate_feeder()
                                    self.record_correct_button_press()
                                    self.trial_correctness = 'CORRECT'
                                    self.past_correct_snd_idx.append(copy(self.chosen_random_snd)) # store this button index
                                    self.terminate_trial()
                                else:
                                # wrong button was pressed
                                    if self.trial_correctness == 'NONE':
                                        if self.flag_SWS_test == False and self.flag_NVS_test == False: AAO.main_ao_conn.send('play_sound:neg_feedback1')
                                        else: self.activate_feeder() # in SWS or NVS trial, CATOS's response is always positive
                                        self.incorrect_response_time = time()
                                        self.record_incorrect_button_press(arduino_msg)
                                        self.trial_correctness = 'INCORRECT'
                                    writeFile(self.log_file_path, '%s, %s was pressed. Incorrect press.'%(get_time_stamp(), arduino_msg[0]))
                                    if FLAG_RTOI == False: # RTOI: Repeat Trial On Incorrect-response
                                        if self.flag_SWS_test == False and self.flag_NVS_test == False: AAO.main_ao_conn.send('play_sound:neg_feedback2')
                                        self.terminate_trial()
                                    else: # Trial will be repeated
                                        ARD_M.send('led_on') # turn the red LED light on (will be automatically off after certain time by Arduino chip itself)

                    else: # TRIAL_LENGTH passed
                        self.terminate_trial(flag_timeout_record=True)

    #---------------------------------------------------------------------------------

    def record_trial_start(self):
        self.result_csv = self.result_csv.replace("Trial#", "%.3i"%self.trial_cnt)
        self.result_csv = self.result_csv.replace("Trial_start_time", get_time_stamp())
        self.result_csv = self.result_csv.replace("Correct_response", "%s-press"%BUTTON_TEXT[self.chosen_random_snd])
        
    #---------------------------------------------------------------------------------

    def record_correct_button_press(self):
        if self.motion_was_detected == False: self.record_trial_start()
        self.result_csv = self.result_csv.replace("Response_time", get_time_stamp())
        self.result_csv = self.result_csv.replace("Response", "%s-press"%BUTTON_TEXT[self.chosen_random_snd])
        self.result_csv = self.result_csv.replace("Correctness", 'CORRECT')
        writeFile(self.result_file_path, self.result_csv)

    #---------------------------------------------------------------------------------

    def record_incorrect_button_press(self, arduino_msg):
        tmp_result_csv = copy(self.result_csv)
        # Because even if it's a incorrect response, 
        # the cat still can press the correct button again. (Depending on the training phase)
        # it uses a copy of the self.result_csv to write the incorrect response in the result file.
        tmp_result_csv = tmp_result_csv.replace("Trial#", "%.3i"%self.trial_cnt)
        tmp_result_csv = tmp_result_csv.replace("Trial_start_time", get_time_stamp())
        if self.chosen_random_snd == SND_FOIL_IDX: tmp_result_csv = tmp_result_csv.replace("Correct_response", "No-motion")
        else: tmp_result_csv = tmp_result_csv.replace("Correct_response", "%s-press"%BUTTON_TEXT[self.chosen_random_snd])
        tmp_result_csv = tmp_result_csv.replace("Response_time", get_time_stamp())
        if self.chosen_random_snd == SND_FOIL_IDX: tmp_result_csv = tmp_result_csv.replace("Response", "MOTION")
        else: tmp_result_csv = tmp_result_csv.replace("Response", "%s-press"%arduino_msg[0])
        tmp_result_csv = tmp_result_csv.replace("Correctness", 'INCORRECT')
        writeFile(self.result_file_path, tmp_result_csv)

    #---------------------------------------------------------------------------------

    def terminate_trial(self, flag_timeout_record = False):
        if self.chosen_random_snd >= SND_BUTTON1_IDX: # button-press trial
            AAO.main_msgB_conn.send('chk_ARD_msg:end')
            sleep(0.5)
            if self.trial_correctness != 'NONE': # there was either 'correct' or 'incorrect' response
                self.trial_cnt += 1
                self.trial_cnt_without_timeout += 1
                self.chk_end_feeding()
            elif self.trial_correctness == 'NONE' and self.motion_was_detected == True: # timeout trial
                self.trial_cnt += 1
                self.trial_correctness = 'TIMEOUT'
                AAO.main_ao_conn.send('play_sound:neg_feedback2') # type 2 negative feedback sound is used to notify the trial is finished with incorrect response
                if flag_timeout_record == True:
                    self.result_csv = self.result_csv.replace("Response_time", get_time_stamp())
                    self.result_csv = self.result_csv.replace("Response", "TIMEOUT")
                    self.result_csv = self.result_csv.replace("Correctness", 'TIMEOUT')
                    writeFile(self.result_file_path, self.result_csv)
                    writeFile(self.log_file_path, '%s, %i seconds has passed since the trial started.'%(get_time_stamp(), TRIAL_LENGTH))
            else:
                self.trial_correctness = 'NO_MOTION'
        writeFile(self.log_file_path, '%s, End of trial.'%(get_time_stamp()))
        self.feeding_snd_play_time = -1 # end of trial

    #---------------------------------------------------------------------------------

    def activate_feeder(self):
        ARD_M.send('FEED') # Activate the feeder
        writeFile(self.log_file_path, '%s, Feeder activated'%get_time_stamp())
        sleep(0.5)

        '''
        ARD_M.send('Query:distance') # investigate the distance to the food level
        sleep(0.2)
        distance_to_food = ARD_M.receive('dist_to_food', None) # get the distance-to-food measurements. No timeout-time.
        ### Convert it(supposed to be 10 measurements) into a list of integers.
        del_list = []
        for i in range(len(distance_to_food)):
            try: distance_to_food[i] = int(distance_to_food[i])
            except: del_list.append(i)
        for i in range(len(del_list)): distance_to_food.pop(del_list[i]-i)
        writeFile(self.log_file_path, '%s, Distance measurements to food, %s'%(get_time_stamp(), str(distance_to_food)))
        distance_to_food = int(median(distance_to_food))
        # Record the median value of measurements
        writeFile(self.log_file_path, '%s, Distance to food, %i cm'%(get_time_stamp(), distance_to_food))
        if distance_to_food > 30 or self.feeding_cnt >= MAX_FEEDING_CNT:
        # The food level is greater than the threshold (in centi-meter)
        # or the maximum feeding count is reached
        '''
        self.chk_end_feeding()

    #---------------------------------------------------------------------------------

    def chk_end_feeding(self):
        if self.feeding_cnt >= MAX_FEEDING_CNT or self.trial_cnt_without_timeout >= MAX_TRIAL_CNT:
            self.flag_feeding = False # stop feeding process.
            #sleep(1.5)
            #ARD_M.send('OPEN_FEEDER') # Leave the feeder open
            #sleep(0.2)
            writeFile(self.log_file_path, '%s, Feeding is finished'%get_time_stamp())
    
#-------------------------------------------------------------------------------------


class AA_Organizer(Process):
# Main class for organizing modules.
    def __init__(self):
        global LOG_FILE_PATH
        Process.__init__(self)
        LOG_FILE_PATH = get_log_file_path(OUTPUT_FOLDER)

    #---------------------------------------------------------------------------------

    def run(self):
        forking_enable(0)
        ### set up bidirectional Pipes between this object and other modules
        self.main_vi_conn = [None] * NUMBER_OF_CAMERAS
        self.vi_conn = [None] * NUMBER_OF_CAMERAS
        for i in range(NUMBER_OF_CAMERAS):
            self.main_vi_conn[i], self.vi_conn[i] = Pipe(True)

        self.main_ai_conn, self.ai_conn = Pipe(True)
        self.main_ao_conn, self.ao_conn = Pipe(True)
        self.main_schema_conn, self.schema_conn = Pipe(True)
        self.main_msgB_conn, self.msgB_conn = Pipe(True)

        self.vi_p = []
        for i in range(NUMBER_OF_CAMERAS):
            self.vi_p.append(Process(target=videoIn_run, args=(self.vi_conn[i], LOG_FILE_PATH, OUTPUT_FOLDER, i, FLAG_FFMPEG_ON_THE_RUN, SESSION_START_HOUR, SESSION_END_HOUR,)))
            self.vi_p[i].start() # video-module process starts
            sleep(3)

        self.ai_p = Process(target=audioIn_run, args=(self.ai_conn, LOG_FILE_PATH, OUTPUT_FOLDER, SESSION_START_HOUR, SESSION_END_HOUR,))
        self.ai_p.start() # audio-module process starts

        self.ao_p = Process(target=audioOut_run, args=(self.ao_conn, LOG_FILE_PATH, OUTPUT_FOLDER, SOUND_FILES, SESSION_START_HOUR, SESSION_END_HOUR,))
        self.ao_p.start() # audio-module process starts

        self.schema_p = Process(target=schema_run, args=(self.schema_conn, AAS, AAO,))
        self.schema_p.start() # message polling from the video-module starts

        self.msgB_p = Process(target=msgB_run, args=(self.msgB_conn,))
        self.msgB_p.start() # message polling from the video-module starts

        #try:
        while True:
            command = raw_input('Press < q > and < Enter > to terminate the program.\n') # collect the user-input
            if command == 'q':
                ### send a message to each module to stop
                self.main_ai_conn.send('q')
                self.main_ao_conn.send('q')
                for i in range(NUMBER_OF_CAMERAS): self.main_vi_conn[i].send('q')
                self.main_schema_conn.send('q')
                self.main_msgB_conn.send('q')
                self.ai_p.join()
                self.ao_p.join()
                for i in range(NUMBER_OF_CAMERAS): self.vi_p[i].join()
                self.schema_p.join()
                self.msgB_p.join()
                break

            sleep(0.5)

        msg = '***** Program Exits.'
        self.onExit(False, msg)
        '''
        except KeyboardInterrupt:
            msg = '\n***** Keyboard Interruption. Terminating the program.'
            self.onExit(True, msg)
        except:
            msg = '\n***** An exception occured. Refer the log files. Terminating the program.'
            self.onExit(True, msg)
        '''

    #---------------------------------------------------------------------------------

    def onExit(self, termination = False, msg = None):
        if msg is not None:
            print msg
            writeFile(PROGRAM_LOG_PATH, '\n\n%s, %s'%(get_time_stamp(), msg))
        self.main_ai_conn.close()
        for i in range(NUMBER_OF_CAMERAS): self.main_vi_conn[i].close()
        self.main_schema_conn.close()
        self.main_msgB_conn.close()
        self.ai_conn.close()
        self.ao_conn.close()
        for i in range(NUMBER_OF_CAMERAS): self.vi_conn[i].close()
        self.schema_conn.close()
        self.msgB_conn.close()
        if termination:
            self.ai_p.terminate()
            self.ao_p.terminate()
            for i in range(NUMBER_OF_CAMERAS): self.vi_p[i].terminate()
            self.schema_p.terminate()
            self.msgB_p.terminate()

        ### checking log files and generating movie files
        ui = raw_input("The next process will go through all the log files in the output folder and try to generate movie files(mp4) deleting the temporary image folders.\nProceed? (Y/N)")
        if ui.strip().upper() == 'Y':
            uvcInst = uvc.VideoConverter()
            uvcInst.run()

            ### taging wave sound files
            print "-----------------------\n"
            ui = raw_input("The next process will go through all the wave-sound-files in the output folder and try to tag with proper category names.\nProceed? (Y/N)")
            if ui.strip().upper() == 'Y':
                ustInst = ust.WaveFileRecognizer(OUTPUT_PATH)
                ustInst.run()

            ### checking MR(Movements Record) files and generating PNG files to show it graphically
            print "-----------------------\n"
            ui = raw_input("The next process will go through all the MR(Movements Record) files in the output folder and try to generate PNG picture files drawing the movements.\nProceed? (Y/N)")
            if ui.strip().upper() == 'Y':
                umdInst = umd.M_drawer(OUTPUT_PATH)
                umdInst.run()

                ### Make folder for each type of files and move
                print "-----------------------\n"
                ui = raw_input("Make folder for each type of result files and movie files accordingly.\nProceed? (Y/N)")
                if ui.strip().upper() == 'Y':
                    umf.run()

#------------------------------------------------------------------------------------

if __name__ == '__main__':
    if len(sys.argv) > 1:
        if sys.argv[1] == '-w': GNU_notice(1)
        elif sys.argv[1] == '-c': GNU_notice(2)
    else:
        GNU_notice(0)
        ARD_M = Arduino_module(OUTPUT_FOLDER) # Connect the Arduino chip
        AAS = AA_Schema()
        AAO = AA_Organizer()
        AAO.run()


