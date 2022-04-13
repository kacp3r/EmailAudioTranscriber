from configparser import ConfigParser
from datetime import datetime, timedelta
from datetime import timedelta


class Settings:
    settings_file = ''

    email_address = ''
    imap_server = ''
    imap_port = 0
    smtp_server = None
    smtp_port = None

    acceptable_from_email = ''
    email_subject_should_contain = ''
    acceptable_attachment_types = []

    check_since = ''

    keywords = []

    emails_to_notify = []

    config = ConfigParser()

    MAX_DAYS_TO_CHECK = 1

    def __init__(self, settings_file):
        self.settings_file = settings_file

        config = ConfigParser()
        config.read(settings_file)

        self.email_address = config.get('email_account', 'email_address')
        self.imap_server = config.get('email_account', 'imap_server')
        self.imap_port = int(config.get('email_account', 'imap_port'))
        self.smtp_server = config.get('email_account', 'smtp_server')
        self.smtp_port = int(config.get('email_account', 'smtp_port'))

        self.acceptable_from_email = config.get('email_filters', 'acceptable_from_email')
        self.email_subject_should_contain = config.get('email_filters', 'email_subject_should_contain')
        self.acceptable_attachment_types = config.get('email_filters', 'acceptable_attachment_types').split('\n')

        self.check_since = datetime.strptime(config.get('time', 'check_since'), '%Y-%m-%d %H:%M:%S')
        if self.check_since < datetime.today() - timedelta(days=self.MAX_DAYS_TO_CHECK):
            self.check_since = datetime.today() - timedelta(days=self.MAX_DAYS_TO_CHECK)

        self.keywords = config.get('keywords', 'list').split('\n')

        self.emails_to_notify = config.get('emails_to_notify', 'list').split('\n')

    def update_time(self, given_date):
        config = ConfigParser()
        config.read(self.settings_file)
        given_date_datetime = datetime.strptime(given_date, '%Y-%m-%d %H:%M:%S')
        self.check_since = given_date_datetime
        config['time']['check_since'] = (given_date_datetime + timedelta(0, 1)).strftime('%Y-%m-%d %H:%M:%S')
        with open(self.settings_file, 'w') as file:
            config.write(file)
