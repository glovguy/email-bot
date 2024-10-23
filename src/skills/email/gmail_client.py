from typing import List, Dict, Any
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
from email.mime.multipart import MIMEMultipart


flow = Flow.from_client_secrets_file(
    'client_secret.apps.googleusercontent.com.json',
    scopes=[
        'https://www.googleapis.com/auth/gmail.readonly', 
        'https://www.googleapis.com/auth/gmail.modify', 
        'https://www.googleapis.com/auth/gmail.send'
    ],
    redirect_uri='http://localhost:5000/oauth2callback',
)
BOT_EMAIL_ADDRESS = config("EMAIL_ADDRESS")

class GmailClient():
    def __init__(self, user_id=None) -> None:
        self.credentials = db_session.query(OAuthCredential).filter_by(user_id=user_id).first().to_credentials()
        self.user_id = user_id
        self.gmail_service = build('gmail', 'v1', credentials=self.credentials)

    def messages(self):
        results = self.gmail_service.users().messages().list(userId='me', maxResults=10).execute()
        return results.get('messages', [])

    def get_message(self, email_id: str) -> Dict[str, Any]:
        return self.gmail_service.users().messages().get(userId='me', id=email_id).execute()

    def get_thread(self, thread_id: str) -> Dict[str, Any]:
        return self.gmail_service.users().threads().get(userId='me', id=thread_id).execute()['messages']
    
    def get_email_content(self, email: Email) -> str:
        gmail_message = self.get_message(email.gmail_id)
        if "parts" not in gmail_message["payload"]:
            return self.part_as_email_content(gmail_message["payload"])

        messages = []
        for part in gmail_message["payload"]["parts"]:
            msg = self.part_as_email_content(part)
            if msg is not None:
                messages.append(msg)
        return "\n\n---\n\n".join(messages)

    def email_as_chat_entry(self, email: Email) -> List[Dict[str, str]]:
        role = "assistant" if email.from_email_address == BOT_EMAIL_ADDRESS else "user"
        gmail_message = self.get_message(email.gmail_id)
        if "parts" not in gmail_message["payload"]:
            return self.part_as_email_content(gmail_message["payload"])

        messages = []
        for part in gmail_message["payload"]["parts"]:
            msg = self.part_as_email_content(part)
            if msg is not None:
                messages.append({ 
                    "role": role,
                    "content": msg 
                })
        return messages

    def thread_as_chat_history(self, thread_id: str) -> List[Dict[str, str]]:
        emails_in_thread = Email.query.filter_by(thread_id=thread_id).order_by(Email.received_at).all()
        messages = []
        for email in emails_in_thread:
            msg = self.get_email_content(email)
            if msg is not None:
                messages.append({ 
                    "role": "assistant" if email.from_email_address == BOT_EMAIL_ADDRESS else "user",
                    "content": msg 
                })
        return messages

    def part_as_email_content(self, part: Dict[str, Any]) -> str:
        if part["mimeType"] == "text/plain" and "body" in part:
            email_content = base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8")

            # Extract only the reply content
            parsed_email = EmailReplyParser.read(email_content)
            actual_message = parsed_email.reply
            return actual_message

    def fetch_emails(self) -> List[Email]:
        return self.fetch_emails_partial_sync()

    def fetch_emails_partial_sync(self) -> List[Email]:
        latest_email = db_session.query(Email).order_by(Email.received_at.desc()).first()
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

    def fetch_emails_full_sync(self, update_existing_records=False) -> List[Email]:
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

    def send_message(self, enqueued_message: EnqueuedMessage) -> Dict[str, str]:
        message = MIMEMultipart()
        message['to'] = enqueued_message.recipient_email
        message['subject'] = enqueued_message.subject

        # Convert content to HTML to preserve formatting
        html_content = f"<span style='white-space: pre-wrap; word-wrap: break-word;'>{enqueued_message.content}</span>"
        message.attach(MIMEText(html_content, 'html'))

        if enqueued_message.parent_message_id:
            message['In-Reply-To'] = enqueued_message.parent_message_id
            message['References'] = enqueued_message.parent_message_id

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
