from imapclient import IMAPClient
from decouple import config
from email.mime.text import MIMEText
import smtplib
from src.models import Email

UNREAD = ['UNSEEN']
EMAIL_ADDRESS = config('EMAIL_ADDRESS')

class EmailInbox:
    def __init__(self):
        self.email_session = EmailSession()

    def fetch_unread_emails(self):
        """Fetch unread emails from the inbox."""
        self.server = self.email_session.connect()
        try:
            self.server.select_folder('INBOX')
            email_uids = self.server.search(UNREAD)
            print("Email uids: ", email_uids)
            if not email_uids:
                return []

            # raw_emails = self.server.fetch(email_uids, ['BODY[]'])
            # emails = [Email.from_raw_email(raw_emails[email_uid], email_uid) for email_uid in raw_emails]
            emails = []
            for email_id in email_uids:
                newEmail = self.create_email_entry(email_id)
                if newEmail is not None:
                    emails.append(newEmail)

            return emails

        finally:
            self.email_session.disconnect()

    def create_email_entry(self, email_uid):
        try:
            raw_email = self.server.fetch(email_uid, ['BODY[]'])
            return Email.from_raw_email(raw_email[email_uid], email_uid)
        except Exception as e:
            # If something goes wrong, mark the email as unread again
            print("error creating email entry for uid: ", email_uid, " error: ", e)
            self.server.remove_flags(email_uid, ['\\Seen'])

    def send_response(self, email, message):
        return self.send_email(email.sender, "Re: " + email.subject, message)
    
    def send_email(self, recipient, subject, body):
        """Send an email to the specified recipient."""
        msg = MIMEText(body)
        msg['From'] = EMAIL_ADDRESS
        msg['To'] = recipient
        msg['Subject'] = subject

        with self.email_session.connect_smtp() as server:
            server.sendmail(EMAIL_ADDRESS, [recipient], msg.as_string())
        
        print(f"Sent email to {recipient} with subject '{subject}'")


class EmailSession:
    def __init__(self):
        self.server = None
        self.smtp_server = None

    def connect(self):
        """Connects to the email server using IMAP."""
        HOST = config('EMAIL_HOST', default='imap.gmail.com')
        PORT = config('EMAIL_PORT', default=993, cast=int)
        EMAIL_PASSWORD = config('EMAIL_PASSWORD')

        self.server = IMAPClient(HOST, port=PORT, use_uid=True, ssl=True)
        self.server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        print("Successfully connected to the IMAP email server.")
        return self.server
    
    def connect_smtp(self):
        """Connects to the SMTP email server."""
        SMTP_HOST = config('SMTP_HOST', default='smtp.gmail.com')
        SMTP_PORT = config('SMTP_PORT', default=587, cast=int)  # Default port for TLS encryption
        EMAIL_ADDRESS = config('EMAIL_ADDRESS')
        EMAIL_PASSWORD = config('EMAIL_PASSWORD')

        self.smtp_server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
        self.smtp_server.starttls()  # Upgrade the connection to secure encrypted SSL/TLS
        self.smtp_server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        print("Successfully connected to the SMTP email server.")
        return self.smtp_server

    def disconnect(self):
        """Disconnect from the server."""
        if self.server:
            self.server.logout()
            print("Successfully disconnected from the IMAP email server.")

        if self.smtp_server:
            self.smtp_server.quit()
            print("Successfully disconnected from the SMTP email server.")