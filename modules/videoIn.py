import Queue
from time import time, sleep
from datetime import datetime
from copy import copy
from os import path, mkdir

import cv2
import numpy as np

from modules.misc_funcs import get_time_stamp, writeFile, chk_fps, chk_msg_q, calc_pt_line_dist

flag_window = True # create an opencv window or not

# ======================================================

class VideoIn:
    def __init__(self, parent, cam_idx, pos=(300, 25)):
        self.parent = parent
        self.cam_idx = cam_idx
        self.cap_cam = cv2.VideoCapture()
        self.cap_cam.open(cam_idx)
        sleep(0.5)
        for i in xrange(3):
            ret, frame = self.cap_cam.read()
            if ret == True: break
            sleep(0.1)
        self.fSize = (int(frame.shape[1]/2), int(frame.shape[0]/2))
        self.cap_cam.set(3, self.fSize[0]) # set the width of frame
        self.cap_cam.set(4, self.fSize[1]) # set the height of frame

        self.contour_threshold = 40
        self.roi_pts = [ (25,10), (250,580), (450,760), (610,760), (1060,440), (1150,10) ] # points for Region Of Interest 
        self.m_wrectTh = (100, 1700) # min & max threshold for wrect (whole bounding rect) of movement

        self.msg_q = Queue.Queue()
        if flag_window == True:
            cv2.namedWindow('CATOS_CAM%.2i'%self.cam_idx, cv2.WINDOW_NORMAL)
            cv2.moveWindow('CATOS_CAM%.2i'%self.cam_idx, pos[0], pos[1])

    # --------------------------------------------------

    def run(self, flag_chk_cam_view=False, flag_feeder=False):
        msg = ''
        fps=0; prev_fps=[]; prev_fps_time=time()
        mod_name = 'videoIn'
        first_run = True
        # average NMC ( Number of Movement Contours, Image moment is not used. Image moment will be much bigger if a monkey is closer to the webcam )
        # average distance between movement contours
        # average CMC ( center of movement contours : (int(sum(contours.X) / NMC), int(sum(contours.Y) / NMC)) )
        # length of video
        nmc = 0 # Number of movement contours
        dist_b_mc = [] # average Distance between movement contours
        cmcX = [] # X-pos of average Center of movement contours
        cmcY = [] # Y-pos of average Center of movement contours
        movLog_fp = path.join( self.parent.output_folder, '%s_MovLog.txt'%(get_time_stamp()) ) # movement log file
        if flag_chk_cam_view == False:
            f = open(movLog_fp, 'w')
            f.write('timestamp, sum.NMC, avg.Dist_b_MC, avg.CMC-X, avg.CMC-Y\n')
            f.close()
        writeFile(self.parent.log_file_path, '%s, [%s], webcam %i starts. Frame-size: %s\n'%(get_time_stamp(), mod_name, self.cam_idx, str(self.fSize)))

        # Wait for a few seconds while retreiving webcam images
        # (When webcam is initialized, retreived images change at the beginning, 
        # and it's recognized as movements.)
        func_init_time = time()
        while time()-func_init_time < 1:
            ret, frame_arr = self.cap_cam.read() # get a new frame
            cv2.waitKey(100)
        last_mov_log_time = time()
        while True:
            fps, prev_fps, prev_fps_time = chk_fps(mod_name, fps, prev_fps, prev_fps_time, self.parent.log_file_path)

            ret, frame_arr = self.cap_cam.read() # get a new frame
            if ret == False: sleep(0.1); continue

            if flag_chk_cam_view == False:
                grey_img = cv2.cvtColor(frame_arr, cv2.COLOR_RGB2GRAY) # grey image
                grey_img = self.preprocessing(grey_img) # preprocess the grey image
                
                ### leave only the area surrounded by three screens
                mask = np.zeros( (grey_img.shape[0], grey_img.shape[1]) , dtype=np.uint8 )
                cv2.fillConvexPoly(mask, np.asarray(self.roi_pts), 255)
                grey_img = cv2.bitwise_and( grey_img, grey_img, mask=mask )
                
                ### processing of motion around screens
                if first_run == True:
                    first_run = False
                    grey_avg = cv2.convertScaleAbs(grey_img)
                    grey_avg = grey_avg.astype(np.float32)
                else:
                    cv2.accumulateWeighted(grey_img, grey_avg, 0.8)

                ### contour of movements
                grey_tmp = cv2.convertScaleAbs(grey_avg)
                grey_diff = cv2.absdiff(grey_img, grey_tmp)
                grey_diff = cv2.Canny(grey_diff, 10, 15)
                wrect, rects = self.chk_contours(grey_diff, self.contour_threshold)
                
                if (self.cam_idx in self.parent.cam_idx) and (rects != []) and (self.m_wrectTh[0] < wrect[2]+wrect[3] < self.m_wrectTh[1]):
                # if this is a cam for watching subject and there's a meaningful movement
                    nmc += len(rects)
                    sumX = 0; sumY = 0
                    sum_dist_b_mc = 0
                    for ri in range(len(rects)):
                        _r = rects[ri]
                        _x = _r[0]+_r[2]/2; _y = _r[1]+_r[3]/2
                        cv2.circle(grey_img, (_x,_y), 5, 200, 2)
                        if ri > 0:
                            _pr = rects[ri-1]
                            _x2 = _pr[0]+_pr[2]/2; _y2 = _pr[1]+_pr[3]/2
                            cv2.line(grey_img, (_x,_y), (_x2,_y2), 200, 1)
                            sum_dist_b_mc += np.sqrt( abs(_x-_x2)**2 + abs(_y-_y2)**2 ) 
                        sumX += _x; sumY += _y
                        #cv2.rectangle(grey_img, (_r[0],_r[1]), (_r[0]+_r[2],_r[1]+_r[3]), 255, 1)
                    avgX = sumX/len(rects); avgY = sumY/len(rects)
                    cmcX.append(avgX); cmcY.append(avgY)
                    dist_b_mc.append(sum_dist_b_mc/len(rects))
                else: # there's no meaningful movement
                    pass 
                if time()-last_mov_log_time > 10: # every 10 seconds
                    ### record the movement data
                    f = open(movLog_fp, 'a')
                    if nmc > 0:
                        f.write( '%s, %i, %i, %i, %i\n'%(get_time_stamp(), nmc, int(np.average(dist_b_mc)), int(np.average(cmcX)), int(np.average(cmcY))) )
                    else:
                        f.write( '%s, 0, 0, 0, 0\n'%(get_time_stamp()) )
                    f.close()
                    nmc=0; dist_b_mc=[]; cmcX=[]; cmcY=[] # init
                    last_mov_log_time = time()
                            
            else: # chk_cam_view
                ### draw ROI lines
                for i in range(len(self.roi_pts)):
                    pt1 = self.roi_pts[(i-1)]
                    pt2 = self.roi_pts[i]
                    cv2.line(frame_arr, pt1, pt2, (0,0,255), 2)
            
            if flag_window == True:
                if flag_chk_cam_view == True: cv2.imshow("CATOS_CAM%.2i"%(self.cam_idx), frame_arr)
                else: cv2.imshow("CATOS_CAM%.2i"%(self.cam_idx), grey_img)
            cv2.waitKey(5)
            msg_src, msg_body, msg_details = chk_msg_q(self.msg_q) # listen to a message
            if msg_body == 'quit': break
            
        self.cap_cam.release()
        if flag_window == True: cv2.destroyWindow("CATOS_CAM%.2i"%(self.cam_idx))
        log_ = '%s, [%s], webcam %i stopped.\n'%(get_time_stamp(), mod_name, self.cam_idx)
        writeFile(self.parent.log_file_path, log_)

    # --------------------------------------------------

    def find_color(self, rect, inImage, HSV_min, HSV_max, bgColor=(0,0,0)):
    # Find a color(range: 'HSV_min' ~ 'HSV_max') in an area('rect') of an image('inImage')
    # 'bgcolor' is a background color of the masked image
    # 'rect' here is (x1,y1,x2,y2)
        tmp_grey_img = np.zeros( (inImage.shape[0], inImage.shape[1]) , dtype=np.uint8 )
        tmp_col_img = np.zeros( (inImage.shape[0], inImage.shape[1], 3), dtype=np.uint8 )
        HSV_img = np.zeros( (inImage.shape[0], inImage.shape[1], 3), dtype=np.uint8 )
        tmp_col_img[:,:,:] = bgColor
        tmp_col_img[ rect[1]:rect[3], rect[0]:rect[2], : ] = inImage[ rect[1]:rect[3], rect[0]:rect[2], : ].copy()
        tmp_col_img = self.preprocessing(tmp_col_img)
        cv2.cvtColor(tmp_col_img, cv2.COLOR_BGR2HSV, HSV_img)
        cv2.inRange(HSV_img, HSV_min, HSV_max, tmp_grey_img)
        return tmp_grey_img

    # --------------------------------------------------
    
    def preprocessing(self, inImage, param=[5,2,2]):
        inImage = cv2.GaussianBlur(inImage, (param[0],param[0]), 0)
        inImage = cv2.dilate(inImage, None, iterations=param[1])
        inImage = cv2.erode(inImage, None, iterations=param[2])
        return inImage

    # --------------------------------------------------

    def chk_contours(self, inImage, contour_threshold):
        contours, hierarchy = cv2.findContours(inImage, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        wrect = [-1,-1,-1,-1] # whole rect, bounding all the contours
        rects = [] # rects, bounding each contour piece
        for ci in xrange(len(contours)):
            #M = cv2.moments(contours[ci])
            br = cv2.boundingRect(contours[ci])
            if br[2] + br[3] > contour_threshold:
                if wrect[0] == -1 and wrect[1] == -1: wrect[0] = br[0]; wrect[1] = br[1]
                if wrect[2] == -1 and wrect[3] == -1: wrect[2] = br[0]; wrect[3] = br[1]
                if br[0] < wrect[0]: wrect[0] = br[0]
                if br[1] < wrect[1]: wrect[1] = br[1]
                if (br[0]+br[2]) > wrect[2]: wrect[2] = br[0]+br[2]
                if (br[1]+br[3]) > wrect[3]: wrect[3] = br[1]+br[3]
                rects.append(br)
        wrect[2] = wrect[2]-wrect[0]
        wrect[3] = wrect[3]-wrect[1]
        return tuple(wrect), rects
    
    # --------------------------------------------------
