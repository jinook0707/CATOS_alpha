'''
aa_dataviewer
This is used for browsing video & audio data collected by CATOS_AA.
It also shows some graph of recent performance of the subject.
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
import wx, wx.media, cv
from wx.lib.agw import multidirdialog
from glob import glob
from copy import copy
from datetime import datetime, timedelta

import numpy as np

import matplotlib as mpl
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg

debug = False

#################################################################
# Class for this initial blank page
#################################################################
class _blankPage(wx.Panel):
    def __init__(self, parent):
        if debug: print "_blankPage.__init__"
        wx.Panel.__init__(self, parent)
        wx.StaticText(self, -1, label = "" , pos = (5, 40))

#################################################################
# Class for general browsing of recorded data
#################################################################
class DataBrowser(wx.Panel):
    def __init__(self, parent):
        if debug: print 'DataBrowser.__init__'

        self.window_width = AADV.window_width
        self.window_height = AADV.window_height

        wx.Panel.__init__(self, parent, size=(self.window_width, self.window_height))

        self.window_posX = AADV.window_posX
        self.window_posY = AADV.window_posY
        self.SetBackgroundColour('grey')

        ### Connecting key-inputs with some functions
        find_BtnID = 101
        enter_BtnID = 102
        new_data_folder_BtnID = 103
        self.Bind(wx.EVT_MENU, self.onFindStr, id = find_BtnID)
        self.Bind(wx.EVT_MENU, self.onEnter, id = enter_BtnID)
        self.Bind(wx.EVT_MENU, self.onNewDataFolder, id = new_data_folder_BtnID)
        accel_tbl = wx.AcceleratorTable([ (wx.ACCEL_SHIFT,  ord('F'), find_BtnID ),
                                            (wx.ACCEL_NORMAL,  wx.WXK_RETURN, enter_BtnID ),
                                            (wx.ACCEL_SHIFT,  ord('O'), new_data_folder_BtnID ) ])
        self.SetAcceleratorTable(accel_tbl)

        wx.StaticText(self, -1, label = "Press SHIFT-O to open the folder for browsing data." , pos = (5, 40))

    #------------------------------------------------------------

    def load_data(self):
        if debug: print 'DataBrowser.load_data'

        ### Choosing the data-folder
        dlg = wx.DirDialog(self, "Choose a data folder containing 'csv', 'jpg', 'mp4', 'wav' folders.", os.getcwd(), wx.OPEN)
        dlgResult = dlg.ShowModal()
        if dlgResult == wx.ID_OK:
            self.folder_path = dlg.GetPath()
            dlg.Destroy()
        else:
            dlg.Destroy()
            return

        ### Checking the folder has all the required data sub-folders.
        flag_invalid_folder = False
        if not os.path.isdir(os.path.join(self.folder_path, "csv")): flag_invalid_folder = True
        if not os.path.isdir(os.path.join(self.folder_path, "jpg")): flag_invalid_folder = True
        if not os.path.isdir(os.path.join(self.folder_path, "mp4")): flag_invalid_folder = True
        if not os.path.isdir(os.path.join(self.folder_path, "wav")): flag_invalid_folder = True
        if flag_invalid_folder == True:
            print "ERROR: Chosen directory doesn't have one or more of the following folders, 'csv', 'jpg', 'mp4', 'wav'."
            self.Destroy()
            return

        dir_list = []
        log_file_path = []
        for item in glob(os.path.join(self.folder_path, '*')):
            if os.path.isdir(item): dir_list.append(item)
            elif os.path.isfile(item):
                fn = os.path.split(item)[1]
                fn = fn.split('.')
                extension = fn[len(fn)-1]
                if extension == 'log': log_file_path = item

        ### load the result-csv file
        self.result_csv_file_path = log_file_path.replace(".log", ".csv")
        if os.path.isfile(self.result_csv_file_path):
            f = open(self.result_csv_file_path, 'r')
            ### put brackets (' [[ ' & ' ]] ') around the 'hh_mm_ss' part of timestamps in the text.
            lines = f.readlines()
            for i in range(len(lines)):
                items = lines[i].split(",") # separate items with the comma
                flag_timestamp_editted = False
                for j in range(len(items)):
                    item = items[j].strip()
                    if len(item) == 26 and item.startswith('20'): # if it's a time-stamp
                        items[j] = item[:11] + ' [[ ' + item[11:19] + ' ]] ' + item[19:] # put brackets
                        flag_timestamp_editted = True
                if flag_timestamp_editted:
                    lines[i] = str(items)[1:-1].replace("'","").replace("\"","").replace("\\n", "\n\n") # replace the changed line with the line with brackets
            self.result_csv = ''
            self.result_csv = self.result_csv.join(lines)
            f.close()
            self.result_csv_text = wx.TextCtrl(self, -1, value=self.result_csv, pos=(0,5), size = (self.window_width/2-10, 155), style=wx.TE_MULTILINE)
        self.save_result_btn = wx.Button(self, -1, "Save", pos = (0, 160), size=(100,20))
        self.save_result_btn.Bind(wx.EVT_LEFT_UP, self.onSaveResultCSV)

        ### load the log file contents
        f = open(log_file_path, 'r')
        ### put brackets (' [[ ' & ' ]] ') around the 'hh_mm_ss' part of timestamps in the log.
        lines = f.readlines()
        for i in range(len(lines)):
            items = lines[i].split(",") # separate items with the comma
            flag_timestamp_editted = False
            for j in range(len(items)):
                item = items[j].strip()
                if len(item) == 26 and item.startswith('20'): # if it's a time-stamp
                    items[j] = item[:11] + ' [[ ' + item[11:19] + ' ]] ' + item[19:] # put brackets
                    flag_timestamp_editted = True
            if flag_timestamp_editted:
                lines[i] = str(items)[1:-1].replace("'","").replace("\"","").replace("\\n", "\n") # replace the changed line with the line with brackets
        self.log = ''
        self.log = self.log.join(lines)
        f.close()
        self.log_text = wx.TextCtrl(self, -1, value=self.log, pos=(self.window_width/2+5,5), size = (self.window_width/2, 135), style=wx.TE_MULTILINE|wx.TE_READONLY|wx.TE_RICH2)
        self.log = self.log.lower()

        ### Search
        search_btn_start_pos = self.window_width-300
        self.prev_result = wx.Button(self, -1, "<", pos = (search_btn_start_pos, 140), size=(25,10))
        self.prev_result.Bind(wx.EVT_LEFT_UP, self.prev_result_click)
        self.next_result = wx.Button(self, -1, ">", pos = (search_btn_start_pos+30, 140), size=(25,10))
        self.next_result.Bind(wx.EVT_LEFT_UP, self.next_result_click)
        wx.StaticText(self, -1, label = "Search:", pos = (search_btn_start_pos+70, 140))
        self.search_txt = wx.TextCtrl(self, id=2, value = "", pos = (search_btn_start_pos+120, 140), size=(100,20))
        self.search_word = ""
        self.search_result = []
        self.search_result_label = wx.StaticText(self, -1, label = ".", pos = (search_btn_start_pos+220, 145), size=(100,20))

        self.time_stamp = []
        self.csv_files = []
        self.mp4_files = []
        self.wav_files = []
        self.jpg_files = []
        self.CSV_POS = (5, 430)
        self.MP4_POS = (360, 180)
        self.JPG_POS = (360, 190)
        self.WAV_POS = (5,550)

        for item in dir_list:
            item = os.path.split(item)[1]
            if item.lower() == 'csv': self.load_csv_files()
            elif item.lower() == 'mp4': self.load_mp4_files()
            elif item.lower() == 'wav': self.load_wav_files()
            elif item.lower() == 'jpg': self.load_jpg_files()

        ### Time-Stamp list-box
        self.ts_box = wx.ListBox(self, 0, (5,200), (350,220), self.time_stamp, wx.LB_SINGLE|wx.LB_SORT)
        self.ts_box.Bind(wx.EVT_LISTBOX, self.file_selected)
        self.ts_box.Bind(wx.EVT_LISTBOX_DCLICK, self.file_selected)

        ### CSV (MovementRecord CSV file, not the result CSV file)
        self.csv_text = wx.TextCtrl(self, -1, value='', pos=self.CSV_POS, size=(353,110), style=wx.TE_MULTILINE|wx.TE_READONLY)
        self.loaded_img = None

        ### TimeStamp label on top of the JPEG image
        self.ts_label = wx.StaticText(self, id=-1, pos = (self.JPG_POS[0], self.JPG_POS[1]-30), label = '')
        self.ts_label.SetFont(wx.Font(25, wx.DEFAULT, wx.NORMAL, wx.NORMAL, False))

        self.status_label = wx.StaticText(self, id=-1, pos = (5, 655), label = '')
        self.snd_play_status_future_call = None

    #------------------------------------------------------------

    def load_csv_files(self):
        if debug: print 'DataBrowser.load_csv_files'

        csv_dir = os.path.join(self.folder_path, 'csv')
        for f in glob(os.path.join(csv_dir, '*.csv')):
            fn = os.path.split(f)[1]
            self.csv_files.append(fn)
            ts = fn.replace("_MR.csv", "")
            ts = ts[:11] + ' [[ ' + ts[11:19] + ' ]] ' + ts[19:]
            self.time_stamp.append(ts)

    #------------------------------------------------------------

    def load_mp4_files(self):
        if debug: print 'DataBrowser.load_mp4_files'

        mp4_dir = os.path.join(self.folder_path, 'mp4')
        for f in glob(os.path.join(mp4_dir, '*.mp4')): self.mp4_files.append(os.path.split(f)[1])

    #------------------------------------------------------------

    def load_jpg_files(self):
        if debug: print 'DataBrowser.load_jpg_files'

        jpg_dir = os.path.join(self.folder_path, 'jpg')
        for f in glob(os.path.join(jpg_dir, '*.jpg')): self.jpg_files.append(os.path.split(f)[1])

    #------------------------------------------------------------

    def load_wav_files(self):
        if debug: print 'DataBrowser.load_wav_files'

        wav_dir = os.path.join(self.folder_path, 'wav')
        for f in glob(os.path.join(wav_dir, '*.wav')):
            ts = os.path.split(f)[1]
            ts = ts[:11] + ' [[ ' + ts[11:19] + ' ]] ' + ts[19:]
            self.wav_files.append(ts)
        self.wav_box = wx.ListBox(self, 1, self.WAV_POS, (350,100), self.wav_files, wx.LB_SINGLE|wx.LB_SORT)
        self.wav_box.Bind(wx.EVT_LISTBOX, self.file_selected)
        self.wav_box.Bind(wx.EVT_LISTBOX_DCLICK, self.file_selected)

    #------------------------------------------------------------

    def file_selected(self, event):
        if debug: print 'DataBrowser.file_selected'

        list_id = event.GetId()
        list_box = wx.FindWindowById(list_id)
        file_name = list_box.GetStrings()[list_box.GetSelections()[0]]
        file_name = file_name.replace(" [[ ", "").replace(" ]] ", "")
        if list_id == 0: # video-recording time stamps
            ### load csv file
            file_path = os.path.join(self.folder_path, "csv", file_name+"_MR.csv")
            f = open(file_path, 'r')
            value = f.read()
            f.close()
            self.csv_text.SetValue(value)

            ### load jpg file
            if self.loaded_img != None: self.loaded_img.Destroy()
            jpg_file_path = os.path.join(self.folder_path, "jpg", file_name+"_MR.jpg")
            if os.path.isfile(jpg_file_path): # if the file exist
                img = wx.Image(jpg_file_path, wx.BITMAP_TYPE_ANY)
                bmp = img.ConvertToBitmap()
                self.loaded_img = wx.StaticBitmap(self, -1, bmp, self.JPG_POS)
                ### display time-stamp in bigger text
                ts_items = file_name.split("_")
                ts = "%s/%s/%s  %s:%s:%s"%(ts_items[0], ts_items[1], ts_items[2], ts_items[3], ts_items[4], ts_items[5])
                self.ts_label.SetLabel(ts)
            else:
                self.loaded_img = None

            if event.GetEventType() == wx.EVT_LISTBOX_DCLICK.typeId:
            # If the click was double-click, play the movie
                ### load mp4 file
                file_path = os.path.join(self.folder_path, "mp4", file_name+".mp4")
                video_file = cv.CaptureFromFile(file_path)
                nFrames = int(cv.GetCaptureProperty(video_file, cv.CV_CAP_PROP_FRAME_COUNT))
                fps = cv.GetCaptureProperty(video_file, cv.CV_CAP_PROP_FPS)
                waitPerFrameInMillisec = int(1.0 / fps * 1000.0 / 1.0)
                cv.NamedWindow("AA_MP4_VIEW", cv.CV_WINDOW_NORMAL)
                cv.MoveWindow("AA_MP4_VIEW", self.window_posX + self.MP4_POS[0], self.window_posY + self.MP4_POS[1])
                for i in xrange(nFrames):
                    frame = cv.QueryFrame(video_file)
                    if frame != None:
                        cv.ShowImage("AA_MP4_VIEW", frame)
                        #cv.WaitKey(waitPerFrameInMillisec)
                        ### Listen for ESC key
                        c = cv.WaitKey(waitPerFrameInMillisec) % 0x100
                        if c == 27: break
                cv.DestroyWindow("AA_MP4_VIEW")

        elif list_id == 1: # audio-recording time stamps
            if self.snd_play_status_future_call != None: self.snd_play_status_future_call.Stop()

            file_path = os.path.join(self.folder_path, "wav", file_name)
            wav = wave.open(file_path, "r")
            numFrames = wav.getnframes()
            sRate = float(wav.getframerate())
            soundlength = round(1000*numFrames/sRate) # length in msecs
            sound = wx.Sound(file_path)
            sound.Play(wx.SOUND_ASYNC)
            self.status_label.SetLabel("wav-file playing..")
            self.snd_play_status_future_call = wx.FutureCall(soundlength, self.setStatusText, "")
            wx.FutureCall(soundlength, self.init_snd_play_status_future_call)

    #------------------------------------------------------------

    def onFindStr(self, event):
        if debug: print 'DataBrowser.onFindStr'

        focused_widget = self.FindFocus().GetId()
        if focused_widget != 2: # search-text doesn't have the focus
            self.search_txt.SetFocus() # give the focus on it

    #------------------------------------------------------------

    def prev_result_click(self, event):
        if debug: print 'DataBrowser.prev_result_click'

        if len(self.search_result) > 0:
            self.log_text.SetStyle(self.search_result[self.search_result_idx],self.search_result[self.search_result_idx]+self.s_len, wx.TextAttr("BLUE", "GREY")) # change the previous one to the original color
            self.search_result_idx -= 1
            if self.search_result_idx == -1: self.search_result_idx = len(self.search_result)-1
            idx = self.search_result[self.search_result_idx]
            self.log_text.SetInsertionPoint(idx) # move to the next position
            self.log_text.SetStyle(idx,idx+self.s_len, wx.TextAttr("YELLOW", "GREY")) # change the color
            self.search_result_label.SetLabel("%i/%i"%(self.search_result_idx+1, len(self.search_result)))

    #------------------------------------------------------------

    def next_result_click(self, event):
        if debug: print 'DataBrowser.next_result_click'

        if len(self.search_result) > 0:
            self.log_text.SetStyle(self.search_result[self.search_result_idx],self.search_result[self.search_result_idx]+self.s_len, wx.TextAttr("BLUE", "GREY")) # change the previous one to the original color
            self.search_result_idx += 1
            if self.search_result_idx == len(self.search_result): self.search_result_idx = 0 # if it reached the end, return to the first one
            idx = self.search_result[self.search_result_idx]
            self.log_text.SetInsertionPoint(idx) # move to the next position
            self.log_text.SetStyle(idx,idx+self.s_len, wx.TextAttr("YELLOW", "GREY")) # change the color
            self.search_result_label.SetLabel("%i/%i"%(self.search_result_idx+1, len(self.search_result)))

    #------------------------------------------------------------

    def onEnter(self, event):
        if debug: print 'DataBrowser.onEnter'

        focused_widget = self.FindFocus().GetId()
        if focused_widget == 2: # search-text has the focus
            if self.search_txt.GetValue() == self.search_word: # search word has not changed
                self.next_result_click(None)
            else:
                self.log_text.SetStyle(0,len(self.log), wx.TextAttr("BLACK", "WHITE"))
                self.search_word = self.search_txt.GetValue().lower()
                self.s_len = len(self.search_word)
                self.search_result = AADV.search_string(self.search_word, self.log, self.log_text)
                self.search_result_idx = 0
                if len(self.search_result) > 0:
                    self.search_result_label.SetLabel("%i/%i"%(self.search_result_idx+1, len(self.search_result)))
                else:
                    self.search_result_label.SetLabel("No matches")

    #------------------------------------------------------------

    def onSaveResultCSV(self, event):
        if debug: print 'DataBrowser.onSaveResultCSV'
        resultCSV = self.result_csv_text.GetValue()
        resultCSV = resultCSV.replace("\n\n","\n").replace(" [[ ","").replace(" ]] ","").replace(",  ",", ")
        f = open(self.result_csv_file_path, 'w')
        f.write(resultCSV)
        f.close()
        dlg = PopupDialog(inString = "The result CSV file is saved.", size=(300,150))
        dlg.ShowModal()
        dlg.Destroy()

    #------------------------------------------------------------

    def setStatusText(self, txt):
        if debug: print 'DataBrowser.setStatusText'
        self.status_label.SetLabel(txt)

    #------------------------------------------------------------

    def init_snd_play_status_future_call(self):
        if debug: print 'DataBrowser.init_snd_play_status_future_call'

        self.snd_play_status_future_call = None

    #------------------------------------------------------------

    def onNewDataFolder(self, event):
        if debug: print 'DataBrowser.onNewDataFolder'

        for child in self.GetChildren(): child.Destroy()
        wx.StaticText(self, -1, label = "Press SHIFT-O to open the folder for browsing data." , pos = (5, 40))
        self.load_data()

#################################################################
# Class for showing graphs with the result csv files
#################################################################
class ResultGraph(wx.Panel):
    def __init__(self, parent):
        if debug: print 'ResultGraph.__init__'

        self.window_width = AADV.window_width
        self.window_height = AADV.window_height

        wx.Panel.__init__(self, parent, size=(self.window_width, self.window_height))

        self.window_posX = AADV.window_posX
        self.window_posY = AADV.window_height

        ### Connecting key-inputs with some functions
        new_data_folder_BtnID = 103
        self.Bind(wx.EVT_MENU, self.onSelectSessionClick, id = new_data_folder_BtnID)
        accel_tbl = wx.AcceleratorTable([ (wx.ACCEL_SHIFT,  ord('O'), new_data_folder_BtnID ) ])
        self.SetAcceleratorTable(accel_tbl)

        wx.StaticText(self, -1, label = "Press SHIFT-O to open the folder for presenting the graph." , pos = (5, 40))

        ### Control objects setup
        button_start_posY = 50; self.button_start_posY = button_start_posY
        self.select_sessions_btn = wx.Button(self, -1, "Select sessions", pos = (self.window_width-200, button_start_posY))
        self.select_sessions_btn.Bind(wx.EVT_LEFT_UP, self.onSelectSessionClick)
        _pos = self.select_sessions_btn.GetPosition()
        _staticTxt = wx.StaticText(self, -1, label = "Selected sessions" , pos = (_pos[0]+45, _pos[1]+25))
        _pos = _staticTxt.GetPosition()
        self.hundred_trials_chkbox = wx.CheckBox(self, -1 ,'1 Data point = 100 trials\n(Check-off:\n1 Data point = 1 Day)', (_pos[0]-50, _pos[1]+120), (190, 100))
        self.hundred_trials_chkbox.SetValue(False)
        _pos = self.hundred_trials_chkbox.GetPosition()
        self.chart_type_cb = wx.ComboBox(self, -1, 'Line-chart', (_pos[0],_pos[1]+90), (170,-1), ['Bar-chart', 'Line-chart'], wx.CB_READONLY)
        #self.chart_type_cb.Bind(wx.EVT_COMBOBOX, self.on)
        _pos = self.chart_type_cb.GetPosition()
        self.display_values_chkbox = wx.CheckBox(self, -1 ,'Display values', (_pos[0], _pos[1]+40))
        self.display_values_chkbox.SetValue(True)
        _pos = self.display_values_chkbox.GetPosition()
        self.correctness_btn = wx.Button(self, -1, "Draw Correctness\n(Default)", pos = (_pos[0], _pos[1]+30))
        self.correctness_btn.Bind(wx.EVT_LEFT_UP, self.onCorrectnessClick)
        _pos = self.correctness_btn.GetPosition()
        self.RT_btn = wx.Button(self, -1, "Draw Reaction Time\n(Motion-detection\nto Button-press)", pos = (_pos[0], _pos[1]+50))
        self.RT_btn.Bind(wx.EVT_LEFT_UP, self.onRTClick)

        ### show the journal
        wx.StaticText(self, -1, label = "Journal" , pos = (0, self.window_height-220))
        journal_file = open('_Journal.txt', 'r')
        self.journal = journal_file.read()
        self.journal_text = wx.TextCtrl(self, -1, value=self.journal, pos=(0,self.window_height-200), size = (self.window_width, 200), style=wx.TE_MULTILINE|wx.TE_READONLY|wx.TE_RICH2)

        self.folder_names = []
        self.result_data = {}
        self.result_headers = {}

        self.curr_item = '' # either correctness or RT for now

    #------------------------------------------------------------

    def select_sessions(self):
        if debug: print 'ResultGraph.select_sessions'

        ### Choosing the data-folder
        dlg = multidirdialog.MultiDirDialog(self, message=u"Choose directories for showing the result data graph.", defaultPath=os.getcwd())
        dlgResult = dlg.ShowModal()
        if dlgResult == wx.ID_OK:
            self.folder_paths = dlg.GetPaths()
            ### Get rid of invalid folder-names
            # Valid folder name format = 'yyyy_mm_dd'
            for full_path in self.folder_paths:
                folder_name = os.path.basename(full_path)
                remove_list = []
                ### if the folder_name doesn't match with the format, discard.
                if len(folder_name) != 10: remove_list.append(full_path)
                elif folder_name[4] != "_" or folder_name[7] != "_": remove_list.append(full_path)
                for i in range(len(remove_list)): self.folder_paths.remove(remove_list[i])
            dlg.Destroy()
            self.journal_text.SetStyle(0,len(self.journal), wx.TextAttr("BLACK", "WHITE"))
            self.search_selected_days() # mark the selected sessions in journal-text
            return True
        else:
            dlg.Destroy()
            return False

    #------------------------------------------------------------

    def collect_result_data(self):
        if debug: print 'ResultGraph.collect_result_data'

        self.folder_names = []
        self.result_data = {}
        self.result_headers = {}
        for i in range(len(self.folder_paths)):
            path = '/Volumes/' + self.folder_paths[i] # in OSX
            cnt_result_csv_file = 0
            for result_csv_file in glob(os.path.join(path, '*.csv')):
                result_file_path = os.path.join(path, result_csv_file)
                result_file = open(result_file_path, 'r')
                lines = result_file.readlines()
                result_file.close()
                if lines[0].startswith('Trial#'): # if this csv-file is a result csv file
                    cnt_result_csv_file += 1
                    self.folder_names.append(os.path.basename(path)) # store folder names with the result csv file
                    self.result_headers[self.folder_names[i]] = [item.strip().upper() for item in copy(lines[0].split(","))] # store the header line
                    self.result_data[self.folder_names[i]] = self.extract_trial_info(lines) # store the data
            if cnt_result_csv_file != 1:
                if cnt_result_csv_file == 0: print 'WARNING: There was no proper CSV result file in the path; %s'%path
                elif cnt_result_csv_file > 1:
                    msg = 'WARNING: There were more than one CSV result file in the path; %s\n'%path
                    msg += 'The last one, %s, was selected.'%result_file_path
                    print msg

        ### Selected sessions list-box
        self.selected_sessions_LB = wx.ListBox(self, -1, (self.window_width-150, self.button_start_posY+50), (150,100), self.folder_names, wx.LB_SINGLE|wx.LB_SORT)
        self.selected_sessions_LB.Bind(wx.EVT_LISTBOX, self.session_selected)
        self.selected_sessions_LB.Bind(wx.EVT_LISTBOX_DCLICK, self.session_selected)    

    #------------------------------------------------------------

    def session_selected(self, event):
        if debug: print 'ResultGraph.session_selected'
        selected_idx = self.selected_sessions_LB.GetSelections()
        if len(selected_idx) > 0: # if there's a selected item in the session list box
            selected_idx = selected_idx[0]
            if self.hundred_trials_chkbox.GetValue() == True and self.sessions_in_result_data != None:
                _tmp = 0
                for i in range(len(self.sessions_in_result_data)):
                    _number_of_sessions = self.sessions_in_result_data[i]
                    _tmp += _number_of_sessions
                    if _tmp > selected_idx:
                        selected_idx = copy(i)
                        break
                if selected_idx > len(self.sessions_in_result_data)-1: selected_idx = len(self.sessions_in_result_data)-1
            self.draw_graph(selected_idx) # draw a graph with an arrow
        else:
            self.draw_graph() # draw a graph

    #------------------------------------------------------------

    def extract_trial_info(self, lines):
        if debug: print 'ResultGraph.extract_trial_info'
        ### collect trial info. only.
        output_lines = []
        for line in lines:
            first_char = line[0]
            try: first_char = int(first_char)
            except: pass
            if type(first_char) == int: # if the first character of the line is a number(trial number)
                output_lines.append(line)
        return output_lines

    #------------------------------------------------------------

    def display_data(self):
        if debug: print 'ResultGraph.display_data'

        self.sessions_in_result_data = None
        if len(self.folder_names) > 0:
            ### Data extraction
            if self.hundred_trials_chkbox.GetValue() == True:
                self.result_data_for_graph = []
                self.sessions_in_result_data = [0] # how many sessions are in each result data point
                if self.curr_item == 'correctness':
                    if self.chart_type_cb.GetValue() == 'Line-chart':
                        self.button_result_data_for_graph = []
                        for i in range(3): self.button_result_data_for_graph.append([]) # correctness-data for 3 buttons
                        self.cnt_correct_trials_3_buttons = [0, 0, 0]
                    self.cnt_trials_tmp = [0,0,0]
                    self.cnt_correct_trials = 0
                elif self.curr_item == 'RT':
                    self.cnt_trials_tmp = 0
                    self.RT = []
            else:
                self.result_data_for_graph = [0.0]*len(self.folder_names)
                self.cnt_trials_in_folder = [] # number of trials for each session(folder)
            for i in range(len(self.folder_names)):
                if self.curr_item == 'correctness': self.extract_correctness_info(i)
                elif self.curr_item == 'RT': self.extract_RT_info(i)

            if self.hundred_trials_chkbox.GetValue() == True:
                if len(self.result_data_for_graph) < len(self.sessions_in_result_data):
                # If number of trials of the last some sessions doesn't reach 100 trails,
                # the above two dataset's number of data don't match
                # In such a case, discard the very last number in self.sessions_in_result_data.
                    self.sessions_in_result_data.pop(len(self.sessions_in_result_data)-1)

            selected_idx = self.selected_sessions_LB.GetSelections()

            if len(selected_idx) > 0: # if there's a selected item in the session list box
                self.session_selected(None)
            else:
                self.draw_graph() # draw a graph

    #------------------------------------------------------------

    def extract_correctness_info(self, folder_idx):
        if debug: print 'ResultGraph.extract_correctness_info'

        _cnt_trials = 0
        _cnt_correct_trials = 0
        lines = self.result_data[self.folder_names[folder_idx]]
        try: ri_idx = self.result_headers[self.folder_names[folder_idx]].index('ACTIVELY_INVOLVED_INDIVIDUAL')
        except:
            print 'ERROR in processing, %s'%self.folder_names[folder_idx]
            return
        cr_idx = self.result_headers[self.folder_names[folder_idx]].index('CORRECT_RESPONSE')
        c_idx = self.result_headers[self.folder_names[folder_idx]].index('CORRECTNESS')
        for line in lines:
            items = line.split(",")
            responsive_individual = items[ri_idx].strip().upper()
            corr_resp = items[cr_idx].strip().lower()
            corr_val = items[c_idx].strip().upper()
            if not responsive_individual.startswith('BLACK') and corr_val != 'TIMEOUT':
            # exclude the trials, Black cat was the main ind. also exclude 'TIMEOUT' trials
                if self.hundred_trials_chkbox.GetValue() == True: # we're dealing with 100-trial batches, not each daily session
                    if corr_resp == 'button1-press': self.cnt_trials_tmp[0] += 1
                    elif corr_resp == 'button2-press': self.cnt_trials_tmp[1] += 1
                    elif corr_resp == 'button3-press': self.cnt_trials_tmp[2] += 1
                    if corr_val == 'CORRECT':
                        self.cnt_correct_trials += 1 # for total correctness
                        if self.chart_type_cb.GetValue() == 'Line-chart':
                            ### for each button's correctness
                            if corr_resp == 'button1-press': self.cnt_correct_trials_3_buttons[0] += 1
                            elif corr_resp == 'button2-press': self.cnt_correct_trials_3_buttons[1] += 1
                            elif corr_resp == 'button3-press': self.cnt_correct_trials_3_buttons[2] += 1
                    if sum(self.cnt_trials_tmp) == 100:
                    # whenever accumulated trial data reaches 100 trials, calculate the correctness
                        self.result_data_for_graph.append(self.cnt_correct_trials) # store the correctness percentage for total trials
                        #print '---'
                        #print self.cnt_correct_trials
                        if self.chart_type_cb.GetValue() == 'Line-chart':
                            for b_idx in range(3):
                            # store the correctness percetages for each button's trials
                                self.button_result_data_for_graph[b_idx].append(self.cnt_correct_trials_3_buttons[b_idx]/float(self.cnt_trials_tmp[b_idx])*100.0)
                                #print self.cnt_correct_trials_3_buttons[b_idx]/float(self.cnt_trials_tmp[b_idx])*100.0
                        #print '---'
                        self.cnt_trials_tmp = [0,0,0]
                        self.cnt_correct_trials = 0
                        self.sessions_in_result_data.append(0)
                        if self.chart_type_cb.GetValue() == 'Line-chart': self.cnt_correct_trials_3_buttons = [0, 0, 0]
                else:
                    if corr_val == 'CORRECT': _cnt_correct_trials += 1
                    _cnt_trials += 1
        if self.hundred_trials_chkbox.GetValue() == True:
            _idx = len(self.sessions_in_result_data)-1
            self.sessions_in_result_data[_idx] += 1
        else:
            if _cnt_trials == 0: correctness = 0
            else: correctness = _cnt_correct_trials / float(_cnt_trials)
            self.result_data_for_graph[folder_idx] = correctness * 100.0 # store the correctness percentage
            self.cnt_trials_in_folder.append(_cnt_trials)

    #------------------------------------------------------------

    def extract_RT_info(self, folder_idx):
        if debug: print 'ResultGraph.extract_RT_info'

        _cnt_trials = 0
        lines = self.result_data[self.folder_names[folder_idx]]
        _RT = []
        ri_idx = self.result_headers[self.folder_names[folder_idx]].index('ACTIVELY_INVOLVED_INDIVIDUAL')
        c_idx = self.result_headers[self.folder_names[folder_idx]].index('CORRECTNESS')
        for line in lines:
            items = line.split(",")
            responsive_individual = items[ri_idx].strip().upper()
            corr_val = items[c_idx].strip().upper()
            if not responsive_individual.startswith('BLACK') and corr_val != 'TIMEOUT':
            # exclude the trials, Black cat was the main ind. also exclude 'TIMEOUT' trials
                start_time = items[1].split("_")
                end_time = items[4].split("_")
                try:
                    for i in range(len(start_time)):
                        start_time[i] = int(start_time[i])
                    for i in range(len(end_time)):
                        end_time[i] = int(end_time[i])
                except:
                    pass
                    continue
                start_time = datetime(year=start_time[0], month=start_time[1], day=start_time[2], hour=start_time[3], minute=start_time[4], second=start_time[5], microsecond=start_time[6])
                end_time = datetime(year=end_time[0], month=end_time[1], day=end_time[2], hour=end_time[3], minute=end_time[4], second=end_time[5], microsecond=end_time[6])

                if self.hundred_trials_chkbox.GetValue() == True:
                    self.RT.append( (end_time - start_time).seconds )
                    self.cnt_trials_tmp += 1
                    if self.cnt_trials_tmp == 100:
                    # whenever accumulated trial data reaches 100 trials, calculate the RT data
                        average_RT = float(sum(self.RT)) / 100
                        self.result_data_for_graph.append(average_RT)
                        self.sessions_in_result_data.append(0)
                        self.cnt_trials_tmp = 0
                        self.RT = []
                else:
                    _RT.append( (end_time - start_time).seconds )
                    _cnt_trials += 1
        if self.hundred_trials_chkbox.GetValue() == True:
            _idx = len(self.sessions_in_result_data)-1
            self.sessions_in_result_data[_idx] += 1
        else:           
            average_RT = float(sum(_RT)) / len(_RT)
            self.result_data_for_graph[folder_idx] = average_RT # store the average reaction-time
            self.cnt_trials_in_folder.append(_cnt_trials)

    #------------------------------------------------------------

    def search_selected_days(self):
        if debug: print 'ResultGraph.search_selected_days'

        first_idx = None
        for i in range(len(self.folder_paths)):
            search_word = os.path.basename(self.folder_paths[i])

            '''
            search_word = search_word.split("_")[0]
            # The folder-name might have '_1', '_2', and so on indicating there were multiple sesssions in a day.
            # Getting rid of this type of tag in the above script line.
            search_word = search_word[:4] + "." + search_word[4:6] + "." + search_word[6:]
            '''
            search_word = search_word.replace("_", ".")
            self.search_result = AADV.search_string(search_word, self.journal, self.journal_text)
            if first_idx == None and len(self.search_result) > 0: first_idx = self.search_result[0] # store the first searched text index
        if first_idx != None: self.journal_text.SetInsertionPoint(first_idx) # move to the next position

    #------------------------------------------------------------

    def draw_graph(self, idx_for_arrow=None):
        if debug: print 'ResultGraph.draw_graph'

        ### Draw the graph
        self.figure = mpl.figure.Figure(figsize=(10,6))
        self.axes = self.figure.add_subplot(111)
        x_data = range(len(self.result_data_for_graph))
        width = 0.8
        _chart_type = self.chart_type_cb.GetValue()
        if _chart_type == 'Bar-chart':
            self.axes.bar( left=x_data, 
                        height=self.result_data_for_graph, 
                        width=width, 
                        bottom=0, 
                        color='#ffffcc', 
                        align='center' )
        elif _chart_type == 'Line-chart':
            if self.curr_item == 'correctness' and self.hundred_trials_chkbox.GetValue() == True:
                self.axes.plot( x_data, self.result_data_for_graph, '-ko', x_data, self.button_result_data_for_graph[0], '--r*', x_data, self.button_result_data_for_graph[1], '--g+', x_data, self.button_result_data_for_graph[2], '--bx')
            else:
                self.axes.plot( x_data, self.result_data_for_graph, '-ko')
            

        title_font = dict( weight='bold', size='x-large')
        label_font = dict( weight='bold', size='large')
        if self.curr_item == 'correctness':
            self.axes.set_title(label='Correctness Plot', fontdict=title_font)
            self.axes.set_ylabel(ylabel='Correctness(%)', fontdict=label_font)
            self.axes.set_ylim(bottom=0, top=100)
        elif self.curr_item == 'RT':
            self.axes.set_title(label='Reaction-time Plot', fontdict=title_font)
            self.axes.set_ylabel(ylabel='Reaction-time;\nfrom Motion-detection to Button-press', fontdict=label_font)
        self.axes.set_xlabel(xlabel='Sessions', fontdict=label_font)
        self.axes.set_xlim(left=-1, right=len(self.result_data_for_graph))
        self.axes.set_xticks([]) # erase the ticks (numbers) on the x-axis with an empty list
        #self.axes.set_xticks(x_data)
        #self.axes.set_xticklabels(self.folder_names)

        if self.curr_item == 'RT': RT_max_val = max(self.result_data_for_graph)

        if self.display_values_chkbox.GetValue() == True:
            ### displaying the values for each bar
            for i in range(len(self.result_data_for_graph)):
                if self.curr_item == 'correctness':
                    if self.hundred_trials_chkbox.GetValue() == True:
                        value = '%.1f'%(self.result_data_for_graph[i])
                    else:
                        value = '%.1f\n(%i trials)'%(self.result_data_for_graph[i], self.cnt_trials_in_folder[i])
                    y_pos = self.result_data_for_graph[i]-7
                elif self.curr_item == 'RT':
                    if self.hundred_trials_chkbox.GetValue() == True:
                        value = '%.1f'%(self.result_data_for_graph[i])
                    else:
                        value = '%.3f\n(%i trials)'%(self.result_data_for_graph[i], self.cnt_trials_in_folder[i])
                    y_pos = self.result_data_for_graph[i]-RT_max_val*0.07
                self.axes.annotate(value, xy=(x_data[i], y_pos))

        ### displyaing an arrow for selected session
        if idx_for_arrow != None:
            if self.curr_item == 'correctness':
                self.axes.arrow( x=x_data[idx_for_arrow], y=0, dx=0, dy=3, head_width=0.2, head_length=3 )
            elif self.curr_item == 'RT':
                dy_val = RT_max_val * 0.03
                head_length_val = RT_max_val * 0.03
                self.axes.arrow( x=x_data[idx_for_arrow], y=0, dx=0, dy=dy_val, head_width=0.2, head_length=head_length_val )

        self.canvas = FigureCanvasWxAgg(self, -1, self.figure)

    #------------------------------------------------------------

    def onRTClick(self, event):
        if debug: print 'ResultGraph.onRTClick'
        self.curr_item = 'RT'
        self.display_data()

    #------------------------------------------------------------

    def onCorrectnessClick(self, event):
        if debug: print 'ResultGraph.onCorrectnessClick'
        self.curr_item = 'correctness'
        self.display_data()

    #------------------------------------------------------------

    def onSelectSessionClick(self, event):
        if debug: print 'ResultGraph.onSelectSessionClick'

        try: self.selected_sessions_LB.Destroy()
        except: pass
        if self.select_sessions() == True:
            self.curr_item = 'correctness'
            self.collect_result_data()
            self.display_data()


#################################################################
# Main Class
#################################################################
class AA_Data_Viewer(wx.Frame):
    def __init__(self):
        if debug: print 'AA_Data_Viewer.__init__'

        self.window_width = 1000
        self.window_height = 700

        wx.Frame.__init__(self, None, -1, "AA_Data_viewer", pos = (0,0), size = (self.window_width,self.window_height), style = wx.DEFAULT_FRAME_STYLE)
        self.Center()
        screenWidth = wx.Display(0).GetGeometry()[2]
        screenHeight = wx.Display(0).GetGeometry()[3]
        self.window_posX = screenWidth/2-self.window_width/2
        self.window_posY = screenHeight/2-self.window_height/2  

        self.panel = wx.Panel(self, pos = (0,0), size = (self.window_width,self.window_height))
        self.panel.SetBackgroundColour('grey')
        
        ### Connecting key-inputs with some functions
        exit_BtnID = 100
        self.Bind(wx.EVT_MENU, self.onExit, id = exit_BtnID)
        accel_tbl = wx.AcceleratorTable([ (wx.ACCEL_SHIFT,  ord('Q'), exit_BtnID ) ])
        self.SetAcceleratorTable(accel_tbl)

        wx.FutureCall(1, self.setup_notebook)
    
    #------------------------------------------------------------

    def setup_notebook(self):
        if debug: print 'AA_Data_Viewer.setup_notebook'

        ### set up notebook 
        self.nb = wx.Notebook(self.panel, size=(self.window_width,self.window_height-25))
        self.page1 = _blankPage(self.nb)
        self.page2 = DataBrowser(self.nb)
        self.page3 = ResultGraph(self.nb)
        self.nb.AddPage(self.page1, "")
        self.nb.AddPage(self.page2, "Data Browser")
        self.nb.AddPage(self.page3, "Result graph")

    #------------------------------------------------------------

    def search_string(self, search_str, text, textCtrl):
        search_str = search_str.lower()
        str_len = len(search_str)
        search_result = []
        search_result_idx = 0
        idx = 0
        start_idx = 0
        idx = text.find(search_str, start_idx) # search the search_str in the given text, and return the index
        while idx != -1:
            search_result.append(idx)
            start_idx = idx+str_len
            textCtrl.SetStyle(idx,idx+str_len, wx.TextAttr("BLUE", "GREY"))
            idx = text.find(search_str, start_idx)
        if len(search_result) > 0:
            textCtrl.SetInsertionPoint(search_result[0]) # move to the first search-result
            textCtrl.SetStyle(search_result[0],search_result[0]+str_len, wx.TextAttr("YELLOW", "GREY"))
        return search_result

    #------------------------------------------------------------

    def onExit(self, event):
        if debug: print "AA_Data_Viewer.onExit"
        self.Destroy()

#################################################################
# Class for Pop-up message
#################################################################
class PopupDialog(wx.Dialog):
    def __init__(self, parent = None, id = -1, title = "AA_Dialog", inString = "", size = (200, 150)):
        wx.Dialog.__init__(self, parent, id, title)
        self.SetSize(size)
        self.Center()
        txt = wx.StaticText(self, -1, label = inString, pos = (20, 20))
        txt.SetSize(size)
        txt.SetFont(wx.Font(15, wx.DEFAULT, wx.NORMAL, wx.NORMAL, False))
        okButton = wx.Button(self, wx.ID_OK, "OK")
        b_size = okButton.GetSize()
        okButton.Position = (size[0] - b_size[0] - 20, size[1] - b_size[1] - 40)
        okButton.SetDefault()


if __name__ == "__main__":
    AAviewerApp = wx.App()
    AADV = AA_Data_Viewer()
    AADV.Show()
    AAviewerApp.MainLoop()





