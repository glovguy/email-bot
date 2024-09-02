from .oauth_credential import OAuthCredential
from .gmail_client import GmailClient
from .email import Email
from flask import Blueprint, request, redirect, session
from src.models import User

email_bp = Blueprint('email', __name__, url_prefix='/email')

@email_bp.route('/')
def emails_home():
    credential = OAuthCredential.query.filter_by(user_id=1).first()
    if credential is None:
        authorization_url, state = GmailClient.authorization_url()
        session['state'] = state
        return redirect(authorization_url)
    
    return emails_display()


def emails_display():
    messages = Email.query.all() # TODO: scope by user

    email_info = []
    for msg in messages:
        subject = msg.subject
        sender = msg.from_email_address
        email_info.append(f"Subject: {subject}, From: {sender}<br>{msg.snippet}")
    
    return "<div>" + "</div><hr><div>".join(email_info) + "</div>"


@email_bp.route('/oauth2callback')
def oauth2callback():
    GmailClient.credentials_from_oauth_redirect(request.url, current_user().id)
    print("Credentials successfully created")
    return redirect('/emails')


# TODO: move to a top-level module
def current_user():
    return User.query.first()