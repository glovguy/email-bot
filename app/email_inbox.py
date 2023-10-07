from imapclient import IMAPClient
from decouple import config
from models import Email, User
from authorization import Authorization

UNREAD = ['UNSEEN']

class EmailInbox:
    def __init__(self):
        self.email_session = EmailSession()

    def fetch_unread_emails(self):
        """Fetch unread emails from the inbox."""
        server = self.email_session.connect()
        try:
            server.select_folder('INBOX')
            email_ids = server.search(UNREAD)
            if not email_ids:
                return []

            raw_emails = server.fetch(email_ids, ['BODY[]'])
            emails = [Email.from_raw_email(raw_emails[email_uid], email_uid) for email_uid in raw_emails]

            return emails

        finally:
            self.email_session.disconnect()

    def send_response(self, recipient_email, subject, message):
        return self.email_session.send_email(recipient_email, subject, message)


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
            print("Successfully disconnected from the email server.")
