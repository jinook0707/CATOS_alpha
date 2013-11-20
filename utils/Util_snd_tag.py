'''
Util_snd_tag.py
This is for changing filename of recorded wave files.
Changed filename will include a tag showing what type
of sound was recorded.

This script assumes HTK (Hidden-Markov Toolkit) from
'http://htk.eng.cam.ac.uk/' is already installed.
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

import subprocess
from os import getcwd, path, remove, rename
from glob import glob

class WaveFileRecognizer:
    def __init__(self, path):
        self.output_path = path

    def run(self):
        try:
            for wf in glob(path.join(self.output_path, "*.wav")):
                command = ['HVite', '-T', '1', 
                            '-H', 'utils/HTK_files/models.hmm', '-C', 'utils/HTK_files/config', 
                            '-w', 'utils/HTK_files/grammar.lat', 'utils/HTK_files/dict', 'utils/HTK_files/models.list', 
                            wf]
                p = subprocess.Popen(command, stderr=subprocess.STDOUT, stdout=subprocess.PIPE)
                stdout = p.communicate()[0]
                sound_tag = stdout.split('\n')[-2].split(" ")[0]
                rec_file = wf.replace('.wav', '.rec')
                remove(rec_file)
                ### add sound-tag at the end of the file name to indicate what type of sound as it was recognized
                new_fn = wf.replace(".wav", "_%s.wav"%sound_tag)
                rename(wf, new_fn)
                print "[ %s ] was tagged as %s-sound"%(wf, sound_tag)
            return True
        except Exception as e:
            print e
            return False

if __name__ == '__main__':
    output_path = path.join(getcwd(), "output")
    WFR_inst = WaveFileRecognizer(output_path)
    WFR_inst.run()
