from src.email_inbox import EmailInbox
from src.dialogue import Dialogue
from src.models import Email


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

if __name__ == '__main__':
    tick()
