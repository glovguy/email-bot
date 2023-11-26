from decouple import config
from flask import Flask
from flask_apscheduler import APScheduler
from src.email_inbox import EmailInbox
from src.dialogues.ponder_wittgenstein_dialogue import PonderWittgensteinDialogue
from src.dialogues.process_email_dialogue import ProcessEmailDialogue
from src.dialogues.get_to_know_you_dialogue import GetToKnowYouDialogue
from src.models import Email, User

me = User.query.filter_by(name=config('ME')).first()

def tick():
    inbox = EmailInbox()
    emails = inbox.fetch_unread_emails()
    print(len(emails), " emails received")
    
    unprocessed_emails = Email.query.filter_by(is_processed=0).all()
    print(len(unprocessed_emails), " unprocessed emails.")
    for email in unprocessed_emails:
        print("Processing email: ", email)
        ProcessEmailDialogue().process(email)

def ask_get_to_know_you():
    GetToKnowYouDialogue().ask_get_to_know_you(me)

def ponder_wittgenstein():
    PonderWittgensteinDialogue().ponder_wittgenstein(me)

app = Flask(__name__)

app.config['JOBS'] = [
    {
        'id': 'check_and_process_unread_emails',
        'func': 'app:tick',
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

@app.route("/")
def hello_world():
    return "<p>Hello, World!</p>"


if __name__ == '__main__':
    # tick()
    # ponder_wittgenstein()
    scheduler = APScheduler()
    scheduler.init_app(app)
    scheduler.start()
    app.run()
