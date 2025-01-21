from decouple import config
import re
import numpy as np
from email.utils import getaddresses
from pyzmail import PyzMessage
from sqlalchemy import Boolean, create_engine, Column, Integer, String, DateTime, ForeignKey, func
from sqlalchemy.engine.url import URL
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, scoped_session, sessionmaker
from sqlalchemy.sql import text, expression
from sqlalchemy.types import UserDefinedType
from flask_sqlalchemy import SQLAlchemy


EMAIL_ADDRESS = config('EMAIL_ADDRESS')
POSTGRES_DATABASE_NAME = "bot_memory"
POSTGRES_USERNAME = config("POSTGRES_USERNAME")
POSTGRES_PASSWORD = config("POSTGRES_PASSWORD")

POSTGRES_DATABASE_URL = URL.create(
    drivername="postgresql+psycopg2",
    username=POSTGRES_USERNAME,
    password=POSTGRES_PASSWORD,
    host="localhost",
    port=5432,
    database=POSTGRES_DATABASE_NAME,
)
SQLALCHEMY_DATABASE_URI = POSTGRES_DATABASE_URL.render_as_string(hide_password=False)

def init_session():
    # singleton db session, no multithreading
    engine = create_engine(POSTGRES_DATABASE_URL.render_as_string(hide_password=False))
    db_session = scoped_session(sessionmaker(autoflush=True, bind=engine))
    return engine, db_session

engine, db_session = init_session()

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


def cosine_similarity(a, b):
    if not isinstance(a, np.ndarray):
        a = np.array(a)
    if not isinstance(b, np.ndarray):
        b = np.array(b)

    dot_product = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)

    similarity = dot_product / (norm_a * norm_b)
    return similarity


def create_vector_extension():
    db_session.execute(text('CREATE EXTENSION IF NOT EXISTS vector'))
    db_session.execute(text("""
    CREATE OR REPLACE FUNCTION cosine_similarity(a vector, b vector)
    RETURNS float AS $$
    SELECT 1 - (a <=> b);
    $$ LANGUAGE SQL IMMUTABLE STRICT;
    """))
    db_session.commit()


class User(db.Model):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    email_address = Column(String, unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    oauth_credential = relationship("OAuthCredential", back_populates="user")
    zettels = relationship("Zettel", back_populates="user")
    topics = relationship("ZettelkastenTopic", back_populates="user")
    message_queues = relationship("MessageQueue", back_populates="user")
    emails = relationship("Email", back_populates="user")
    hour_awake = Column(Integer, default=9) # when we would expect the user to read and respond to emails
    hour_bedtime = Column(Integer, default=17)
    open_questions = relationship("OpenQuestion", back_populates="user")

    def __repr__(self):
        return f"<User(id={self.id}, name='{self.name}', email_address='{self.email_address}')>"

def create_user(email_address, name, **kwargs):
    user = User(
        email_address=email_address,
        name=name,
        **kwargs,
    )
    db_session.add(user)
    db_session.commit()
    return user

# deprecated
class EmailOld:
    """
    Legacy email class, no longer mapped to database table.
    Kept for compatibility with existing code.
    """

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


def setup_db():
    print("running setup!")
    # Create database if it doesn't exist
    temp_engine = create_engine(f"postgresql+psycopg2://{POSTGRES_USERNAME}:{POSTGRES_PASSWORD}@localhost/postgres")
    conn = temp_engine.connect()
    conn.execute(text("commit"))
    try:
        conn.execute(text(f"CREATE DATABASE {POSTGRES_DATABASE_NAME}"))
    except:
        pass
    conn.close()
    temp_engine.dispose()
    # Create models
    Base.metadata.create_all(bind=engine)
    create_vector_extension()
