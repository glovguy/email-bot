from datetime import datetime
import json
from decouple import config
from email.utils import getaddresses
from flask_sqlalchemy import SQLAlchemy
from google.oauth2.credentials import Credentials
from pyzmail import PyzMessage
from sqlalchemy import Boolean, create_engine, Column, Integer, String, Text, DateTime, ForeignKey, func
from sqlalchemy.engine.url import URL
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, scoped_session, sessionmaker


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
db_session = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))

Base = declarative_base()
Base.query = db_session.query_property()

db = SQLAlchemy()


class Email(db.Model):
    __tablename__ = 'emails'

    id = Column(Integer, primary_key=True)
    gmail_id = Column(String, nullable=False, unique=True)
    thread_id = Column(String, nullable=True)
    snippet = Column(String, nullable=True)
    from_email_address = Column(String, nullable=False)
    to_email_address = Column(String, nullable=False)
    subject = Column(String, nullable=False)
    is_processed = Column(Boolean, default=False, nullable=False)
    history_id = Column(String, nullable=True)

    @classmethod
    def from_raw_gmail(cls, raw_email):
        payload = raw_email["payload"]
        headers = payload["headers"]
        email_instance = Email(
            gmail_id=raw_email["id"],
            thread_id=raw_email["threadId"],
            snippet=raw_email["snippet"],
            from_email_address=next((p["value"] for p in headers if p["name"] == "From")),
            to_email_address=next((p["value"] for p in headers if p["name"] == "To")),
            subject=next((p["value"] for p in headers if p["name"] == "Subject")),
            history_id=raw_email["historyId"]
        )
        db_session.add(email_instance)
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
    # emails = relationship("Email", order_by=Email.id, back_populates="sender_user")
    # emails_old = relationship("EmailOld", order_by=EmailOld.id, back_populates="sender_user_old")
    oauth_credential = relationship("OAuthCredential", back_populates="user")
    signatures_csv = Column(String) # comma separated list of exact string signatures used

    def __repr__(self):
        return f"<User(id={self.id}, name='{self.name}', email_address='{self.email_address}')>"
    
    @property
    def signatures(self):
        if self.signatures_csv:
            return self.signatures_csv.split(',')
        return []


class OAuthCredential(db.Model):
    __tablename__ = "oauth_credential"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user = relationship("User", back_populates="oauth_credential")
    token = Column(Text, nullable=False)
    refresh_token = Column(String(512), nullable=True)
    token_uri = Column(String(512), nullable=False)
    client_id = Column(String(512), nullable=False)
    client_secret = Column(String(512), nullable=False)
    scopes = Column(Text, nullable=True)
    expiry = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f'<OAuthCredential user_id: {self.user_id} expiry: {self.expiry}>'

    @property
    def is_expired(self):
        if self.expiry:
            return datetime.utcnow() > self.expiry
        return True

    @classmethod
    def create_or_update(cls, user_id, credentials):
        credential = cls.query.filter_by(user_id=user_id).first()
        if credential:
            credential.token = credentials.token
            credential.refresh_token = credentials.refresh_token
            credential.token_uri = credentials.token_uri
            credential.client_id = credentials.client_id
            credential.client_secret = credentials.client_secret
            credential.scopes = json.dumps(credentials.scopes)
            credential.expiry = credentials.expiry
        else:
            credential = cls(
                user_id=user_id,
                token=credentials.token,
                refresh_token=credentials.refresh_token,
                token_uri=credentials.token_uri,
                client_id=credentials.client_id,
                client_secret=credentials.client_secret,
                scopes=json.dumps(credentials.scopes),
                expiry=credentials.expiry
            )
            db_session.add(credential)

        db_session.commit()
        return credential

    def to_credentials(self):
        return Credentials(
            token=self.token,
            refresh_token=self.refresh_token,
            token_uri=self.token_uri,
            client_id=self.client_id,
            client_secret=self.client_secret,
            scopes=json.loads(self.scopes) if self.scopes else None
        )


def init_db():
    Base.metadata.create_all(bind=engine)
