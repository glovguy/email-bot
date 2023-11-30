from decouple import config
from email.utils import getaddresses
from pyzmail import PyzMessage
from sqlalchemy import Boolean, create_engine, Column, Integer, String, DateTime, ForeignKey, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, scoped_session, sessionmaker

DATABASE_URL = "sqlite:///email_bot.db"
SAVE_EMAIL_ADDRESS = config('SAVE_EMAIL_ADDRESS')

engine = create_engine(DATABASE_URL, convert_unicode=True)
db_session = scoped_session(sessionmaker(autocommit=False,
                                         autoflush=False,
                                         bind=engine))

Base = declarative_base()
Base.query = db_session.query_property()


class Email(Base):
    __tablename__ = 'emails'

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
    sender_user = relationship("User", back_populates="emails")
    is_processed = Column(Boolean, default=False, nullable=False)

    def __repr__(self):
        return f"<Email(id={self.id}, uid={self.uid}, sender='{self.sender}', subject='{self.subject}')>"
    
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
        email = Email.query.filter_by(uid=email_uid).first()
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
        thread_path = Email.thread_path_from_parent(message_id, in_reply_to=in_reply_to)
        for sig in sender_user.signatures:
            body = body.replace(sig, '').strip()
        recipients = [recipient_tuple[1] for recipient_tuple in getaddresses(msg.get_all('to', []))]
        
        email_instance = Email(
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
            parent_email = Email.query.filter_by(message_id=in_reply_to).first()
        if parent_email is not None:
            print("Found parent email: ", parent_email)
            return f"{parent_email.thread_path}/{current_message_id}"
        return f"/{in_reply_to}/{current_message_id}"
    
    def recipient_is_save_address(self):
        return SAVE_EMAIL_ADDRESS in self.recipients
    
    def email_chain(self):
        msg_ids = [msg_id for msg_id in self.thread_path.split('/') if msg_id != '']
        return Email.query.filter(Email.message_id.in_(msg_ids)).all()


class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    email_address = Column(String, unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    emails = relationship("Email", order_by=Email.id, back_populates="sender_user")
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
