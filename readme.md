This is a script I wrote for a client who had audio files on his email account, and needed to transcribe them via Google Speech API.

It downloads files from the given email account, sends them to Google API for transcription, checks for keywords in the transcription, and sends the audio file and the transcription to a given email address.

Free Google API access was sufficient for client's needs.

Audio file attachments have to have unique names (e.g. date and time).

A single run of the script processes all emails from a given date and then closes. The program was compiled into an executable with PyInstaller and set up on the client's machine to run every few minutes via CRON.

Settings.ini file must be filled out before running the script. On first run, the user will be asked to put in the password to the email account containing the emails with audio files.

I refactored the project to the Chain of Responsibility pattern for my own training purposes.