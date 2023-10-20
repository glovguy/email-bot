from decouple import config
from email.utils import getaddresses
from pyzmail import PyzMessage
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, scoped_session, sessionmaker
# from talon.signature.bruteforce import extract_signature

DATABASE_URL = "sqlite:///email_bot.db"
SAVE_EMAIL_ADDRESS = config('SAVE_EMAIL_ADDRESS', default=config('EMAIL_ADDRESS'))

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
    parent_id = Column(Integer, ForeignKey('emails.id'))
    parent = relationship("Email", remote_side=[id])
    uid = Column(String) # UID from IMAP server
    sender_user_id = Column(Integer, ForeignKey('users.id'))
    sender_user = relationship("User", back_populates="emails")

    def __repr__(self):
        return f"<Email(id={self.id}, sender='{self.sender}', subject='{self.subject}')>"
    
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

    @staticmethod
    def from_raw_email(raw_email, email_uid):
        """Parse a raw email and return an instance of the Email model."""
        message = PyzMessage.factory(raw_email[b'BODY[]'])
        sender_user = User.query.filter_by(email_address=message.get_address('from')[1]).first()
        body = message.text_part.get_payload().decode(message.text_part.charset)
        for sig in sender_user.signatures:
            body = body.replace(sig, '').strip()
        recipients = [recipient_tuple[1] for recipient_tuple in getaddresses(message.get_all('to', []))]
        
        email_instance = Email(
            sender=message.get_address('from')[1],
            recipients=recipients,
            subject=message.get_subject(),
            content=body,
            uid=email_uid,
            sender_user_id=sender_user.id if sender_user else None,
            # parent_id logic, if applicable, goes here
        )
        db_session.add(email_instance)
        db_session.commit()
        
        return email_instance
    
    def recipient_is_save_address(self):
        return SAVE_EMAIL_ADDRESS in self.recipients

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
