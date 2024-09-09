from decouple import config
import re
from email.utils import getaddresses
from pyzmail import PyzMessage
from sqlalchemy import Boolean, create_engine, Column, Integer, String, DateTime, ForeignKey, func
from sqlalchemy.engine.url import URL
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, scoped_session, sessionmaker
from sqlalchemy.sql import text, expression
from sqlalchemy.types import UserDefinedType
from contextlib import contextmanager
from flask_sqlalchemy import SQLAlchemy


EMAIL_ADDRESS = config('EMAIL_ADDRESS')

POSTGRES_USERNAME = config("POSTGRES_USERNAME")
POSTGRES_PASSWORD = config("POSTGRES_PASSWORD")
POSTGRES_DATABASE_NAME = "bot_memory"

POSTGRES_DATABASE_URL = URL.create(
    drivername="postgresql+psycopg2",
    username=POSTGRES_USERNAME,
    password=POSTGRES_PASSWORD,
    host="localhost",
    port=5432,
    database=POSTGRES_DATABASE_NAME,
)
SQLALCHEMY_DATABASE_URI = POSTGRES_DATABASE_URL.render_as_string(hide_password=False)

engine = create_engine(POSTGRES_DATABASE_URL.render_as_string(hide_password=False))
db_session = scoped_session(sessionmaker(autoflush=False, bind=engine))

@contextmanager
def session_scope():
    session = db_session()
    try:
        yield session
        session.commit()
    except:
        print("ERR CAUSING DB ROLLBACK")
        session.rollback()
        raise
    finally:
        session.close()

Base = declarative_base()
Base.query = db_session.query_property()

db = SQLAlchemy()

class Vector(UserDefinedType):
    def __init__(self, dim):
        self.dim = dim

    def get_col_spec(self):
        return f"vector({self.dim})"

    def bind_expression(self, bindvalue):
        return expression.cast(bindvalue, self)

    def bind_processor(self, _dialect):
        def process(value):
            if value is None:
                return None
            if isinstance(value, list):
                return value
            raise ValueError("Vector values must be lists")
        return process

    def result_processor(self, _dialect, _coltype):
        def process(value):
            if value is None:
                return None
            value = value.strip('[]')
            return [float(x) for x in re.split(r',\s*(?=(?:[^"]*"[^"]*")*[^"]*$)', value)]
        return process

def create_vector_extension():
    db_session.execute(text('CREATE EXTENSION IF NOT EXISTS vector'))
    db_session.execute(text("""
    CREATE OR REPLACE FUNCTION cosine_similarity(a vector, b vector)
    RETURNS float AS $$
    SELECT 1 - (a <=> b);
    $$ LANGUAGE SQL IMMUTABLE STRICT;
    """))
    db_session.commit()

class EmailOld(db.Model):
    __tablename__ = 'emails_old'

    id = Column(Integer, primary_key=True)
    sender = Column(String, nullable=False)
    recipients_csv = Column(String, nullable=False)
    subject = Column(String, nullable=False)
    content = Column(String, nullable=False)
    timestamp = Column(DateTime, default=func.now(), nullable=False)
    thread_path = Column(String)
    uid = Column(String) # UID from IMAP server
    message_id = Column(String) # unique ID for each message, used by messages to refer to each other
    sender_user_id = Column(Integer, ForeignKey('users.id'))
    # sender_user = relationship("User", back_populates="emails_old")
    is_processed = Column(Boolean, default=False, nullable=False)

    def __repr__(self):
        return f"<EmailOld(id={self.id}, uid={self.uid}, sender='{self.sender}', subject='{self.subject}')>"
    
    @property
    def recipients(self):
        if self.recipients_csv:
            return self.recipients_csv.split(',')
        return []
    
    @recipients.setter
    def recipients(self, recipients_list):
        if recipients_list:
            self.recipients_csv = ','.join(recipients_list)
        else:
            self.recipients_csv = None

    @classmethod
    def from_raw_email(cls, raw_email, email_uid):
        """Parse a raw email and return an instance of the Email model."""
        email = EmailOld.query.filter_by(uid=email_uid).first()
        if email is not None:
            print("Email entry already exists for uid ", email_uid, ". Skipping.")
            return email

        msg = PyzMessage.factory(raw_email[b'BODY[]'])
        sender_user = User.query.filter_by(email_address=msg.get_address('from')[1]).first()
        body = msg.text_part.get_payload().decode(msg.text_part.charset)
        message_id = msg.get_decoded_header('message-id')
        in_reply_to = msg.get_decoded_header('in-reply-to')
        if in_reply_to:
            # This is a hack for gmail, will need more general approach later
            [*main_body, _] = body.split("\nOn ")
            body = "\nOn ".join(main_body)
        thread_path = EmailOld.thread_path_from_parent(message_id, in_reply_to=in_reply_to)
        for sig in sender_user.signatures:
            body = body.replace(sig, '').strip()
        recipients = [recipient_tuple[1] for recipient_tuple in getaddresses(msg.get_all('to', []))]
        
        email_instance = EmailOld(
            sender=msg.get_address('from')[1],
            recipients=recipients,
            subject=msg.get_subject(),
            content=body,
            uid=email_uid,
            sender_user_id=sender_user.id if sender_user else None,
            message_id=message_id,
            thread_path=thread_path
        )
        db_session.add(email_instance)
        db_session.commit()
        
        return email_instance
    
    @classmethod
    def thread_path_from_parent(cls, current_message_id, parent_email=None, in_reply_to=None):
        print("current_message_id: ", current_message_id)
        print("parent_email: ", parent_email)
        print("in_reply_to: ", in_reply_to, type(in_reply_to))
        if parent_email is None and in_reply_to == '':
            return f"/{current_message_id}"
        
        if in_reply_to != '':
            parent_email = EmailOld.query.filter_by(message_id=in_reply_to).first()
        if parent_email is not None:
            print("Found parent email: ", parent_email)
            return f"{parent_email.thread_path}/{current_message_id}"
        return f"/{in_reply_to}/{current_message_id}"
    
    def recipient_is_chat_address(self):
        return EMAIL_ADDRESS in self.recipients
    
    def email_chain(self):
        msg_ids = [msg_id for msg_id in self.thread_path.split('/') if msg_id != '']
        return EmailOld.query.filter(EmailOld.message_id.in_(msg_ids)).all()


class User(db.Model):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    email_address = Column(String, unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    oauth_credential = relationship("OAuthCredential", back_populates="user")
    zettels = relationship("Zettel", back_populates="user")
    signatures_csv = Column(String) # comma separated list of exact string signatures used

    def __repr__(self):
        return f"<User(id={self.id}, name='{self.name}', email_address='{self.email_address}')>"
    
    @property
    def signatures(self):
        if self.signatures_csv:
            return self.signatures_csv.split(',')
        return []


def init_db():
    Base.metadata.create_all(bind=engine)
    create_vector_extension()
