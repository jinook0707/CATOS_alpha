'''
videoIn_module.py
This is for continuously watching a scene through a webcam
and recording only when certain condition was met such as
bounding rect of movement points were in certain range of
size.
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
import os

from time import sleep, time
from copy import copy
from math import sqrt
from glob import glob

import cv ###
import numpy as np ###
from scipy import asarray
#from scipy.ndimage import measurements
from scipy.cluster.hierarchy import fclusterdata

from common_module import writeFile, chk_fps, get_time_stamp, chk_session_time, update_log_file_path

FLAG_INITIAL_DELAY = True # wait 1.5 minutes before actual function starting

FLAG_DEBUG = False
FLAG_DEBUG_CV_WIN = False
FLAG_FFMPEG_ON_THE_RUN = False

PLACE_TO_CHECK_MOVEMENTS = ""
LOG = ''

#------------------------------------------------------------------------------------

def videoIn_run(vi_conn, log_file_path, output_folder, cID, flag_ffmpeg_on_the_run, session_start_hour, session_end_hour):
    global FLAG_DEBUG, FLAG_FFMPEG_ON_THE_RUN, LOG, PLACE_TO_CHECK_MOVEMENTS
    cwd = os.getcwd()
    FLAG_FFMPEG_ON_THE_RUN = flag_ffmpeg_on_the_run
    LOG = log_file_path

    if FLAG_INITIAL_DELAY:
        func_start_time = time()
        while True:
            elapsed_time = time() - func_start_time
            #print "Elapsed time: %i (s)"%elapsed_time
            if elapsed_time > 90: # wait for 1.5 minutes before actual starting
                break

    CV_inst = C_Vision(vi_conn, cwd, output_folder, cID)

    last_fps_timestamp = time()
    fps_cnt = 0
    flag_session_changed_to_off = False
    flag_session_changed_to_on = False
    while True:
        if chk_session_time(session_start_hour, session_end_hour) == False:
            if flag_session_changed_to_off == False: # 1st run after finishing the session-time
                CV_inst = None # Turn off CV
                flag_session_changed_to_off = True
                flag_session_changed_to_on = False
            if vi_conn.poll(): # check whether there's any message arrived through the pipe
                msg = vi_conn.recv() # receive the message
                if msg == 'q':
                    break
            sleep(1)
            continue
        else:
            if flag_session_changed_to_on == False: # 1st run after starting the session-time
                flag_session_changed_to_off = False
                flag_session_changed_to_on = True
                LOG = update_log_file_path(output_folder, LOG)
                CV_inst = C_Vision(vi_conn, cwd, output_folder, cID) # initialize the CV

        ### FPS-check
        fps, fps_cnt, last_fps_timestamp = chk_fps(last_fps_timestamp, fps_cnt)
        if FLAG_DEBUG:
            if fps != -1: print "LoopPerSecond-check from video module : %i"%fps

        CV_inst.run(fps) # run the image porcessing

        if CV_inst.flag_save_movie != None:
            if FLAG_FFMPEG_ON_THE_RUN:
                ### send a message for generating a movie file
                file_name = "%s_cID%.2i%s"%(CV_inst.recording_timestamp, cID, CV_inst.movie_file_ext)
                output_video_file = os.path.join(cwd, output_folder, file_name)
                tmp_file = CV_inst.recording_timestamp + "_%05d.jpg"
                tmp_file = os.path.join(CV_inst.tmp_img_dir_path, tmp_file)
                command = ("ffmpeg -r %i -i %s -vcodec %s -qscale %i %s,%s")%(CV_inst.rec_fps, tmp_file, CV_inst.movie_vcodec, CV_inst.movie_vquality, output_video_file, CV_inst.tmp_img_dir_path)
                vi_conn.send(command) # send the command to the organizer to save the movie
            CV_inst.init_movie_params()

        if vi_conn.poll(): # check whether there's any message arrived through the pipe
            msg = vi_conn.recv() # receive the message
            if msg == 'q':
                break
            elif msg == 'check_motion_at_feeder':
                PLACE_TO_CHECK_MOVEMENTS = "feeder"

#------------------------------------------------------------------------------------

class C_Vision(object):
    def __init__(self, vi_conn, cwd, output_folder, cID):
        self.behavior_rec_path = ''
        self.vi_conn = vi_conn
        self.cwd = cwd
        self.output_folder = output_folder
        self.cID = cID

        if cID == 0: rect_for_movements_at_feeder = [175, 46, 58, 75] # [100, 65, 63, 95] # x, y, w, h
        #elif cID == 1: rect_for_movements_at_feeder = [175, 46, 58, 75]
        self.x_range_for_feeder_movements = [rect_for_movements_at_feeder[0]-1, rect_for_movements_at_feeder[0]+rect_for_movements_at_feeder[2]+1]
        self.y_range_for_feeder_movements = [rect_for_movements_at_feeder[1]-1, rect_for_movements_at_feeder[1]+rect_for_movements_at_feeder[3]+1]

        ### min & max values for InRangeS function for detecting whitish blob
        if self.cID == 0:
            self.HSV_min = (0,0,250)
            self.HSV_max = (179,124,254) #(179,99,254)
        elif self.cID == 1:
            self.HSV_min = (0,0,250)
            self.HSV_max = (179,124,254)

        if FLAG_DEBUG_CV_WIN:
            self.win_name = 'debug#%i'%self.cID
            cv.NamedWindow(self.win_name, cv.CV_WINDOW_NORMAL)
            cv.MoveWindow(self.win_name, cID*150, cID*150)

        ### capturing cameara setup
        self.cap_cam = cv.CaptureFromCAM(cID)
        sleep(3)
        if FLAG_DEBUG: print "Camera #%.2i is connected."%cID
        cv.SetCaptureProperty(self.cap_cam, cv.CV_CAP_PROP_FRAME_WIDTH, 640)
        cv.SetCaptureProperty(self.cap_cam, cv.CV_CAP_PROP_FRAME_HEIGHT, 480)

        ### images setup        
        frame = cv.QueryFrame(self.cap_cam)
        frame_size = cv.GetSize(frame)
        fSize_quarter = (frame_size[0]/2,frame_size[1]/2)
        self.frame_size = frame_size
        self.fSize_quarter = fSize_quarter
        self.color_image = cv.CreateImage(frame_size, 8, 3)
        self.color_image_resize = cv.CreateImage(fSize_quarter, 8, 3)
        self.color_image_for_masking = cv.CreateImage(fSize_quarter, 8, 3)
        self.grey_image = cv.CreateImage(fSize_quarter, cv.IPL_DEPTH_8U, 1)
        self.grey_avg = cv.CreateImage(fSize_quarter, cv.IPL_DEPTH_32F, 1)
        self.temp_grey = cv.CreateImage(fSize_quarter, cv.IPL_DEPTH_8U, 1)
        self.diff_grey = cv.CreateImage(fSize_quarter, cv.IPL_DEPTH_8U, 1)
        self.storage = cv.CreateMemStorage(0)
        self.grey_bg_img = cv.CreateImage(fSize_quarter, cv.IPL_DEPTH_8U, 1)
        self.mask_img = cv.CreateImage(fSize_quarter, cv.IPL_DEPTH_8U, 1)
        self.buffer_images = []

        self.first_run = True
        self.last_time_behavior_recorded = 0.0

        self.th_for_contour_frag = 35 # threshold(width+height of the rect which surrounds one fragment of contours) to be accounted as valid contour fragment
        self.min_th_for_movement = 65 # minimum threshold(width+height) to be accounted as a whole movement
        self.max_th_for_movement = 400 # maximum threshold(width+height) to be accounted as a whole movement
        self.clustering_th = 45 # clustering threshold (minimum distance between blobs to be distinguished as a blob)
        
        self.maximum_frame_cnt = 100000 # if the number of jpeg images exceed this number, start a new temp jpeg folder

        self.movie_file_ext = '.mp4'
        self.movie_vcodec = 'libx264'
        self.movie_vquality = 10
        self.rec_fps = [] # fps for recording a movie

        self.flag_recording_started = False
        self.recording_timestamp = None
        self.has_been_quiet_since = -1 # To check how long it has been quiet.
        self.maximum_q_duration = 3 # in seconds. Recording persists for this amount of time even it has been quiet.
        self.MR_interval = 0.1 # interval between the movement recordings (in seconds)

        self.recognized_blobs = []
        self.max_blob_number = 10 # maximum number of blobs which can be stored in self.recognized_blobs
        self.max_still_blob_dur = 600 # maximum STILL(not moving/changing) blob is allowed to be counted as a blob for this amount of time(in seconds)
        # When the same STILL blob exists over this amount of time, the background image will be updated with this blob image.
        self.still_blob_chk_interval = 10 # interval to check the registered blobs (in seconds)
        self.last_blob_chk_time = -1

        self.flag_take_first_bg_image = True
        self.save_first_img_for_session()

        self.inst_start_time = time()

    #---------------------------------------------------------------------------------

    def save_first_img_for_session(self):
        ### save the first image from the cam
        first_color_image = cv.QueryFrame(self.cap_cam)
        capture_file_name = "_first_color_img_cID%.2i.jpg"%(self.cID)
        capture_file_path = os.path.join(self.cwd, self.output_folder, capture_file_name)
        cv.SaveImage(capture_file_path, first_color_image)
    
    #---------------------------------------------------------------------------------

    def take_bg_img(self):
    # take the background image for the process
        self.color_image = cv.QueryFrame(self.cap_cam)
        cv.Resize(self.color_image, self.color_image_resize)
        cv.CvtColor(self.color_image_resize, self.grey_bg_img, cv.CV_RGB2GRAY)
        cv.Smooth(self.grey_bg_img, self.grey_bg_img, cv.CV_GAUSSIAN, 9, 0)
        cv.Dilate(self.grey_bg_img, self.grey_bg_img, None, 3)
        cv.Erode(self.grey_bg_img, self.grey_bg_img, None, 3)       

    #---------------------------------------------------------------------------------

    def run(self, fps):
        global PLACE_TO_CHECK_MOVEMENTS

        if self.flag_take_first_bg_image == True: # First bg-image has to be taken at the beginning
            self.take_bg_img()
            self.flag_take_first_bg_image = False

        self.color_image = cv.QueryFrame(self.cap_cam)

        #########################################################################################
        # Pre-processing
        #########################################################################################
        cv.Resize(self.color_image, self.color_image_resize)

        cv.CvtColor(self.color_image_resize, self.grey_image, cv.CV_RGB2GRAY)
        cv.Smooth(self.grey_image, self.grey_image, cv.CV_GAUSSIAN, 7, 0)       
        cv.Dilate(self.grey_image, self.grey_image, None, 2)
        cv.Erode(self.grey_image, self.grey_image, None, 2)

        #########################################################################################
        # Checking movements
        #########################################################################################
        if self.first_run:
            self.first_run = False
            cv.ConvertScale(self.grey_image, self.grey_avg, 1.0, 0.0)
        else:
            cv.RunningAvg(self.grey_image, self.grey_avg, 0.3, None)

        cv.ConvertScale(self.grey_avg, self.temp_grey, 1.0, 0.0) # Convert the scale of the moving average. (for Motion-detection)
        cv.AbsDiff(self.grey_image, self.temp_grey, self.diff_grey) # Minus the current frame from the moving average. (for Motion-detection)
        cv.Canny(self.diff_grey, self.diff_grey, 10, 15) # Find Edges for Motion-detection

        m_min_pt1, m_max_pt2, m_center_pt_list = self.get_points(self.diff_grey) # get some useful points from the movement's contours


        #########################################################################################
        # Get rid of changing blobs from the recognized blobs to figure out which blob is 'STILL'
        #########################################################################################
        if time() - self.last_blob_chk_time > self.still_blob_chk_interval:
            removal_idx = []
            for i in range(len(self.recognized_blobs)):
                recognized_time = self.recognized_blobs[i][1]
                bound_rect = self.recognized_blobs[i][2]
                cv.Zero(self.mask_img)
                curr_img_in_blob_location = cv.CloneImage(self.mask_img)
                diff_img = cv.CloneImage(self.mask_img)
                cv.Rectangle(self.mask_img, (bound_rect[0],bound_rect[1]), (bound_rect[0]+bound_rect[2],bound_rect[1]+bound_rect[3]), 255, cv.CV_FILLED)
                cv.Copy(self.grey_image, curr_img_in_blob_location, self.mask_img)
                cv.AbsDiff(self.recognized_blobs[i][0], curr_img_in_blob_location, diff_img)
                cv.Threshold(diff_img, diff_img, 30, 255, cv.CV_THRESH_BINARY)
                mat_diff_img = cv.GetMat(diff_img)
                moments = cv.Moments(mat_diff_img)
                overall_changed_area = cv.GetCentralMoment(moments, 0, 0)
                if overall_changed_area < 2000:
                    pass
                    '''
                    x = bound_rect[0]*2
                    y = bound_rect[1]*2
                    w = bound_rect[2]*2
                    h = bound_rect[3]*2
                    cv.Rectangle(self.color_image, (x,y), (x+w,y+h), (255,0,0), 2)
                    '''
                else:
                    removal_idx.append(i)

                if time() - recognized_time > self.max_still_blob_dur: # this blob is recognized over certain time
                    ### get little bigger image around the blob, then update the background - image
                    cv.Rectangle(self.mask_img, (bound_rect[0]-20,bound_rect[1]-20), (bound_rect[0]+bound_rect[2]+20,bound_rect[1]+bound_rect[3]+20), 255, cv.CV_FILLED)
                    cv.Zero(curr_img_in_blob_location)
                    new_bg_img = cv.CloneImage(curr_img_in_blob_location)
                    cv.Copy(self.grey_image, curr_img_in_blob_location, self.mask_img) # get the changed image part
                    cv.Not(self.mask_img, self.mask_img) # invert the mask image
                    cv.Copy(self.grey_bg_img, new_bg_img, self.mask_img) # get the unchanged bg-image
                    cv.Add(curr_img_in_blob_location, new_bg_img, self.grey_bg_img) # combine the above two into the bg-img
                    timestamp = get_time_stamp()
                    writeFile(LOG, '%s, Background was updated on Cam #%i'%(timestamp, self.cID))
                    '''
                    ### Save the changed bg-img
                    capture_file_name = "_changed_bg_img_cID%.2i_%s.jpg"%(self.cID, timestamp)
                    capture_file_path = os.path.join(self.cwd, self.output_folder, capture_file_name)
                    cv.SaveImage(capture_file_path, self.grey_bg_img)
                    '''
                    if i not in removal_idx:
                        removal_idx.append(i) # this blob info will be removed
            for i in range(len(removal_idx)): self.recognized_blobs.pop(removal_idx[i]-i)
            self.last_blob_chk_time = time()


        #########################################################################################
        # Foreground blob checking
        #########################################################################################
        foreground, fg_mask_img, fg_size = self.bg_subtraction(self.grey_image) # background subtraction

        f_min_pt1, f_max_pt2, f_center_pt_list = self.get_points(foreground) # get some useful points from the foregournd contours

        ### checking foreground blobs and register it
        number_of_fBlobs = 0
        grouped_points_for_fBlobs = []
        if len(f_center_pt_list) > 0:
            
            number_of_fBlobs, grouped_points_for_fBlobs = self.clustering(f_center_pt_list) # clustrering foreground-blobs
            if number_of_fBlobs < 2:
                if f_min_pt1 != [] and f_max_pt2 != []:
                    number_of_fBlobs = 1
                    x = f_min_pt1[0] + (f_max_pt2[0]-f_min_pt1[0])/2
                    y = f_min_pt1[1] + (f_max_pt2[1]-f_min_pt1[1])/2
                    grouped_points_for_fBlobs = [[[x, y]]]
                    if len(self.recognized_blobs) < self.max_blob_number:
                        bound_rect = (f_min_pt1[0], f_min_pt1[1], f_max_pt2[0]-f_min_pt1[0], f_max_pt2[1]-f_min_pt1[1])
                        self.chk_and_register_fBlob(bound_rect)
            else:
                for grouped_points in grouped_points_for_fBlobs:
                    if len(self.recognized_blobs) < self.max_blob_number:
                        bound_rect = cv.BoundingRect(grouped_points)
                        self.chk_and_register_fBlob(bound_rect)

        #########################################################################################
        # Movement Recording
        #########################################################################################
        if len(m_center_pt_list) > 0: # there was a rect indicating the movements
            whole_bounding_rect = (m_min_pt1[0], m_min_pt1[1], m_max_pt2[0]-m_min_pt1[0], m_max_pt2[1]-m_min_pt1[1])
            if self.min_th_for_movement < whole_bounding_rect[2] + whole_bounding_rect[3] < self.max_th_for_movement:
            # bounding rect for all the movement points is within the thresholds
                self.has_been_quiet_since = -1 # it's not quiet
                self.data_recording(fps) # data-recording

                ### Record movement detail with certain interval
                if time() > self.last_time_behavior_recorded + self.MR_interval:

                    ### Find out where the white blob is
                    whitish_area = -1
                    white_x = -1
                    white_y = -1
                    '''
                    ### Temporarily disabled. Not very useful at the moment.
                    if len(f_center_pt_list) > 0:
                        ### make the color image with the area left(= detected blob) after background subtraction
                        cv.Zero(self.color_image_for_masking)
                        cv.Copy(self.color_image_resize, self.color_image_for_masking, fg_mask_img)

                        ### save the masked color image for analysis purpose (Temporary)
                        #capture_file_path = os.path.join(self.cwd, self.output_folder, '_tmp', '%s.jpg'%get_time_stamp())
                        #cv.SaveImage(capture_file_path, self.color_image_for_masking)

                        ### extract whitish color
                        cv.CvtColor(self.color_image_for_masking, self.color_image_for_masking, cv.CV_BGR2HSV)
                        cv.InRangeS(self.color_image_for_masking, self.HSV_min, self.HSV_max, self.grey_image)
                        ### calculate its(whitish blob) size and position
                        mat_result_whitish_blob = cv.GetMat(self.grey_image)
                        moments = cv.Moments(mat_result_whitish_blob)
                        whitish_area = cv.GetCentralMoment(moments,0,0)
                        white_x = -1
                        white_y = -1
                        if whitish_area > 1000:
                            white_x = int(cv.GetSpatialMoment(moments, 1, 0)/whitish_area)
                            white_y = int(cv.GetSpatialMoment(moments, 0, 1)/whitish_area)
                    '''
                    ### make the movement-record
                    movement_rect = (m_min_pt1[0], m_min_pt1[1], m_max_pt2[0]-m_min_pt1[0], m_max_pt2[1]-m_min_pt1[1])
                    if len(f_min_pt1) != 0:
                        foreground_rect = (f_min_pt1[0], f_min_pt1[1], f_max_pt2[0]-f_min_pt1[0], f_max_pt2[1]-f_min_pt1[1])
                        fg_x = foreground_rect[0]+foreground_rect[2]/2
                        fg_y = foreground_rect[1]+foreground_rect[3]/2
                    else:
                        foreground_rect = '(-1/ -1/ -1/ -1)'
                        fg_x = fg_y = -1
                    writeFile(self.behavior_rec_path, "%s, %i/%i, %s, %i/%i, %i, %i, %i, %i/%i, %s, %s\n"%(
                                str(movement_rect).replace(",","/"), 
                                movement_rect[0]+movement_rect[2]/2, movement_rect[1]+movement_rect[3]/2, 
                                str(foreground_rect).replace(",","/"), 
                                fg_x, fg_y, number_of_fBlobs, int(fg_size),
                                int(whitish_area), white_x, white_y, 
                                str(grouped_points_for_fBlobs).replace(",", "/"), get_time_stamp()))
                    self.last_time_behavior_recorded = time()

                    ### Checking on order from main_module
                    if len(PLACE_TO_CHECK_MOVEMENTS) > 0:
                        if PLACE_TO_CHECK_MOVEMENTS == 'feeder':
                            if self.x_range_for_feeder_movements[0] < fg_x < self.x_range_for_feeder_movements[1]:
                                if self.y_range_for_feeder_movements[0] < fg_y < self.y_range_for_feeder_movements[1]:
                                    self.vi_conn.send("motion_at_feeder")
                                    PLACE_TO_CHECK_MOVEMENTS = ""
            else:
                self.flag_save_movie = self.quiet_now(fps)
        else:
            self.flag_save_movie = self.quiet_now(fps)

        if self.flag_recording_started == False: self.save_buffer_img() # if it's not recording, save the buffer image

        #if FLAG_DEBUG_CV_WIN: self.color_image = cv.QueryFrame(self.cap_cam); cv.ShowImage(self.win_name, self.color_image)
    
    #---------------------------------------------------------------------------------

    def bg_subtraction(self, inImage):
    # Background Subtraction
        cv.AbsDiff(inImage, self.grey_bg_img, self.diff_grey)
        cv.Threshold(self.diff_grey, self.diff_grey, 30, 255, cv.CV_THRESH_BINARY)

        mask_img = cv.CloneImage(self.diff_grey)        
        cv.Dilate(mask_img, mask_img, None, 12)     

        mat_diff_grey = cv.GetMat(self.diff_grey)
        ### find out the overall size of the blobs
        moments = cv.Moments(mat_diff_grey)
        overall_area = cv.GetCentralMoment(moments, 0, 0)

        cv.Canny(self.diff_grey, self.diff_grey, 10, 15)
        return self.diff_grey, mask_img, overall_area

    #---------------------------------------------------------------------------------

    def get_points(self, inImage):
    # get the binary image after edge-detection and returns the some useful points of its contours
        contour = cv.FindContours(inImage, self.storage, cv.CV_RETR_CCOMP, cv.CV_CHAIN_APPROX_SIMPLE)
        min_pt1 = []
        max_pt2 = []
        center_pt_list = []
        while contour:
            contour_list = list(contour)
            contour = contour.h_next()
            bound_rect = cv.BoundingRect(contour_list)
            pt1 = (bound_rect[0], bound_rect[1])
            pt2 = (bound_rect[0] + bound_rect[2], bound_rect[1] + bound_rect[3])

            if bound_rect[2] + bound_rect[3] > self.th_for_contour_frag:
                center_pt_list.append([bound_rect[0]+bound_rect[2]/2, bound_rect[1]+bound_rect[3]/2])
                if len(min_pt1) == 0:
                    min_pt1 = list(pt1)
                    max_pt2 = list(pt2)
                else:
                    if min_pt1[0] > pt1[0]: min_pt1[0] = int(pt1[0])
                    if min_pt1[1] > pt1[1]: min_pt1[1] = int(pt1[1])
                    if max_pt2[0] < pt2[0]: max_pt2[0] = int(pt2[0])
                    if max_pt2[1] < pt2[1]: max_pt2[1] = int(pt2[1])
        return min_pt1, max_pt2, center_pt_list

    #---------------------------------------------------------------------------------

    def clustering(self, center_pt_list):       
        pt_arr = np.asarray(center_pt_list)
        result = []
        try: result = list(fclusterdata(pt_arr, self.clustering_th, 'distance'))
        except: pass
        number_of_groups = 0
        groups = []
        if result != []:
            groups = []
            number_of_groups = max(result)
            for i in range(number_of_groups): groups.append([])
            for i in range(len(result)):
                groups[result[i]-1].append(center_pt_list[i])
        return number_of_groups, groups

    #---------------------------------------------------------------------------------

    def chk_and_register_fBlob(self, bound_rect):
        ### if this foreground-blob is not already recognized
        flag_same_blob_already_recognized = False
        for i in range(len(self.recognized_blobs)):
            if bound_rect == self.recognized_blobs[i][2]: flag_same_blob_already_recognized = True

        if flag_same_blob_already_recognized == False:
            cv.Zero(self.mask_img)

            # Register this blob
            self.recognized_blobs.append([cv.CloneImage(self.mask_img), time(), bound_rect]) # recognized blob has its image, timestamp, bound_rect
            
            cv.Rectangle(self.mask_img, (bound_rect[0],bound_rect[1]), (bound_rect[0]+bound_rect[2],bound_rect[1]+bound_rect[3]), 255, cv.CV_FILLED)
            cv.Copy(self.grey_image, self.recognized_blobs[-1][0], self.mask_img)

    #---------------------------------------------------------------------------------

    def data_recording(self, fps):
        if self.flag_recording_started == False: # This is the beginning of storing the video_data
            curr_time_stamp = get_time_stamp()
            if self.recording_timestamp != curr_time_stamp:
                self.recording_timestamp = copy(curr_time_stamp)
                self.recording_frame_cnt = 0
                if FLAG_DEBUG: print "Video-recording starts @ %s"%self.recording_timestamp
                self.start_new_tmp_img_dir()
                self.start_new_MR()
                writeFile(LOG, '%s, Start a video-recording from CAM#%i'%(self.recording_timestamp, self.cID))
                self.record_past_buffer_imgs()
                self.buffer_images = [] # clear the buffer images
                self.save_tmp_image()
                if fps != -1: self.rec_fps.append(fps)
                self.flag_recording_started = True
        else: # The recording already started
            if self.recording_frame_cnt < self.maximum_frame_cnt:
                self.save_tmp_image()
                if fps != -1: self.rec_fps.append(fps)
                #if fps != -1: self.rec_fps = (self.rec_fps + fps)/2
            else:
                if FLAG_DEBUG: print "Video-recording finishes @ %s due to exceeding the maximum frame-rate."%get_time_stamp()
                writeFile(LOG, '%s, Finish the video-recording from %i\nThe average FPS during the recording was, %i'%(get_time_stamp(), self.cID, int(np.median(self.rec_fps))))
                self.init_movie_params()
                self.data_recording(fps)

    #---------------------------------------------------------------------------------

    def start_new_tmp_img_dir(self):
        self.tmp_img_dir_path = os.path.join(self.cwd, self.output_folder, self.recording_timestamp)
        while os.path.isdir(self.tmp_img_dir_path): self.tmp_img_dir_path += 'x'
        os.mkdir(self.tmp_img_dir_path)
    
    #---------------------------------------------------------------------------------

    def start_new_MR(self):
    # start a new MovementRecord file
        time_stamp = os.path.split(self.tmp_img_dir_path)[1].replace("x", "") # obtain the time-stamp without 'x's
        self.behavior_rec_path = os.path.join(self.cwd, self.output_folder, "%s_cID%.2i_MR.csv"%(time_stamp, self.cID))
        txt = "Movement-rect, Movement-center, Foreground-rect, "
        txt += "Foreground-center, Number of blobs, Foreground Blob moment-area, Whitish blob moment-area, "
        txt += "Whitish blob position, Grouped Points for Foreground-Blobs, TimeStamp\n------------------------------------"
        writeFile(self.behavior_rec_path, txt)

    #---------------------------------------------------------------------------------

    def record_past_buffer_imgs(self):
    # put some past data(buffer images) into the tmp_images
        for i in range(len(self.buffer_images)):
            capture_file_name = "%s_%.5i.jpg"%(self.recording_timestamp, self.recording_frame_cnt)
            self.recording_frame_cnt += 1
            capture_file_path = os.path.join(self.tmp_img_dir_path, capture_file_name)
            cv.SaveImage(capture_file_path, self.buffer_images[i])

    #---------------------------------------------------------------------------------

    def save_tmp_image(self):
        capture_file_name = "%s_%.5i.jpg"%(self.recording_timestamp, self.recording_frame_cnt)
        self.recording_frame_cnt += 1
        capture_file_path = os.path.join(self.tmp_img_dir_path, capture_file_name)
        cv.SaveImage(capture_file_path, self.color_image)

    #---------------------------------------------------------------------------------

    def init_movie_params(self):
        self.flag_recording_started = False
        self.has_been_quiet_since = -1
        self.tmp_img_dir_path = None
        self.recording_frame_cnt = 0

    #---------------------------------------------------------------------------------

    def save_buffer_img(self):
        self.buffer_images.append(cv.CloneImage(self.color_image))
        if len(self.buffer_images) > 8: self.buffer_images.pop(0) # fps is usually 7~8. having frames for 1 sec.

    #---------------------------------------------------------------------------------

    def quiet_now(self, fps):
        if self.flag_recording_started: # if it's not recording, there's no need to check the quiet state
            curr_time = time()
            if self.has_been_quiet_since == -1: self.has_been_quiet_since = time()
            else:
                if curr_time - self.has_been_quiet_since > self.maximum_q_duration:
                # quiet moment is longer than maximum-quiet-duration
                    if FLAG_DEBUG: print "Video-recording finishes @ %s"%get_time_stamp()
                    writeFile(LOG, '%s, Finish the video-recording from CAM#%i\nThe average FPS during the recording was, %i'%(get_time_stamp(), self.cID, int(np.median(self.rec_fps))))
                    return "save_the_movie"
                else:
                    self.data_recording(fps)
        return None

#------------------------------------------------------------------------------------
