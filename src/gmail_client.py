from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


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
    
    @classmethod
    def authorization_url(cls):
        return flow.authorization_url()
    
    @classmethod
    def credentials_from_oauth_redirect(cls, request_url):
        flow.fetch_token(authorization_response=request_url)
        return flow.credentials
