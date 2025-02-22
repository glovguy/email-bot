from src.models import db_session, User
from .oauth_credential import OAuthCredential
from .gmail_client import GmailClient
from .email import Email
from .enqueued_message import EnqueuedMessage
from .message_queue import MessageQueue
from .email_event_bus import EmailEventBus
from .views import email_bp
from .hello_world_test import enqueue_test_message

def check_mailbox():
    print("checking mailbox...")
    users_with_credentials = db_session.query(User).join(OAuthCredential).all()
    if len(users_with_credentials) == 0:
        print("no users with credentials found")
    for user in users_with_credentials:
        gmail_client = GmailClient(user_id=user.id)
        gmail_client.fetch_emails_full_sync()
    EmailEventBus.process_unhandled_emails()

def full_sync(user_id):
    gmail_client = GmailClient(user_id=user_id)
    gmail_client.fetch_emails_full_sync(update_existing_records=True)

def send_next_message_if_bandwidth_available():
    user_id = 1
    message_queues = MessageQueue.query.filter_by(user_id=user_id).all()
    for message_queue in message_queues:
        message_queue.send_next_message_if_bandwidth_available()

def register_routes(app):
    app.register_blueprint(email_bp)


__all__ = ['Email', 'EnqueuedMessage', 'EmailEventBus', 'enqueue_test_message']
