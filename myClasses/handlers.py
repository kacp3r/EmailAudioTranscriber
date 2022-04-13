import email
import logging
import ssl
import os
import speech_recognition
import smtplib
import imaplib

from abc import ABC, abstractmethod
from imapclient import IMAPClient
from email import header
from datetime import datetime, timedelta

from myClasses.audio_recording import AudioRecording
from myClasses.audio_converter import Converter

from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger('thing')


# used by a few handlers
def convert_date_from_email_header_to_datetime(raw_email_date):
    raw_email_date = raw_email_date[5:25]
    # if the day is 1-9, the string will be one character shorter with a space at the end
    raw_email_date = raw_email_date.rstrip()
    email_datetime = datetime.strptime(raw_email_date, '%d %b %Y %H:%M:%S')
    return email_datetime


class Handler(ABC):

    @abstractmethod
    def set_next(self, handler):
        pass

    @abstractmethod
    def handle(self, request):
        pass


class AbstractHandler(Handler):

    def __init__(self):
        self._next_handler = None

    def set_next(self, handler):
        self._next_handler = handler
        return handler

    @abstractmethod
    def handle(self, request):
        if self._next_handler:
            return self._next_handler.handle(request)
        return None


class MessageGetter(AbstractHandler):
    def handle(self, request):
        try:
            list_of_emails = self.get_list_of_emails(request.get_email_address(),
                                                     request.get_email_password(),
                                                     request.get_imap_server(),
                                                     request.get_check_since_time())
        except Exception as e:
            logger.debug('Wystąpił błąd podczas ściągania wiadomosci z konta mailowego: ' + str(e))
            request.exception_occurred = True
            list_of_emails = None

        request.list_of_emails = list_of_emails

        if self._next_handler:
            return self._next_handler.handle(request)
        return None

    def get_list_of_emails(self, email_address, email_password, imap_server_address, cutoff_date):
        context = ssl.create_default_context()
        logger.debug('Próbuję ściągnąć wiadomości z serwera od tej daty: ' + str(cutoff_date))
        with IMAPClient(imap_server_address, ssl_context=context) as my_imap_server:
            my_imap_server.login(email_address, email_password)
            my_imap_server.select_folder('INBOX', readonly=True)

            imap_messages = my_imap_server.search('SINCE ' + cutoff_date.strftime('%d-%b-%Y'))
            email_messages = []
            for uid, message_data in my_imap_server.fetch(imap_messages, 'RFC822').items():
                email_message = email.message_from_bytes(message_data[b'RFC822'])
                email_messages.append(email_message)
            logger.debug('Udało się ściągnąć tyle wiadomości: ' + str(len(email_messages)))
            return email_messages


class EmailListFilter(AbstractHandler):
    def handle(self, request):
        if request.list_of_emails:
            filtered_list_of_emails = self.filter_list_of_emails(request.list_of_emails,
                                                                 request.get_check_since_time(),
                                                                 request.get_acceptable_from_email(),
                                                                 request.get_email_subject(),
                                                                 request.get_acceptable_attachment_types())
            request.list_of_emails = None
            request.filtered_list_of_emails = filtered_list_of_emails
        else:
            return super().handle(request)

        if self._next_handler:
            return self._next_handler.handle(request)
        else:
            return request

    def filter_list_of_emails(self, list_of_email_messages, cutoff_date, given_from_address, given_subject,
                              given_attachment_types):
        filtered_list = []
        logger.info('Filtruję listę emaili, na razie ma tyle: ' + str(len(list_of_email_messages)))
        logger.info('Odrzucę wiadomości starsze niż ta data: ' + str(cutoff_date))
        logger.info('Odrzucę wiadomości nie pochodzące z tego adresu: ' + str(given_from_address))
        logger.info('Odrzucę wiadomości nie zawierające tego w temacie: ' + str(given_subject))
        logger.info('Odrzucę wiadomości z załącznikami innych typów niż te: ' + str(given_attachment_types))
        for email_message in list_of_email_messages:
            email_date_found = email.header.make_header(email.header.decode_header(email_message.get('Date'))).__str__()
            email_date_datetime = convert_date_from_email_header_to_datetime(email_date_found)
            from_address = email.header.make_header(email.header.decode_header(email_message.get('From'))).__str__()
            from_address = from_address.split(' ')[0].replace('<', '').replace('>', '')
            email_subject = email.header.make_header(email.header.decode_header(email_message.get('Subject'))).__str__()

            if email_date_datetime < cutoff_date:
                continue

            if from_address:
                if from_address != given_from_address:
                    continue

            if given_subject:
                if not (email_subject.__contains__(given_subject)):
                    continue

            # check if the email has an attachment of one of the given types
            accepted_attachment_type = False
            for part in email_message.get_payload():
                if part.get_content_type() in given_attachment_types:
                    accepted_attachment_type = True
            if not accepted_attachment_type:
                continue

            filtered_list.append(email_message)

        logger.info('Przefiltrowałem listę emaili, teraz ma tyle: ' + str(len(filtered_list)))
        return filtered_list


