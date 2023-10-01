from pyzmail import PyzMessage
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, Session

Base = declarative_base()

class Email(Base):
    __tablename__ = 'emails'

    id = Column(Integer, primary_key=True)
    sender = Column(String, nullable=False)
    subject = Column(String, nullable=False)
    content = Column(String, nullable=False)
    timestamp = Column(DateTime, default=func.now())
    parent_id = Column(Integer, ForeignKey('emails.id'))
    uid = Column(String) # UID from IMAP server

    parent = relationship("Email", remote_side=[id])

    def __repr__(self):
        return f"<Email(id={self.id}, sender='{self.sender}', subject='{self.subject}')>"

    @staticmethod
    def from_raw_email(raw_email, email_uid, session: Session):
        """Parse a raw email and return an instance of the Email model."""
        message = PyzMessage.factory(raw_email[b'BODY[]'])
        email_instance = Email(
            sender=message.get_address('from')[1],
            subject=message.get_subject(),
            content=message.text_part.get_payload().decode(message.text_part.charset),
            uid=email_uid,
            # parent_id logic, if applicable, goes here
        )
        session.add(email_instance)
        session.commit()
        
        return email_instance
