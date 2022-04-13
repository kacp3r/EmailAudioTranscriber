class AudioRecording:
    audio_file_name = ''
    transcript_file_name = ''
    keywords_found_in_transcript = []
    email_header_date = None

    def __init__(self, audio_file_name, date_from_header):
        self.audio_file_name = audio_file_name
        self.email_header_date = date_from_header

    def get_time_of_recording_as_string(self):
        # returns string with YYYY-MM-DD HH:MM:SS, taken from name of file
        if not self.audio_file_name:
            raise AttributeError('This recording has no file name assigned')

        time_from_file_name = self.audio_file_name.replace(' szpieg.wav', '')
        time_with_colons = time_from_file_name.split(' ')[0] \
                           + ' ' \
                           + time_from_file_name.split(' ')[1].replace('-', ':')

        return time_with_colons
