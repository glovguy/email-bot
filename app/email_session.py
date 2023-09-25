from imapclient import IMAPClient
from decouple import config

class EmailSession:
    def __init__(self):
        self.server = None 

    def connect(self):
        """Connects to the email server using IMAP."""
        HOST = config('EMAIL_HOST', default='imap.gmail.com')
        PORT = config('EMAIL_PORT', default=993, cast=int)
        EMAIL_ADDRESS = config('EMAIL_ADDRESS')
        EMAIL_PASSWORD = config('EMAIL_PASSWORD')

        self.server = IMAPClient(HOST, port=PORT, use_uid=True, ssl=True)
        self.server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        print("Successfully connected to the email server.")
        return self.server

    def disconnect(self):
        """Disconnect from the server."""
        if self.server:
            self.server.logout()
            self.server.shutdown()
            print("Successfully disconnected from the email server.")
