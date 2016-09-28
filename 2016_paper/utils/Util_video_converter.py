'''
Util_video_converter.py
This generates MP4 movie file from captured JPG files through webcam
during a session using 'ffmpeg' command tool.
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

import os, subprocess
from glob import glob
from shutil import rmtree
import modules.error_handler_module as eh

#------------------------------------------------------------------------------------
class VideoConverter:
    def __init__(self):
        self.output_path = os.path.join(os.getcwd(), "output")

    #--------------------------------------------------------------------------------

    def run(self):
        time_stamps = []
        cIDs = []
        avg_fps = []
        for log_file in glob(os.path.join(self.output_path, "*.log")):
            fh = open(log_file, 'r')
            log_lines = fh.readlines()
            for line in log_lines:
                items = line.split(",")
                if len(items) > 1 and items[1].strip().startswith('Start a video-recording'):
                    time_stamps.append(items[0].strip())
                    cIDs.append(items[1].split(".")[0].strip()[-1])
                if line.startswith('The average FPS'):
                    avg_fps.append(items[1].strip())

        def movie_generation_loop():
            logs = []
            for i in range(len(time_stamps)):
                print "Executing ffmpeg command. Time-stamp:%s. Please wait.."%time_stamps[i]
                output_file_path, flag_result = self.generate_movie(time_stamps[i], cIDs[i], avg_fps[i])
                if flag_result: msg = "File, '%s', is generated."%output_file_path
                else: msg = "Movie file generation with the time-stamp, %s, failed."%time_stamps[i]
                logs.append(msg)
                print "-------------------------"
                print "Progress: %i/%i"%(i+1, len(time_stamps))
                print "-------------------------"
            print "Movie file generation is completed."
            print "-------------------------"
            print "Result ::"
            for i in range(len(logs)): print logs[i]

        chk_value = self.chk_lengths(time_stamps, avg_fps, cIDs)

        if chk_value == 'same':
            movie_generation_loop()
        elif chk_value == 'fewer_timestamps':
            ### append the average value of average_FPSs for missing FPS values
            diff = len(time_stamps) - len(avg_fps)
            avg_fps_val = 0
            for i in range(len(avg_fps)): avg_fps_val += int(avg_fps[i])
            if len(avg_fps) == 0 : avg_fps_val = 8
            else: avg_fps_val = avg_fps_val / len(avg_fps)
            for i in range(diff): avg_fps.append(str(avg_fps_val))
            # generate the movie
            movie_generation_loop()
        elif chk_value == 'different':
            eh.AOException("ERROR:: Lengths of the timestamps and the average FPS don't match.\nLength of TimeStamps: %i, Length of Average FPS: %i, Length of cIDs: %i"%(len(time_stamps), len(avg_fps), len(cIDs)))

    #--------------------------------------------------------------------------------

    def chk_lengths(self, time_stamps, avg_fps, cIDs):
        if not len(time_stamps) == len(avg_fps) == len(cIDs):
            if len(time_stamps) == len(cIDs) and len(avg_fps) < len(time_stamps):
                return "fewer_timestamps"
            else:
                return "different"
        else:
            return "same"               

    #--------------------------------------------------------------------------------

    def generate_movie(self, time_stamp, cID, avg_fps):
        output_file_name = "%s_cID%.2i.%s"%(time_stamp, int(cID), "mp4")        
        output_file_path = os.path.join(self.output_path, output_file_name)
        tmp_file = time_stamp + "_%05d.jpg"
        tmp_folder = os.path.join(self.output_path, time_stamp)
        flag_no_folder = True
        if not os.path.isdir(tmp_folder): # folder doesn't exist
            for i in range(4): # assumes multiple cameras can be up to 4 cameras
                tmp_folder += "x" # when a movement gets captures on multiple cameras, there could be foldernames with 'x's
                if os.path.isdir(tmp_folder): # if the folder exist
                    flag_no_folder = False
                    break
        else:
            flag_no_folder = False

        result = False
        if flag_no_folder:
            print "Temporary folder doesn't exist with the timestamp, %s"%time_stamp
        else:
            if len([file for file in glob(os.path.join(tmp_folder,"*.jpg"))]) > 1:
            # number of jpeg files in the temp folder is not only one file
                tmp_file = os.path.join(tmp_folder, tmp_file)
                command = ['ffmpeg', '-r', str(avg_fps), '-i', tmp_file, '-vcodec', 'libx264', output_file_path]
                try:
                    #print command
                    p = subprocess.Popen(command, stderr=subprocess.STDOUT, stdout=subprocess.PIPE)
                    stdout = p.communicate()[0]
                    print stdout
                    rmtree(tmp_folder) # delete the temporary folder
                    result = True
                except:
                    pass
            else: # if there's no jpeg or only one jpeg file
                rmtree(tmp_folder)

        return output_file_path, result

#------------------------------------------------------------------------------------

if __name__ == '__main__':
    ui = raw_input("This will go through all the log files in the output folder and try to generate movie files(mp4).\nProceed? (Y/N)")
    if ui.upper() == 'Y':
        vc = VideoConverter()
        vc.run()
