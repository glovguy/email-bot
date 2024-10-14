from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from .email import Email
from .oauth_credential import OAuthCredential
from .enqueued_message import EnqueuedMessage
from src.models import db_session
from email.mime.text import MIMEText
import base64
from email_reply_parser import EmailReplyParser
from decouple import config


flow = Flow.from_client_secrets_file(
    'client_secret.apps.googleusercontent.com.json',
    scopes=[
        'https://www.googleapis.com/auth/gmail.readonly', 
        'https://www.googleapis.com/auth/gmail.modify', 
        'https://www.googleapis.com/auth/gmail.send'
    ],
    redirect_uri='http://localhost:5000/oauth2callback',
)

class GmailClient():
    def __init__(self, user_id=None) -> None:
        self.credentials = db_session.query(OAuthCredential).filter_by(user_id=user_id).first().to_credentials()
        self.user_id = user_id
        self.gmail_service = build('gmail', 'v1', credentials=self.credentials)

    def messages(self):
        results = self.gmail_service.users().messages().list(userId='me', maxResults=10).execute()
        return results.get('messages', [])

    def get_message(self, email_id):
        return self.gmail_service.users().messages().get(userId='me', id=email_id).execute()

    def get_thread(self, thread_id):
        return self.gmail_service.users().threads().get(userId='me', id=thread_id).execute()['messages']

    def thread_as_chat_history(self, thread_id):
        emails_in_thread = Email.query.filter_by(thread_id=thread_id).order_by(Email.id).all()
        messages = []
        bot_email_address = config("EMAIL_ADDRESS")
        for email in emails_in_thread:
            role = "assistant" if email.from_email_address == bot_email_address else "user"
            message = self.get_message(email.gmail_id)
            if "parts" in message["payload"]:
                for part in message["payload"]["parts"]:
                    msg = self.part_as_message(part, role)
                    if msg is not None:
                        messages.append(msg)
            else:
                msg = self.part_as_message(message["payload"], role)
                if msg is not None:
                    messages.append(msg)
        messages
        return messages

    def part_as_message(self, part, role):
        if part["mimeType"] == "text/plain" and "body" in part:
            email_content = base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8")

            # Extract only the reply content
            parsed_email = EmailReplyParser.read(email_content)
            actual_message = parsed_email.reply
            return {"role": role, "content": actual_message}

    def fetch_emails(self):
        return self.fetch_emails_partial_sync()

    def fetch_emails_partial_sync(self):
        latest_email = Email.query.order_by(Email.id.desc()).first()
        history_id = latest_email.history_id
        if history_id is None:
            return self.fetch_emails_full_sync()

        try:
            # https://developers.google.com/gmail/api/guides/sync#partial_synchronization
            results = self.gmail_service.users().history().list(userId="me", startHistoryId=latest_email.history_id).execute()
            nextPageToken = results.get("nextPageToken", None)
            messages = results.get('messages', [])

            new_emails = []
            updated_emails = []
            while (len(messages) > 0):
                print(f"page size of {len(messages)}")
                for message in messages:
                    raw_email = self.get_message(message['id'])

                    existing_email = Email.query.filter_by(gmail_id=message["id"]).first()
                    if existing_email is not None:
                        existing_email.update_from_raw_gmail(raw_email)
                        updated_emails.append(existing_email)
                        continue

                    email = Email.from_raw_gmail(raw_email, self.user_id)
                    new_emails.append(email)
                if nextPageToken is None:
                    break

                results = self.gmail_service.users().history().list(userId="me", startHistoryId=latest_email.history_id, pageToken=nextPageToken).execute()
                nextPageToken = results.get("nextPageToken", None)
                messages = results.get('messages', [])

            print(f"Updated {len(updated_emails)} emails")
            print(f"Created {len(new_emails)} new emails")
        except HttpError:
            print("Unable to do partial sync. Running full sync")
            self.fetch_emails_full_sync(update_existing_records=False)

    def fetch_emails_full_sync(self, update_existing_records=False):
        results = self.gmail_service.users().messages().list(userId='me').execute()
        nextPageToken = results.get("nextPageToken")
        messages = results.get('messages', [])

        new_emails = []
        updated_emails = []
        while (len(messages) > 0):
            print(f"page size of {len(messages)}")
            for msg_info in messages:
                existing_email = Email.query.filter_by(gmail_id=msg_info["id"]).first()
                if existing_email is not None and not update_existing_records:
                    continue

                raw_email = self.get_message(msg_info['id'])
                if existing_email is not None:
                    existing_email.update_from_raw_gmail(raw_email, self.user_id)
                    updated_emails.append(existing_email)
                    continue

                email = Email.from_raw_gmail(raw_email, self.user_id)
                new_emails.append(email)

            if nextPageToken is None:
                break

            results = self.gmail_service.users().messages().list(userId='me', pageToken=nextPageToken).execute()
            nextPageToken = results.get("nextPageToken", None)
            messages = results.get('messages', [])

        print(f"Updated {len(updated_emails)} emails")
        print(f"Created {len(new_emails)} new emails")
        return new_emails

    def send_message(self, enqueued_message: EnqueuedMessage):
        message = MIMEText(enqueued_message.content)
        message['to'] = enqueued_message.recipient_email
        message['subject'] = enqueued_message.subject
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
        return self.gmail_service.users().messages().send(userId='me', body={"raw": raw_message}).execute()

    @classmethod
    def authorization_url(cls):
        return flow.authorization_url()

    @classmethod
    def credentials_from_oauth_redirect(cls, request_url, user_id):
        flow.fetch_token(authorization_response=request_url)
        creds = OAuthCredential.create_or_update(user_id, flow.credentials)
        return creds.to_credentials()
