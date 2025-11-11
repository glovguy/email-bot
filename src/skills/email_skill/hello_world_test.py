
from .gmail_client import GmailClient
from .message_queue import MessageQueue


def test_response_listener(email):
    gmail_client = GmailClient(user_id=1)
    email_content = gmail_client.get_email_content(email)
    print("test_response_listener, email: ", email_content)


def enqueue_test_message():
    print("sending test message...")
    q = MessageQueue.get_or_create(1, "email")
    q.enqueue_message("Hello, world!", "karlsmith@bouzou.com", subject="Hello, world!", response_listener=test_response_listener)
