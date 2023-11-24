from decouple import config
from src.email_inbox import EmailInbox
from src.dialogue import Dialogue
from src.models import Email, User


inbox = EmailInbox()
dialogue = Dialogue()

def tick():
    emails = inbox.fetch_unread_emails()
    print(len(emails), " emails received")
    
    unprocessed_emails = Email.query.filter_by(is_processed=0).all()
    print(len(unprocessed_emails), " unprocessed emails.")
    for email in unprocessed_emails:
        print("Processing email: ", email)
        dialogue.process(email)

def ask_get_to_know_you():
    me = User.query.filter_by(name=config('ME')).first()
    dialogue.ask_get_to_know_you(me)

def ponder_wittgenstein():
    me = User.query.filter_by(name=config('ME')).first()
    dialogue.ponder_wittgenstein(me)

if __name__ == '__main__':
    tick()
    ponder_wittgenstein()
