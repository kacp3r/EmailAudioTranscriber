import logging
import sys
import os
from datetime import datetime

import myClasses


def get_this_directory():
    # the directory is recognized differently when you are running a python script,
    # and differently when you are running an executable baked with pyinstaller
    directory = None
    if getattr(sys, 'frozen', False):
        directory = os.path.dirname(sys.executable)
    elif __file__:
        directory = os.path.dirname(__file__)
    return directory


if __name__ == '__main__':
    # this has to be here, otherwise it will find the directory in the class where the logger is defined
    initializer = myClasses.Initializer(get_this_directory())
    logging.getLogger().disabled = True
    logging.basicConfig(level=logging.INFO,
                        filename=initializer.logs_directory + datetime.now().strftime('%Y%m%d') + '.log',
                        filemode='a',
                        format='%(asctime)s - %(levelname)s - %(message)s',
                        datefmt='%d-%m-%Y %H:%M:%S')

    logger = logging.getLogger('main')
    logger.info('----- Rozpocząłem działanie programu')

    request = myClasses.Request(initializer)

    message_getter              = myClasses.handlers.MessageGetter()
    email_list_filter           = myClasses.handlers.EmailListFilter()
    audio_attachments_extractor = myClasses.handlers.AudioAttachmentsExtractor()
    mp3_to_wav_converter        = myClasses.handlers.Mp3ToWavConverter()
    transcriber                 = myClasses.handlers.Transcriber()
    keyword_finder              = myClasses.handlers.KeywordFinder()
    email_sender                = myClasses.handlers.EmailSender()
    cleaner                     = myClasses.handlers.Cleaner()
    previous_error_checker      = myClasses.handlers.PreviousErrorChecker()
    time_updater                = myClasses.handlers.TimeUpdater()
    closer                      = myClasses.handlers.Closer()

    message_getter.\
        set_next(email_list_filter).\
        set_next(audio_attachments_extractor).\
        set_next(mp3_to_wav_converter).\
        set_next(transcriber).\
        set_next(keyword_finder).\
        set_next(email_sender).\
        set_next(cleaner).\
        set_next(previous_error_checker).\
        set_next(time_updater).\
        set_next(closer)

    result = message_getter.handle(request)
