import ssl

from salt import salt
from cryptography.fernet import Fernet
from os import path
from imapclient import IMAPClient


PASSWORD_FILE_NAME = 'calc.txt'


def get_new_key():
    print(Fernet.generate_key())


def get_password(path_to_directory, email, server):
    print(path_to_directory + PASSWORD_FILE_NAME)
    i = 0
    fail = False
    while i < 5:
        if not path.exists(path_to_directory + PASSWORD_FILE_NAME) or fail:
            password = input('Podaj hasło do maila ' + email + ': ')
            encrypted_password = Fernet(salt).encrypt(str.encode(password))
            with open(path_to_directory + PASSWORD_FILE_NAME, 'wb') as file:
                file.write(encrypted_password)
            if verify_password(server, email, password):
                return password
        else:
            with open(path_to_directory + PASSWORD_FILE_NAME, 'r') as file:
                encrypted_password = file.read()
                password_bytes = Fernet(salt).decrypt(str.encode(encrypted_password))
                password = bytes.decode(password_bytes)
            if verify_password(server, email, password):
                return password
            else:
                fail = True
        i += 1
    print('Nie udało się wprowadzić hasła. Spróbuj uruchomić program ponownie.')


def verify_password(server, email, password):
    context = ssl.create_default_context()
    try:
        with IMAPClient(server, ssl_context=context) as my_imap_server:
            my_imap_server.login(email, password)
            return True
    except Exception as e:
        print(e)
        return False
    pass
