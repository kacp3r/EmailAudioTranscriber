import logging
import myClasses.password

from myClasses.settings import Settings

logger = logging.getLogger(__name__)


class Request:

    # in init pass initializer
    def __init__(self, initializer):
        self.exception_occurred = False

        self._initializer = initializer,

        # I have absolutely no idea why self.initializer is a tuple containing only the initializer
        self._initializer = self._initializer[0]

        self._settings = Settings(self._initializer.settings_file)
        self._email_password = myClasses.password.get_password(self._initializer.bundle_directory,
                                                               self._settings.email_address,
                                                               self._settings.imap_server)

        self.list_of_emails                     = None
        self.filtered_list_of_emails            = None
        self.list_of_audio_recordings           = None
        self.date_of_last_processed_email       = None
        self.files_converted_to_wav             = False
        self.time_of_last_processed_recording   = None

    def get_audio_directory(self):
        return self._initializer.audio_directory

    def get_transcripts_directory(self):
        return self._initializer.transcripts_directory

    def get_logs_directory(self):
        return self._initializer.logs_directory

    def get_latest_log_file_name(self):
        return self._initializer.get_latest_log_file_name()

    def get_email_address(self):
        return self._settings.email_address

    def get_email_password(self):
        return self._email_password

    def get_imap_server(self):
        return self._settings.imap_server

    def get_check_since_time(self):
        return self._settings.check_since

    def get_acceptable_from_email(self):
        return self._settings.acceptable_from_email

    def get_email_subject(self):
        return self._settings.email_subject_should_contain

    def get_acceptable_attachment_types(self):
        return self._settings.acceptable_attachment_types

    def get_keywords(self):
        return self._settings.keywords

    def get_smtp_server(self):
        return self._settings.smtp_server

    def get_smtp_port(self):
        return self._settings.smtp_port

    def get_email_to_notify(self):
        return self._settings.emails_to_notify

    def update_time_in_settings(self, new_time):
        self._settings.update_time(new_time)
