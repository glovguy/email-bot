from pyzmail import PyzMessage
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, Session, scoped_session, sessionmaker

DATABASE_URL = "sqlite:///../email_bot.db"

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
    subject = Column(String, nullable=False)
    content = Column(String, nullable=False)
    timestamp = Column(DateTime, default=func.now(), nullable=False)
    parent_id = Column(Integer, ForeignKey('emails.id'))
    parent = relationship("Email", remote_side=[id])
    uid = Column(String) # UID from IMAP server
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    user = relationship("User", back_populates="emails")

    def __repr__(self):
        return f"<Email(id={self.id}, sender='{self.sender}', subject='{self.subject}')>"

    @staticmethod
    def from_raw_email(raw_email, email_uid, user_id):
        """Parse a raw email and return an instance of the Email model."""
        message = PyzMessage.factory(raw_email[b'BODY[]'])
        email_instance = Email(
            sender=message.get_address('from')[1],
            subject=message.get_subject(),
            content=message.text_part.get_payload().decode(message.text_part.charset),
            uid=email_uid,
            user_id=user_id,
            # parent_id logic, if applicable, goes here
        )
        db_session.add(email_instance)
        db_session.commit()
        
        return email_instance

class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    email_address = Column(String, unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    emails = relationship("Email", order_by=Email.id, back_populates="user")

    def __repr__(self):
        return f"<User(id={self.id}, name='{self.name}', email_address='{self.email_address}')>"

def init_db():
    Base.metadata.create_all(bind=engine)
