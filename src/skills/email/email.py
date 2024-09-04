from sqlalchemy import Boolean, Column, Integer, String
from src.models import db, db_session, object_session


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

    def update_from_raw_gmail(self, raw_email):
        # manage instance session
        session = object_session(self) or db_session
        instance = session.merge(self)

        payload = raw_email["payload"]
        headers = payload["headers"]

        instance.thread_id=raw_email["threadId"]
        instance.snippet=raw_email["snippet"]
        instance.from_email_address=next((p["value"] for p in headers if p["name"] == "From"))
        instance.to_email_address=next((p["value"] for p in headers if p["name"] == "To"))
        instance.subject=next((p["value"] for p in headers if p["name"] == "Subject"))
        instance.history_id=raw_email["historyId"]

        session.add(self)
        session.commit()