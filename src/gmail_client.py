from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from src.models import Email, EmailOld, OAuthCredential


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
        return self.fetch_emails_full_sync()

    def fetch_email_partial_sync(self):
        pass
        # get history_id from most recent email
        # use history.list to get more recent emails
        # https://developers.google.com/gmail/api/guides/sync#partial_synchronization

    def fetch_emails_full_sync(self):
        results = self.gmail_service.users().messages().list(userId='me').execute()
        print(f"results keys: {results.keys()}")
        nextPageToken = results.get("nextPageToken")
        messages = results.get('messages', [])

        new_emails = []
        existing_email_ids = set([eml.gmail_id for eml in Email.query.all()]) # TODO: add filtering for user
        while (len(messages) > 0):
            print(f"page size of {len(messages)}")
            for message in messages:
                if message['id'] in existing_email_ids:
                    continue

                raw_email = self.get_message(message['id'])
                email = Email.from_raw_gmail(raw_email)
                new_emails.append(email)
            if nextPageToken is None:
                break

            results = self.gmail_service.users().messages().list(userId='me', pageToken=nextPageToken).execute()
            print(f"results keys: {results.keys()}")
            nextPageToken = results.get("nextPageToken", None)
            messages = results.get('messages', [])

        return new_emails

    @classmethod
    def authorization_url(cls):
        return flow.authorization_url()

    @classmethod
    def credentials_from_oauth_redirect(cls, request_url, user_id):
        flow.fetch_token(authorization_response=request_url)
        creds = OAuthCredential.create_or_update(user_id, flow.credentials)
        return creds.to_credentials()
