from src.user import User
from src.models import db_session
from src.skills.email.email_event_bus import EmailEventBus
from src.skills.email.gmail_client import GmailClient
from src.skills.email.message_queue import MessageQueue
from src.skills.email.oauth_credential import OAuthCredential


def send_next_message_if_bandwidth_available():
    user_id = 1
    message_queues = MessageQueue.query.filter_by(user_id=user_id).all()
    for message_queue in message_queues:
        message_queue.send_next_message_if_bandwidth_available()


def check_mailbox():
    print("checking mailbox...")
    users_with_credentials = db_session.query(User).join(OAuthCredential).all()
    if len(users_with_credentials) == 0:
        print("no users with credentials found")
    for user in users_with_credentials:
        gmail_client = GmailClient(user_id=user.id)
        gmail_client.fetch_emails_full_sync()
    EmailEventBus.process_unhandled_emails()