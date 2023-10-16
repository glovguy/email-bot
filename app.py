from src.email_inbox import EmailInbox
from src.dialogue import Dialogue

inbox = EmailInbox()


dialogue = Dialogue()

def tick():
    emails = inbox.fetch_unread_emails()
    print(len(emails), " emails received")
    for email in emails:
        print("Processing email: ", email)
        response = dialogue.process(email)
        print("Response in dialogue: ", response)


if __name__ == '__main__':
    tick()
