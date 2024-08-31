from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from src.models import EmailOld, OAuthCredential

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
    
    def fetch_unread_emails(self):
            results = self.gmail_service.users().messages().list(userId='me', q='is:unread').execute()
            messages = results.get('messages', [])
            
            for message in messages:
                email = self.get_message(message['id'])
                # Create an Email entry in the database using the email data
                
                # Mark the email as "read" on the server
                self.gmail_service.users().messages().modify(userId='me', id=message['id'], body={'removeLabelIds': ['UNREAD']}).execute()
    
    def create_email_entry(self, email_uid):
        try:
            raw_email = self.server.fetch(email_uid, ['BODY[]'])
            # ['id', 'threadId', 'labelIds', 'snippet', 'payload', 'sizeEstimate', 'historyId', 'internalDate']
            return EmailOld.from_raw_oauth_email(raw_email[email_uid], email_uid)
        except Exception as e:
            print("error creating email entry for uid: ", email_uid, " error: ", e)
            # If something goes wrong, mark the email as unread again
            self.server.remove_flags(email_uid, ['\\Seen'])
    
    @classmethod
    def authorization_url(cls):
        return flow.authorization_url()
    
    @classmethod
    def credentials_from_oauth_redirect(cls, request_url, user_id):
        flow.fetch_token(authorization_response=request_url)
        creds = OAuthCredential.create_or_update(user_id, flow.credentials)
        return creds.to_credentials()
