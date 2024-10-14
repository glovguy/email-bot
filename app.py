from decouple import config
from flask import Flask
from flask_apscheduler import APScheduler
from flask_migrate import Migrate
from src.skills.ponder_wittgenstein_skill import PonderWittgensteinSkill
from src.skills.get_to_know_you_skill import GetToKnowYouSkill
from src.models import User
from src.skills.zettel.file_management_service import FileManagementService
from src.skills.zettel.zettel import LOCAL_DOCS_FOLDER
import src.views.skills
import os
from src.models import *
from src.skills.email import check_mailbox, send_next_message_if_bandwidth_available
import importlib


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

def ask_get_to_know_you():
    # GetToKnowYouSkill.ask_get_to_know_you(me, initial_doc)
    GetToKnowYouSkill.ask_get_to_know_you_latest_zettelkasten_notes(current_user())

def ponder_wittgenstein():
    PonderWittgensteinSkill.ponder_wittgenstein(current_user())


app.config['JOBS'] = [
    {
        'id': 'check_and_process_unread_emails',
        'func': 'app:check_mailbox',
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
    # ponder_wittgenstein()
    # ask_get_to_know_you()
    # scheduler = APScheduler()
    # scheduler.init_app(app)
    # scheduler.start()
    init_db()
    with app.app_context():
        check_mailbox()
        send_next_message_if_bandwidth_available(current_user())
        FileManagementService().sync_documents_from_folder(LOCAL_DOCS_FOLDER, current_user())
        app.run(port=5000, debug=True, use_reloader=True)
