from .oauth_credential import OAuthCredential
from .gmail_client import GmailClient
from flask import Blueprint, request, redirect, session
from src.user import User


email_bp = Blueprint('email', __name__, url_prefix='/email')

# TODO: move to a top-level module
def current_user():
    return User.query.first()


@email_bp.route('/')
def emails_home():
    credential = OAuthCredential.query.filter_by(user_id=1).first()
    if credential is None:
        authorization_url, state = GmailClient.authorization_url()
        session['state'] = state
        return redirect(authorization_url)
    
    return "<h1>Emails authenticated</h1>"


@email_bp.route('/oauth2callback')
def oauth2callback():
    GmailClient.credentials_from_oauth_redirect(request.url, current_user().id)
    print("Credentials successfully created")
    return redirect('/email')
