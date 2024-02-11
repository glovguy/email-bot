from decouple import config
from flask import Flask
from flask_apscheduler import APScheduler
from src.email_inbox import EmailInbox
from src.skills.ponder_wittgenstein_skill import PonderWittgensteinSkill
from src.skills.process_email_skill import ProcessEmailSkill
from src.skills.get_to_know_you_skill import GetToKnowYouSkill
from src.models import Email, User
from src.skills.zettelkasten_skill import LOCAL_DOCS_FOLDER, FileManagementService
import src.views.skills

me = User.query.filter_by(name=config('ME')).first()

def tick():
    inbox = EmailInbox()
    emails = inbox.fetch_unread_emails()
    print(len(emails), " emails received")
    
    unprocessed_emails = Email.query.filter_by(is_processed=0).all()
    print(len(unprocessed_emails), " unprocessed emails.")
    for email in unprocessed_emails:
        print("Processing email: ", email)
        ProcessEmailSkill.process(email)

def ask_get_to_know_you():
    GetToKnowYouSkill.ask_get_to_know_you(me)

def ponder_wittgenstein():
    PonderWittgensteinSkill.ponder_wittgenstein(me)

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

app.add_url_rule('/skills', view_func=src.views.skills.index)

if __name__ == '__main__':
    tick()
    FileManagementService.sync_documents_from_folder(LOCAL_DOCS_FOLDER)
    # ponder_wittgenstein()
    # ask_get_to_know_you()
    scheduler = APScheduler()
    scheduler.init_app(app)
    scheduler.start()
    app.run(debug=True, use_reloader=True)
