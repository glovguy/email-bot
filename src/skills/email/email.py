from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, Integer, String
from sqlalchemy.orm import relationship
from src.models import db, db_session


class Email(db.Model):
    """
    Represents an email from the Gmail API.
    """
    __tablename__ = 'emails'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    # user = relationship("User", back_populates="emails")
    gmail_id = Column(String, nullable=False, unique=True)
    thread_id = Column(String, nullable=True)
    snippet = Column(String, nullable=True)
    from_email_address = Column(String, nullable=False)
    to_email_address = Column(String, nullable=False)
    subject = Column(String, nullable=False)
    is_processed = Column(Boolean, default=False, nullable=False)
    history_id = Column(String, nullable=True) # used for partial sync
    received_at = Column(DateTime, nullable=False)

    @classmethod
    def from_raw_gmail(cls, raw_email, user_id):
        payload = raw_email["payload"]
        headers = payload["headers"]
        email_instance = Email(
            user_id=user_id,
            gmail_id=raw_email["id"],
            thread_id=raw_email["threadId"],
            snippet=raw_email["snippet"],
            from_email_address=next((p["value"] for p in headers if p["name"].lower() == "from")),
            to_email_address=next((p["value"] for p in headers if p["name"].lower() == "to")),
            subject=next((p["value"] for p in headers if p["name"].lower() == "subject")),
            history_id=raw_email["historyId"],
            received_at=cls.internal_date_to_received_at(raw_email["internalDate"])
        )
        db_session.add(email_instance)
        db_session.commit()
        return email_instance

    def update_from_raw_gmail(self, raw_email, user_id):
        instance = db_session.merge(self)

        payload = raw_email["payload"]
        headers = payload["headers"]

        instance.user_id = user_id
        instance.thread_id=raw_email["threadId"]
        instance.snippet=raw_email["snippet"]
        instance.from_email_address=next((p["value"] for p in headers if p["name"].lower() == "from"))
        instance.to_email_address=next((p["value"] for p in headers if p["name"].lower() == "to"))
        instance.subject=next((p["value"] for p in headers if p["name"].lower() == "subject"))
        instance.history_id=raw_email["historyId"]
        instance.received_at=self.internal_date_to_received_at(raw_email["internalDate"])

        db_session.add(instance)
        db_session.commit()

    @classmethod
    def internal_date_to_received_at(cls, internal_date):
        return datetime.fromtimestamp(int(internal_date) / 1000)
