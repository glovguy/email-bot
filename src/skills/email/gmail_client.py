from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from .email import Email
from .oauth_credential import OAuthCredential


flow = Flow.from_client_secrets_file(
    'client_secret.apps.googleusercontent.com.json',
    scopes=['https://www.googleapis.com/auth/gmail.readonly', 'https://www.googleapis.com/auth/gmail.modify'],
    redirect_uri='http://localhost:5000/oauth2callback',
)

class GmailClient():
    def __init__(self, credentials) -> None:
        self.credentials = credentials
        self.gmail_service = build('gmail', 'v1', credentials=credentials)

    def messages(self):
        results = self.gmail_service.users().messages().list(userId='me', maxResults=10).execute()
        return results.get('messages', [])

    def get_message(self, email_id):
        return self.gmail_service.users().messages().get(userId='me', id=email_id).execute()

    def fetch_emails(self):
        return self.fetch_email_partial_sync()

    def fetch_email_partial_sync(self):
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

                    email = Email.from_raw_gmail(raw_email)
                    new_emails.append(email)
                if nextPageToken is None:
                    break

                results = self.gmail_service.users().history().list(userId="me", startHistoryId=latest_email.history_id, pageToken=nextPageToken).execute()
                nextPageToken = results.get("nextPageToken", None)
                messages = results.get('messages', [])
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
                    existing_email.update_from_raw_gmail(raw_email)
                    updated_emails.append(existing_email)
                    continue

                email = Email.from_raw_gmail(raw_email)
                new_emails.append(email)

            if nextPageToken is None:
                break

            results = self.gmail_service.users().messages().list(userId='me', pageToken=nextPageToken).execute()
            nextPageToken = results.get("nextPageToken", None)
            messages = results.get('messages', [])

        print(f"Updated {len(updated_emails)} emails")
        print(f"Created {len(new_emails)} new emails")
        return new_emails

    @classmethod
    def authorization_url(cls):
        return flow.authorization_url()

    @classmethod
    def credentials_from_oauth_redirect(cls, request_url, user_id):
        flow.fetch_token(authorization_response=request_url)
        creds = OAuthCredential.create_or_update(user_id, flow.credentials)
        return creds.to_credentials()
