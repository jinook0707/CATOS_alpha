'''
Util_MoveF.py
This is for moving files in 'output' folder
into different sub-folders of 'archive' folder
depending on the file-type.
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
from glob import glob
from shutil import move

from modules.common_module import get_time_stamp


def run(folder_name = '', folder_path = ''):
    if folder_path == '':
        folder_name = raw_input('Name the folder in the output-folder to move data-files.: ')
        folder_path = os.path.join('archive', folder_name)

    if folder_name.strip() == '':
        print "ERROR:: The folder-name is empty."
        return

    while os.path.isdir(folder_path):
        print "The folder name, < %s >, already exists in 'archive' folder"%folder_name
        folder_name += 'x'
        folder_path = os.path.join('archive', folder_name)
        print "'x' was added at the end of the folder-name. < %s >"%folder_name
    os.mkdir(folder_path)

    mp4_folder_path = os.path.join(folder_path, 'mp4')
    csv_folder_path = os.path.join(folder_path, 'csv')
    jpg_folder_path = os.path.join(folder_path, 'jpg')
    wav_folder_path = os.path.join(folder_path, 'wav')
    os.mkdir(mp4_folder_path)
    print "mp4 folder created"
    os.mkdir(csv_folder_path)
    print "csv folder created"
    os.mkdir(jpg_folder_path)
    print "jpg folder created"
    os.mkdir(wav_folder_path)
    print "wav folder created"

    for f in glob(os.path.join('output', '*.log')):
        move(f, folder_path) # moving the log file; there's only log file currently(2012.Nov)
        result_csv_file = f.replace(".log", ".csv")
        move(result_csv_file, folder_path) # moving the result csv file
    print "Log file & result-csv file are moved."

    for f in glob(os.path.join('output', '*.mp4')):
        move(f, mp4_folder_path)
    print "*.mp4 files are moved."

    for f in glob(os.path.join('output', '*.csv')):
        move(f, csv_folder_path)
    print "*.csv files(movement recrods) are moved."

    for f in glob(os.path.join('output', '*.jpg')):
        move(f, jpg_folder_path)
    print "*.jpg files(movement recrods) are moved."

    for f in glob(os.path.join('output', '*.wav')):
        move(f, wav_folder_path)
    print "*.wav files are moved."


if __name__ == '__main__':
    run()