class AudioAttachmentsExtractor(AbstractHandler):
    def handle(self, request):
        if request.filtered_list_of_emails:
            request.list_of_audio_recordings, request.date_of_last_processed_email = \
                                    self.extract_audio_attachments(request.filtered_list_of_emails,
                                                                   request.get_acceptable_attachment_types(),
                                                                   request.get_audio_directory())
            request.filtered_list_of_emails = None
            if self._next_handler:
                return self._next_handler.handle(request)
            else:
                return request
        else:
            return super().handle(request)

    def extract_audio_attachments(self, list_of_messages, acceptable_attachment_types, audio_directory):
        if not os.path.exists(audio_directory):
            os.mkdir(audio_directory)

        logger.info('Próbuję zapisać załączniki z wiadomości email')

        list_of_audio_recordings = []
        date_of_last_email_processed = None

        for message in list_of_messages:
            # first get the date from the header,
            # then record it in variable if it is newer than the date stored there
            # this date will be later used as the next cutoff date
            date_from_header = email.header.make_header(email.header.decode_header(message.get('Date'))).__str__()
            date_from_header_datetime = convert_date_from_email_header_to_datetime(date_from_header)
            if date_of_last_email_processed is None:
                date_of_last_email_processed = date_from_header_datetime
            elif date_from_header_datetime > date_of_last_email_processed:
                date_of_last_email_processed = date_from_header_datetime

            for part in message.get_payload():
                if part.get_content_type() in acceptable_attachment_types:
                    attachment_name = part.get_filename()
                    open(audio_directory + attachment_name, 'wb') \
                        .write(part.get_payload(decode=True))
                    list_of_audio_recordings.append(AudioRecording(attachment_name,
                                                                   date_from_header_datetime))
        logger.info('Zapisałem tyle załączników: ' + str(len(list_of_audio_recordings)))
        logger.info('Data i godzina ostatniego otwartego emaila to: ' + str(date_of_last_email_processed))
        return list_of_audio_recordings, date_of_last_email_processed
    pass


class Mp3ToWavConverter(AbstractHandler):

    def handle(self, request):
        if request.list_of_audio_recordings:
            self.convert_list_of_recordings_to_mp3(request.list_of_audio_recordings,
                                                   request.get_audio_directory())
            request.files_converted_to_wav = True
            if self._next_handler:
                return self._next_handler.handle(request)
            else:
                return request
        else:
            return super().handle(request)

    def convert_list_of_recordings_to_mp3(self, list_of_recordings, audio_directory):
        for recording in list_of_recordings:
            self.convert_mp3_to_wav_file(recording, audio_directory)

    def convert_mp3_to_wav_file(self, my_audio_recording, audio_directory):
        logger.info('Próbuję przekonwertować plik z mp3 na wav: ' + my_audio_recording.audio_file_name)
        try:
            Converter.convert_mp3_to_wav(audio_directory, my_audio_recording.audio_file_name)
            my_audio_recording.audio_file_name = my_audio_recording.audio_file_name.replace('mp3', 'wav')
            logger.info('Udało się przekonwertować')
        except Exception as e:
            logger.info('Coś poszło nie tak przy próbie konwersji pliku z mp3 na wav, '
                        'upewnij się, że masz zaisntalowany program ffmpeg '
                        'i że jest on dodany do zmiennej systemowej PATH. Błąd: '
                        + str(e))
            raise Exception()


