from tqdm import tqdm
from decouple import config
from flask import Flask
from flask_apscheduler import APScheduler
from flask_migrate import Migrate
from src.skills.zettel import Zettel
from src.skills.ponder_wittgenstein_skill import PonderWittgensteinSkill
from src.skills.get_to_know_you_skill import GetToKnowYouSkill
from src.models import User
from src.skills.zettel.file_management_service import FileManagementService
from src.skills.zettel import LOCAL_DOCS_FOLDER
from src.skills.zettel import ZettelkastenTopic
from src.skills.interest import OpenQuestion
import src.views.skills
import os
from src.models import *
from src.skills.email import check_mailbox, send_next_message_if_bandwidth_available
import importlib
from src.skills.perplexity import measure_perplexity_of_zettels

def create_app():
    app = Flask(__name__)
    app.secret_key = os.urandom(24)
    app.config['SQLALCHEMY_DATABASE_URI'] = POSTGRES_DATABASE_URL.render_as_string(hide_password=False)
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)

    Migrate(app, db)

    @app.teardown_appcontext
    def shutdown_session(exception=None):
        db_session.remove()

    return [app, db]

[app, db] = create_app()


# TODO: remove
app.add_url_rule('/skills', view_func=src.views.skills.index)


def current_user():
    return User.query.filter_by(name=config('ME')).first()

def sync_mailbox():
    # with app.app_context():
    check_mailbox()

def send_enqueued_messages():
    # with app.app_context():
    send_next_message_if_bandwidth_available()

def ask_get_to_know_you():
    # GetToKnowYouSkill.ask_get_to_know_you(me, initial_doc)
    GetToKnowYouSkill.ask_get_to_know_you_latest_zettelkasten_notes(current_user())

def ponder_wittgenstein():
    PonderWittgensteinSkill.ponder_wittgenstein(current_user())

def sync_local_docs():
    # with app.app_context():
    FileManagementService().sync_documents_from_folder(LOCAL_DOCS_FOLDER, current_user())

app.config['JOBS'] = [
    {
        'id': 'check_mailbox',
        'func': 'app:sync_mailbox',
        'trigger': 'interval',
        'minutes': 17
    },
    {
        'id': 'send_enqueued_messages',
        'func': 'app:send_enqueued_messages',
        'trigger': 'interval',
        'minutes': 29
    },
    {
        'id': 'sync_local_docs',
        'func': 'app:sync_local_docs',
        'trigger': 'interval',
        'days': 1
    },
    # {
    #     'id': 'ponder_wittgenstein',
    #     'func': 'app:ponder_wittgenstein',
    #     'trigger': 'interval',
    #     'days': 2
    # },
    # {
    #     'id': 'ask_get_to_know_you',
    #     'func': 'app:ask_get_to_know_you',
    #     'trigger': 'interval',
    #     'days': 1
    # }
]

def register_all_routes():
    skills_dir = os.path.join(os.path.dirname(__file__), 'src', 'skills')
    for skill in os.listdir(skills_dir):
        skill_path = os.path.join(skills_dir, skill)
        if os.path.isdir(skill_path):
            try:
                views_module = importlib.import_module(f'src.skills.{skill}')
                if hasattr(views_module, 'register_routes'):
                    views_module.register_routes(app)
                    print(f"Registered routes for skill: {skill}")
            except ImportError as e:
                print(f"Could not import views for skill {skill}: {e}")

register_all_routes()


if __name__ == '__main__':
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'  # For development only
    # scheduler = APScheduler()
    # scheduler.init_app(app)
    # scheduler.start()

    # Function to shut down the scheduler
    # @app.teardown_appcontext
    # def shutdown_scheduler(exception=None):
    #     scheduler.shutdown()

    with app.app_context():
        # ponder_wittgenstein()
        # ask_get_to_know_you()
        check_mailbox()
        send_next_message_if_bandwidth_available()
        sync_local_docs()
        measure_perplexity_of_zettels()
        # topics = db_session.query(ZettelkastenTopic).filter(ZettelkastenTopic.user_id == current_user().id).all()
        # for topic in topics:
        #     print(f"Speculating open questions for topic: {topic.name}")
        #     OpenQuestion.speculate_open_questions_from_topic(topic)
        # app.run(port=5000, debug=True, use_reloader=True)
