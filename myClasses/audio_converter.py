# this script requires ffmpeg program to be installed
from os import remove, path
from pydub import AudioSegment


class Converter:

    @staticmethod
    def convert_mp3_to_wav(folder, source_file):
        sound = AudioSegment.from_mp3(folder + source_file)
        sound.export(folder + source_file.split('.')[0] + '.wav', format='wav')
        if path.exists(folder + source_file):
            remove(folder + source_file)
