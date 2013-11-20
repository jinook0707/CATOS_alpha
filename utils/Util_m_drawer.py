'''
Util_m_drawer.py
This is for generating a JPG file per a MP4 file.
The generated JPG file shows the movement pattern
appeared thoughout the MP4 file. 
(Movement summary of the movie file)
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
import os, sys
from glob import glob
from math import sqrt
from copy import copy

import cv ###

FLAG_DISPLAY_JPG = False

#------------------------------------------------------------------------------------

class M_drawer:
    def __init__(self, target_path):
        self.target_path = target_path
        if FLAG_DISPLAY_JPG == True: cv.NamedWindow('disp', cv.CV_WINDOW_NORMAL)
        if FLAG_DISPLAY_JPG == True: cv.MoveWindow('disp', 50, 50)
        self.total_nFrames = 0

    #---------------------------------------------------------------------------------
    def get_FG_rect_value(self, inString):
    # get overall foreground rect value
        if inString.strip() == '(-1/ -1/ -1/ -1)': return -1
        else:
            b_rect = inString.replace("(","").replace(")","").split("/")
            b_rect = (int(b_rect[0])*2, int(b_rect[1])*2, int(b_rect[2])*2, int(b_rect[3])*2)       
            return b_rect

    #---------------------------------------------------------------------------------

    def get_FGB_center_pt(self, fgb_pts):
    # get each foreground blob's center point
        number_of_pts = len(fgb_pts)
        x = 0; y = 0
        for i in range(number_of_pts):
            x += fgb_pts[i][0]
            y += fgb_pts[i][1]
        x = x/number_of_pts
        y = y/number_of_pts
        return [x,y]

    #---------------------------------------------------------------------------------

    def get_img_from_video(self, cap_vf):
        frames = []
        nFrames = int(cv.GetCaptureProperty(cap_vf, cv.CV_CAP_PROP_FRAME_COUNT))
        fps = int(cv.GetCaptureProperty(cap_vf, cv.CV_CAP_PROP_FPS))
        self.total_nFrames += nFrames
        for i in xrange(nFrames):
            frame = cv.QueryFrame(cap_vf)
            if i == 0 or i == nFrames/2: # store first, middle frame
                frames.append(cv.CloneImage(frame))
            ### try to store the last frame, but if it fails, ignore it.
            if i == nFrames-1:
                try: frames.append(cv.CloneImage(frame))
                except: pass

        ### Add differences between the middle-first & last-first onto the first frame  
        diff_img0 = cv.CreateImage(cv.GetSize(frames[0]), 8, 3)
        diff_img1 = cv.CreateImage(cv.GetSize(frames[0]), 8, 3)
        cv.AbsDiff(frames[0], frames[1], diff_img0)
        if len(frames) > 2: cv.AbsDiff(frames[0], frames[2], diff_img1)
        cv.Add(diff_img0, frames[0], frames[0])
        if len(frames) > 2: cv.Add(diff_img1, frames[0], frames[0])     

        return frames[0]

    #---------------------------------------------------------------------------------

    def run(self):
        #first_img_path = os.path.join(self.target_path, '_first_color_img_cID00.jpg')
        #first_img = cv.LoadImage(first_img_path)
        d_color1 = (0, 0, 0)
        d_color2 = (255, 255, 255)
        cat_margin = 30 # due to dilate function, etc
        font = cv.InitFont(cv.CV_FONT_HERSHEY_PLAIN, 1, 1, 0, 3, 8)
        dr_cnt = 0 # counter for drawing

        for f in glob(os.path.join(self.target_path, '*_MR.csv')): # open all the MovementRecord files
            mr_f = open(f, 'r')
            mr_f_lines = mr_f.readlines()

            jpg_file = f.replace(".csv", ".jpg")
            if not os.path.isfile(jpg_file): # jpg file doesn't exist
                video_file = f.replace("_MR.csv", ".mp4")
                if os.path.isfile(video_file): # video file exist
                    cap_vf = cv.CaptureFromFile(video_file)
                    img_from_video = self.get_img_from_video(cap_vf)                    
                    last_center_pt = (-1,-1)
                    last_center_pt_b = (-1,-1)
                    last_center_pt_white = (-1,-1)
                    last_center_pt_black = (-1,-1)
                    lines_cnt = len(mr_f_lines)
                    for i in range(2, lines_cnt):
                        items = mr_f_lines[i].split(",")
                        if len(items) > 1:
                            number_of_blobs = int(items[4])
                            #d_color_e_dec = 255-(float(i)/lines_cnt*255)
                            d_color_e_inc = float(i)/lines_cnt*255
                            d_color = (d_color_e_inc, d_color_e_inc, d_color_e_inc)

                            '''
                            ### Drawing for movement rects
                            b_rect = items[0].replace("(","").replace(")","").split("/")
                            b_rect = (int(b_rect[0]), int(b_rect[1]), int(b_rect[2]), int(b_rect[3]))
                            d_color_e = 255-(float(i+1)/lines_cnt*255)
                            d_color = (d_color_e, d_color_e, d_color_e)
                            cv.Rectangle(img_from_video, (b_rect[0],b_rect[1]), (b_rect[0]+b_rect[2],b_rect[1]+b_rect[3]), d_color1, 1)
                            center_pt = items[1].split("/")
                            center_pt = (int(center_pt[0]), int(center_pt[1]))
                            cv.Circle(img_from_video, center_pt, 3, d_color, 1)
                            if last_center_pt != (-1,-1): cv.Line(img_from_video, last_center_pt, center_pt, d_color, 1)
                            last_center_pt = tuple(center_pt)
                            '''

                            '''
                            ### rect bounding all the foreground features
                            b_rect = self.get_FG_rect_value(items[2])
                            #cv.Rectangle(img_from_video, (b_rect[0],b_rect[1]), (b_rect[0]+b_rect[2],b_rect[1]+b_rect[3]), d_color, 1)
                            if b_rect != -1:
                                ### Drawing the center point of the movement whole bounding rect (and the connecting lines between the center points.)
                                center_pt = items[3].split("/")
                                center_pt = (int(center_pt[0])*2, int(center_pt[1])*2)
                                cv.Circle(img_from_video, center_pt, 5, d_color, 2)
                                if last_center_pt_b != (-1,-1): cv.Line(img_from_video, last_center_pt_b, center_pt, d_color, 1)
                                last_center_pt_b = tuple(center_pt)
                            '''

                            ### rects for each foreground blob
                            fB_grouped_pts = eval(items[8].replace("/", ","))
                            if fB_grouped_pts != []:
                                for fB_idx in range(len(fB_grouped_pts)):
                                    fgb_pts = fB_grouped_pts[fB_idx]
                                    if fgb_pts != '[]': fgb_center_pt = self.get_FGB_center_pt(fgb_pts)
                                    fgb_center_pt = (fgb_center_pt[0]*2, fgb_center_pt[1]*2)
                                    cv.Circle(img_from_video, fgb_center_pt, 3, d_color, 2)
                                    if fB_idx > 0: 
                                        cv.Line(img_from_video, last_fgb_center_pt, fgb_center_pt, d_color, 1)
                                    last_fgb_center_pt = copy(fgb_center_pt)
                            
                            ### Drawing the center point of the whitish blob
                            if items[7].strip() == '-1/-1': wbpt = (-1,-1)
                            else:
                                wbpt = items[7].split("/") # white blob center point
                                wbpt = (int(wbpt[0])*2, int(wbpt[1])*2)
                            if wbpt != (-1, -1):
                                # draw a rectangle at the center of white blob(s)
                                cv.Rectangle(img_from_video, (wbpt[0]-2,wbpt[1]-2), (wbpt[0]+2,wbpt[1]+2), (0,0,125), 1)

                            if FLAG_DISPLAY_JPG == True: cv.ShowImage('disp', img_from_video)

                    mr_img_path = f.replace(".csv", ".jpg")
                    cv.SaveImage(mr_img_path, img_from_video)
                    dr_cnt += 1
                    print "An image, %s, is generated."%mr_img_path
                    mr_f.close()
                else:
                # Video file doesn't exist (means it wasn't generated due to lack of enough JPEG files)
                # Usually it's meaningless very short record. (or no record at all)
                    mr_f.close()
                    os.remove(f) # remove the MR-csv file

        for f in glob(os.path.join(self.target_path, '*.log')):
            log_f = open(f, 'a')
            log_f.write("\n* Total number of frames of movie files: %i\n"%(self.total_nFrames))
            log_f.close()
            
        print "Number of images generated: %i"%(dr_cnt)
        print "Image drawing process is complete."

#------------------------------------------------------------------------------------

if __name__ == '__main__':
    path = os.getcwd()
    input_path = ''
    if len(sys.argv) > 1:
        for i in range(1, len(sys.argv)): input_path += sys.argv[i] + ' '
        input_path = input_path.strip()
    else: input_path = 'output'
    path = os.path.join(path, input_path)
    mDrawer = M_drawer(path)
    mDrawer.run()
