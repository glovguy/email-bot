from decouple import config
from flask import Flask, request, redirect, session
from flask_apscheduler import APScheduler
from flask_migrate import Migrate
from src.gmail_client import GmailClient
from src.skills.ponder_wittgenstein_skill import PonderWittgensteinSkill
from src.skills.process_email_skill import ProcessEmailSkill
from src.skills.get_to_know_you_skill import GetToKnowYouSkill
from src.models import User
from src.skills.zettelkasten_skill import LOCAL_DOCS_FOLDER, FileManagementService
import src.views.skills
import os
from src.models import *


def create_app():
    app = Flask(__name__)
    app.secret_key = os.urandom(24)
    app.config['SQLALCHEMY_DATABASE_URI'] = POSTGRES_DATABASE_URL.render_as_string(hide_password=False)
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)

    Migrate(app, db)

    @app.teardown_appcontext
    def shutdown_session(exception=None):
        db_session.remove()

    return [app, db]

[app, db] = create_app()


@app.route('/')
def home():
    credential = OAuthCredential.query.filter_by(user_id=1).first()
    if credential is None:
        authorization_url, state = GmailClient.authorization_url()
        session['state'] = state
        return redirect(authorization_url)

    return redirect("/emails")


@app.route('/oauth2callback')
def oauth2callback():
    GmailClient.credentials_from_oauth_redirect(request.url, current_user().id)
    print("Credentials successfully created")
    return redirect('/emails')


@app.route('/emails')
def emails_display():
    credential = OAuthCredential.query.filter_by(user_id=1).first()
    gmail_client = GmailClient(credential.to_credentials())
    messages = gmail_client.messages()

    email_info = []
    for message in messages:
        msg = gmail_client.get_message(message["id"])
        email_data = msg['payload']['headers']
        subject = next((header['value'] for header in email_data if header['name'] == 'Subject'), 'No Subject')
        sender = next((header['value'] for header in email_data if header['name'] == 'From'), 'Unknown')
        email_info.append(f"Subject: {subject}, From: {sender}")
    
    return "<br>".join(email_info)


app.add_url_rule('/skills', view_func=src.views.skills.index)


def current_user():
    return User.query.filter_by(name=config('ME')).first()

def check_mailbox():
    print("checking mailbox...")
    credential = OAuthCredential.query.filter_by(user_id=1).first()
    gmail_client = GmailClient(credential.to_credentials())

    new_emails = gmail_client.fetch_emails()
    print(len(new_emails), " new emails received")

    # unprocessed_emails = Email.query.filter_by(is_processed=False).all()
    # print(len(unprocessed_emails), " unprocessed emails.")
    # for email in unprocessed_emails:
    #     print("Processing email: ", email)
    #     ProcessEmailSkill.process(email)

def ask_get_to_know_you():
    # GetToKnowYouSkill.ask_get_to_know_you(me, initial_doc)
    GetToKnowYouSkill.ask_get_to_know_you_latest_zettelkasten_notes(current_user())

def ponder_wittgenstein():
    PonderWittgensteinSkill.ponder_wittgenstein(current_user())


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


if __name__ == '__main__':
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'  # For development only
    # FileManagementService.sync_documents_from_folder(LOCAL_DOCS_FOLDER)
    # ponder_wittgenstein()
    # ask_get_to_know_you()
    # scheduler = APScheduler()
    # scheduler.init_app(app)
    # scheduler.start()
    init_db()
    with app.app_context():
        check_mailbox()
        app.run(port=5000, debug=True, use_reloader=True)