class Transcriber(AbstractHandler):

    def handle(self, request):
        self.error_flag = False
        if request.files_converted_to_wav:
            self.transcribe_list_of_recordings(request.list_of_audio_recordings,
                                               request.get_audio_directory(),
                                               request.get_transcripts_directory())
            if self.error_flag:
                request.exception_occurred = True
            if self._next_handler:
                return self._next_handler.handle(request)
            else:
                return request
        else:
            return super().handle(request)

    def transcribe_list_of_recordings(self, list_of_recordings, audio_directory, transcripts_directory):
        for recording in list_of_recordings:
            self.transcribe_recording(recording, audio_directory, transcripts_directory)

    def transcribe_recording(self, given_audio_recording, audio_directory, transcripts_directory):
        my_audio_file = audio_directory + given_audio_recording.audio_file_name
        my_recognizer = speech_recognition.Recognizer()

        logger.info('Próbuje dostać transkrypcję pliku audio od google speech')

        with speech_recognition.AudioFile(my_audio_file) as my_source:
            audio = my_recognizer.record(my_source)

            try:
                my_text = my_recognizer.recognize_google(audio, language='pl-PL')
                logger.info('Transkrypcja: ' + my_text)

            except speech_recognition.UnknownValueError:
                my_text = 'Google Speech nie zrozumiał nagrania'
                logger.info(my_text)

            except speech_recognition.RequestError as e:
                my_text = 'Nie udało się otrzymać odpowiedzi od Google Speech; {0}'.format(e)
                self.error_flag = True
                logger.info(my_text)

        my_text_file = given_audio_recording.audio_file_name.split('.')[0] + '.txt'
        path_to_my_text_file = transcripts_directory + my_text_file
        with open(path_to_my_text_file, 'w', encoding='utf-8') as file:
            file.write('\n' + my_text)
        given_audio_recording.transcript_file_name = my_text_file
        logger.info('Zapisałem transkrypcję do pliku ' + path_to_my_text_file)


class KeywordFinder(AbstractHandler):

    def handle(self, request):
        if request.files_converted_to_wav:
            for recording in request.list_of_audio_recordings:
                self.look_for_keywords_in_transcript(recording,
                                                     request.get_keywords(),
                                                     request.get_transcripts_directory())

            if self._next_handler:
                return self._next_handler.handle(request)
            else:
                return request
        else:
            return super().handle(request)

    def look_for_keywords_in_transcript(self, given_recording, keywords, transcripts_directory):
        keywords_found_in_text = []

        with open(transcripts_directory + given_recording.transcript_file_name, 'r', encoding='utf-8') \
                as transcript:
            transcript_content = transcript.read()
            for keyword in keywords:
                if keyword in transcript_content:
                    keywords_found_in_text.append(keyword)
        given_recording.keywords_found_in_transcript = keywords_found_in_text


class EmailSender(AbstractHandler):

    def handle(self, request):
        if request.files_converted_to_wav:
            for recording in request.list_of_audio_recordings:
                audio_file_name = recording.audio_file_name
                logger.info(f'Próbuję wysłać email z plikiem: {audio_file_name}')
                try:
                    self.send_email_notification(request.get_email_address(),
                                                 request.get_email_password(),
                                                 request.get_smtp_server(),
                                                 request.get_smtp_port(),
                                                 request.get_email_to_notify(),
                                                 recording.audio_file_name,
                                                 request.get_audio_directory(),
                                                 request.get_transcripts_directory(),
                                                 recording.transcript_file_name,
                                                 recording.keywords_found_in_transcript)
                    request.time_of_last_processed_recording = recording.get_time_of_recording_as_string()
                    logger.info(f'Udało się wysłać email z plikiem {audio_file_name}')
                except Exception as e:
                    logger.info(f'Nie udało się wysłać emaila z plikiem {audio_file_name}, error: {str(e)}')
                    request.exception_occurred = True

            if self._next_handler:
                return self._next_handler.handle(request)
            else:
                return request
        else:
            return super().handle(request)

    def send_email_notification(self,
                                sender_email,
                                password,
                                smtp_server,
                                smtp_port,
                                receiver_email,
                                audio_file_name,
                                audio_directory,
                                transcripts_directory,
                                transcript_file='',
                                keywords_found=''):

        subject = audio_file_name.replace('szpieg.wav', '') + ' ' + str(keywords_found) \
            .replace('[', '') \
            .replace(']', '') \
            .replace('\'', '')
        body = ''

        if keywords_found:
            body += (str(keywords_found)
                     .replace('[', '')
                     .replace(']', '')
                     .replace('\'', '')
                     ) + '\n'

        if transcript_file:
            with open(transcripts_directory + transcript_file, 'r', encoding='utf-8') as my_file:
                body += '\n' + my_file.read()

        # Create a multipart message and set headers
        message = MIMEMultipart()
        message['From'] = sender_email
        message['To'] = receiver_email[0]
        message['Subject'] = subject
        message['Bcc'] = str(receiver_email).replace('[', '').replace(']', '')  # Recommended for mass emails

        # Add body to email
        message.attach(MIMEText(body, 'plain'))
        path_to_audio_file = audio_directory + audio_file_name

        # Open file in binary mode
        with open(path_to_audio_file, 'rb') as attachment:
            # Add file as application/octet-stream
            # Email client can usually download this automatically as attachment
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(attachment.read())

        # Encode file in ASCII characters to send by email
        encoders.encode_base64(part)

        # Add header as key/value pair to attachment part
        part.add_header(
            'Content-Disposition',
            f'attachment; filename= {audio_file_name}',
        )

        # Add attachment to message and convert message to string
        message.attach(part)
        text = message.as_string()

        # Log in to server using secure context and send email
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(smtp_server, smtp_port, context=context) as server:
            server.login(sender_email, password)
            server.sendmail(sender_email, receiver_email, text)


