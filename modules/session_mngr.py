'''
This module is for managing an experimental session procedure.
'''
from time import sleep
from random import randint
from datetime import datetime
import Queue

import wx
from misc_funcs import writeFile, get_time_stamp, update_log_file_path, show_msg, chk_msg_q, make_b_curve_coord

# ======================================================

class ESessionManager:
    def __init__(self, parent):
        self.parent = parent
        wx.FutureCall(1000, self.init_timer)
        self.msg_q = Queue.Queue()
        self.active_time = [7, 17]
        self.state = 'active'

    # --------------------------------------------
    
    def init_timer(self):
        ''' set timer for processing message '''
        self.timer = wx.Timer(self.parent)
        self.parent.Bind(wx.EVT_TIMER, self.onTimer, self.timer)
        self.timer.Start( (1000/30) )

    # --------------------------------------------
    
    def onTimer(self, event):
        ''' Timer for checking message and processing with the current state
        '''
        ### retrieve and process messages
        while self.msg_q.empty() == False:
            msg_src, msg_body, msg_details = chk_msg_q(self.msg_q) # listen to a message
            
        ### start/stop session
        now = datetime.now()
        if self.state == 'active':
            if self.active_time[0] > now.hour or now.hour >= self.active_time[1]:
                self.state = 'sleep'
                self.parent.stop_mods('videoIn')
                self.parent.stop_mods('audioIn')
        elif self.state == 'sleep':
            if self.active_time[1] > now.hour >= self.active_time[0]:
                self.state = 'active'
                self.parent.start_mods('videoIn')
                self.parent.start_mods('audioIn')

    # --------------------------------------------
    
    def quit(self):
        self.timer.Stop()

    # --------------------------------------------
    
# ======================================================


if __name__ == '__main__':
    pass



