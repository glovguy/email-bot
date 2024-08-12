from decouple import config
from flask import Flask, request, redirect, session
from flask_apscheduler import APScheduler
from src.email_inbox import EmailInbox
from src.gmail_client import GmailClient
from src.skills.ponder_wittgenstein_skill import PonderWittgensteinSkill
from src.skills.process_email_skill import ProcessEmailSkill
from src.skills.get_to_know_you_skill import GetToKnowYouSkill
from src.models import Email, User
from src.skills.zettelkasten_skill import LOCAL_DOCS_FOLDER, FileManagementService
import src.views.skills
import os


me = User.query.filter_by(name=config('ME')).first()

def check_mailbox():
    inbox = EmailInbox()
    emails = inbox.fetch_unread_emails()
    print(len(emails), " emails received")
    
    unprocessed_emails = Email.query.filter_by(is_processed=0).all()
    print(len(unprocessed_emails), " unprocessed emails.")
    for email in unprocessed_emails:
        print("Processing email: ", email)
        ProcessEmailSkill.process(email)

def ask_get_to_know_you():
    # GetToKnowYouSkill.ask_get_to_know_you(me, initial_doc)
    GetToKnowYouSkill.ask_get_to_know_you_latest_zettelkasten_notes(me)

def ponder_wittgenstein():
    PonderWittgensteinSkill.ponder_wittgenstein(me)

app = Flask(__name__)
app.secret_key = os.urandom(24)

app.config['JOBS'] = [
    {
        'id': 'check_and_process_unread_emails',
        'func': 'app:check_mailbox',
        'trigger': 'interval',
        'hours': 1
    },
    {
        'id': 'ponder_wittgenstein',
        'func': 'app:ponder_wittgenstein',
        'trigger': 'interval',
        'days': 2
    },
    {
        'id': 'ask_get_to_know_you',
        'func': 'app:ask_get_to_know_you',
        'trigger': 'interval',
        'days': 1
    }
]

@app.route('/')
def home():
    authorization_url, state = GmailClient.authorization_url()
    session['state'] = state
    return redirect(authorization_url)

@app.route('/oauth2callback')
def oauth2callback():
    credentials = GmailClient.credentials_from_oauth_redirect(request.url)
    print("\n\ncredentials:\n\n",credentials,"\n\n")
    
    gmail_client = GmailClient(credentials)

    messages = gmail_client.messages()
    gmail_service = gmail_client.gmail_service
    
    # Process and display email information
    email_info = []
    for message in messages:
        msg = gmail_service.users().messages().get(userId='me', id=message['id']).execute()
        email_data = msg['payload']['headers']
        subject = next((header['value'] for header in email_data if header['name'] == 'Subject'), 'No Subject')
        sender = next((header['value'] for header in email_data if header['name'] == 'From'), 'Unknown')
        email_info.append(f"Subject: {subject}, From: {sender}")
    
    return "<br>".join(email_info)

app.add_url_rule('/skills', view_func=src.views.skills.index)

if __name__ == '__main__':
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'  # For development only
    # check_mailbox()
    # FileManagementService.sync_documents_from_folder(LOCAL_DOCS_FOLDER)
    # ponder_wittgenstein()
    # ask_get_to_know_you()
    # scheduler = APScheduler()
    # scheduler.init_app(app)
    # scheduler.start()
    app.run(port=5000, debug=True, use_reloader=True)