class Cleaner(AbstractHandler):
    # deletes old files and messages from server

    DAYS_TO_WAIT = 7

    def handle(self, request):
        # this one should always happen, regardless of the previous steps

        logger.info(f'Próbuję skasować pliki starsze niż {self.DAYS_TO_WAIT} dni')
        try:
            self.delete_old_files(self.DAYS_TO_WAIT, request.get_audio_directory())
            self.delete_old_files(self.DAYS_TO_WAIT, request.get_transcripts_directory())
            self.delete_old_files(self.DAYS_TO_WAIT, request.get_logs_directory())
            logger.info(f'Skasowałem pliki starsze niż {self.DAYS_TO_WAIT} dni')
        except Exception as e:
            logger.info(f'Nie udało się skasować starych plików. Błąd: {str(e)}')
            request.exception_occurred = True

        logger.info(f'Próbuje skasować wiadomości email starsze niż {self.DAYS_TO_WAIT} dni')
        try:
            self.delete_old_emails_from_server(request.get_email_address(),
                                               request.get_email_password(),
                                               request.get_imap_server(),
                                               request.get_check_since_time(),
                                               self.DAYS_TO_WAIT)
            logger.info(f'Udało się skasować wiadomości starsze niż {self.DAYS_TO_WAIT} dni')
        except Exception as e:
            logger.info(f'Nie udało się skasować wiadomości starsze niż {self.DAYS_TO_WAIT} dni')
            request.exception_occurred = True

        if self._next_handler:
            return self._next_handler.handle(request)
        else:
            return request

    def delete_old_files(self, days_to_wait, directory):
        cutoff_date = datetime.now() - timedelta(days=days_to_wait)

        if not os.path.exists(directory):
            return

        for file_name in os.listdir(directory):
            creation_time = os.stat(directory + file_name).st_ctime
            creation_time = datetime.fromtimestamp(creation_time)
            if creation_time < cutoff_date:
                os.remove(directory + file_name)

    def delete_old_emails_from_server(self,
                                      email_address,
                                      password,
                                      imap_server,
                                      current_date,
                                      days_in_past):
        # I know I started using IMAPClient, but I need imaplib for this one

        # emails before this date will be deleted
        cutoff_date = current_date - timedelta(days=days_in_past)
        cutoff_date = cutoff_date.strftime('%d-%b-%Y')

        imap_client = imaplib.IMAP4_SSL(imap_server)
        imap_client.login(email_address, password)

        imap_client.select('INBOX')

        status, messages = imap_client.search(None, 'BEFORE "' + cutoff_date + '"')

        # convert list of messages to list of email IDs
        messages = messages[0].split(b' ')

        for mail in messages:
            # if there are no mails, the list will be a single empty bit,
            # and it will cause an error in store command
            if mail == b'':
                continue
            # _, msg = imap_client.fetch(mail, '(RFC822)')
            imap_client.store(mail, '+FLAGS', '\\Deleted')

        imap_client.expunge()
        imap_client.close()
        imap_client.logout()


