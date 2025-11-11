from .oauth_credential import OAuthCredential
from .gmail_client import GmailClient
from .email import Email
from .enqueued_message import EnqueuedMessage
from .message_queue import MessageQueue
from .email_event_bus import EmailEventBus
from .views import email_bp
from .hello_world_test import enqueue_test_message
from .default_listener import default_listener
from src.skills.zettel import Zettel
from .jobs import check_mailbox, send_next_message_if_bandwidth_available

def full_sync(user_id: int):
    gmail_client = GmailClient(user_id=user_id)
    gmail_client.fetch_emails_full_sync(update_existing_records=True)

def register_routes(app):
    app.register_blueprint(email_bp)


__all__ = ['Email', 'EnqueuedMessage', 'EmailEventBus', 'enqueue_test_message', 'OAuthCredential', 'MessageQueue', 'default_listener']
