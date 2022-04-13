import logging
import sys
import os

from os import path

logger = logging.getLogger(__name__)


class Initializer:
    AUDIO_DIRECTORY = 'audio/'
    TRANSCRIPTS_DIRECTORY = 'transcripts/'
    LOGS_DIRECTORY = 'logs/'
    SETTINGS_FILE = 'settings.ini'

    def __init__(self, bundle_directory):
        self.bundle_directory = bundle_directory + '/'

        self.audio_directory = path.join(self.bundle_directory, self.AUDIO_DIRECTORY)
        self.transcripts_directory = path.join(self.bundle_directory, self.TRANSCRIPTS_DIRECTORY)
        self.logs_directory = path.join(self.bundle_directory, self.LOGS_DIRECTORY)
        self.settings_file = path.join(self.bundle_directory, self.SETTINGS_FILE)

        self.create_directory_if_it_doesnt_exist(self.audio_directory)
        self.create_directory_if_it_doesnt_exist(self.transcripts_directory)
        self.create_directory_if_it_doesnt_exist(self.logs_directory)

    def create_directory_if_it_doesnt_exist(self, directory):
        if not path.exists(directory):
            os.mkdir(directory)

    def find_latest_log_file(self, logs_directory):
        # it finds the latest log file created
        files = os.listdir(logs_directory)
        paths = [path.join(logs_directory, basename) for basename in files]
        path_to_log_file = max(paths, key=path.getctime)
        return path_to_log_file

    def get_latest_log_file_name(self):
        # it finds the latest log file created
        files = os.listdir(self.logs_directory)
        paths = [path.join(self.logs_directory, basename) for basename in files]
        path_to_log_file = max(paths, key=path.getctime)
        log_file_name = path_to_log_file.split('/')[-1]
        return path_to_log_file