class PreviousErrorChecker(AbstractHandler):
    # checks if the program finished correctly last time
    # if not, then it sends an email containing the two last log files

    def handle(self, request):
        # this one runs regardless of what happened before
        logger.info('Sprawdzam, czy ostatnim razem program zakończył się pomyślnie')
        program_finished_correctly_last_time = self.check_if_program_finished_correctly_last_time(
            request.get_latest_log_file_name(),
            request.get_logs_directory()
        )

        if program_finished_correctly_last_time:
            logger.info('Program zakończył się pomyślnie ostatnim razem')
        else:
            logger.info('Program nie zakończył się poprawnie ostatnim razem, spróbuję wysłać logi.')
            try:
                self.send_two_last_logs(request.get_email_address(),
                                        request.get_email_password(),
                                        request.get_smtp_server(),
                                        request.get_smtp_port(),
                                        request.get_email_to_notify(),
                                        request.get_logs_directory())
                logger.info('Wysłałem dwa ostatnie logi')
            except Exception as e:
                logger.info(f'Nie udało się wysłać logów, error: {str(e)}')
                request.exception_occurred = True

        if self._next_handler:
            return self._next_handler.handle(request)
        else:
            return request

    def check_if_program_finished_correctly_last_time(self, log_file_name, logs_directory):
        this_log_file = log_file_name
        previous_log_file = (logs_directory +
                             (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d') +
                             '.log')

        # file_content = ''
        with open(this_log_file, 'r') as log_file:
            file_content = log_file.read()
        pass
        # if this log file is empty, then take the previous one
        if not file_content:
            # if previous file doesn't exist, then this is the first run, and everything's ok
            if not os.path.isfile(previous_log_file):
                return True
            with open(previous_log_file, 'r') as log_file:
                file_content = log_file.read()

        # look for: ----- Pomyślnie zakończyłem pracę programu
        # unless you find this first: ----- Rozpocząłem działanie programu
        # we have to ignore the first occurrence of "----- Rozpocząłem"
        # because it was added by the currently running instance
        # hmm

        counter = 0
        for line in reversed(file_content.split('\n')):
            if '----- Pomyślnie zakończyłem pracę programu' in line:
                return True
            if '----- Rozpocząłem działanie programu' in line:
                if counter == 1:
                    return False
                else:
                    counter = 1

    def send_two_last_logs(self,
                           sender_email,
                           password,
                           smtp_server,
                           smtp_port,
                           receiver_email,
                           logs_directory):
        subject = 'Coś poszło nie tak'
        body = ('Coś poszło nie tak przy ostatnim uruchomieniu programu. \n'
                'Możesz sprawdzić, co poszło nie tak w załączonych logach.')

        # Create a multipart message and set headers
        message = MIMEMultipart()
        message['From'] = sender_email
        message['To'] = receiver_email[0]
        message['Subject'] = subject
        message['Bcc'] = str(receiver_email).replace('[', '').replace(']', '')  # Recommended for mass emails

        # Add body to email
        message.attach(MIMEText(body, 'plain'))

        log_file_name = ''
        second_log_file_name = ''

        files = os.listdir(logs_directory)
        paths = [os.path.join(logs_directory, basename) for basename in files]
        path_to_log_file = max(paths, key=os.path.getctime)
        log_file_name = path_to_log_file.split('/')[-1]

        file_paths_and_names = [(path_to_log_file, log_file_name)]

        paths.remove(path_to_log_file)
        if paths:
            path_to_second_log_file = max(paths, key=os.path.getctime)
            second_log_file_name = path_to_second_log_file.split('/')[-1]
            file_paths_and_names = [(path_to_log_file, log_file_name),
                                    (path_to_second_log_file, second_log_file_name)]

        text = ''
        for (mypath, file_name) in file_paths_and_names:
            # Open file in binary mode
            with open(mypath, 'rb') as attachment:
                # Add file as application/octet-stream
                # Email client can usually download this automatically as attachment
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(attachment.read())

            # Encode file in ASCII characters to send by email
            encoders.encode_base64(part)

            # Add header as key/value pair to attachment part
            part.add_header(
                'Content-Disposition',
                f'attachment; filename= {file_name},'
            )

            # Add attachment to message and convert message to string
            message.attach(part)
            text = message.as_string()

        # Log in to server using secure context and send email
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(smtp_server, smtp_port, context=context) as server:
            server.login(sender_email, password)
            server.sendmail(sender_email, receiver_email, text)


class TimeUpdater(AbstractHandler):
    # update the time in the settings file to the last processed email

    def handle(self, request):
        if request.time_of_last_processed_recording:
            request.update_time_in_settings(request.time_of_last_processed_recording)
        logger.info('Zaktualizowałem czas ostatniego nagrania w ustawieniach na: '
                    + str(request.time_of_last_processed_recording))
        if self._next_handler:
            return self._next_handler.handle(request)
        else:
            return request


class Closer(AbstractHandler):
    # just put the closing line into the log
    # this line is used earlier, for checking if the previous run finished correctly

    def handle(self, request):
        if not request.exception_occurred:
            logger.info('----- Pomyślnie zakończyłem pracę programu')
        else:
            logger.info('XXXXX Zakończyłem pracę programu, ale po drodze wystąpił błąd')

        if self._next_handler:
            return self._next_handler.handle(request)
        else:
            return request

