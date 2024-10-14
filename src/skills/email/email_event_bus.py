from src.models import db, db_session
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from .email import Email


class EmailCommandListener(db.Model):
    __tablename__ = 'email_command_listeners'

    id = Column(Integer, primary_key=True)
    gmail_thread_id = Column(String(255), nullable=False, unique=True)
    listener_function = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=func.now())

    def __repr__(self):
        return f'<EmailCommandListener {self.id} for thread {self.gmail_thread_id}>'


class EmailEventBus:
    @classmethod
    def register_listener(cls, gmail_thread_id: str, listener_function: str):
        print(f"Registering listener {listener_function} for thread {gmail_thread_id}")
        listener = db_session.query(EmailCommandListener).filter_by(gmail_thread_id=gmail_thread_id).first()
        if listener:
            listener.listener_function = listener_function
        else:
            listener = EmailCommandListener(
                gmail_thread_id=gmail_thread_id,
                listener_function=listener_function
            )
        db_session.add(listener)
        db_session.commit()

    @classmethod
    def dispatch_email(cls, email):
        listener = db_session.query(EmailCommandListener).filter_by(gmail_thread_id=email.thread_id).first()
        if listener:
            try:
                module_name, function_name = listener.listener_function.rsplit('.', 1)
                module = __import__(module_name, fromlist=[function_name])
                listener_fn = getattr(module, function_name)

                listener_fn(email)

                email.is_processed = True
                db_session.commit()
            except Exception as e:
                print(f"Error dispatching email: {str(e)}")
        else:
            print(f"No listener found for email thread {email.thread_id}")
            email.is_processed = True
            db_session.commit()

    @classmethod
    def process_unhandled_emails(cls):
        unprocessed_emails = db_session.query(Email).filter_by(is_processed=False).all()
        for email in unprocessed_emails:
            EmailEventBus.dispatch_email(email)
