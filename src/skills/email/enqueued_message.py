from src.models import db, db_session
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime


class EnqueuedMessage(db.Model):
    __tablename__ = 'enqueued_messages'

    id = Column(Integer, primary_key=True)
    content = Column(Text, nullable=False)
    estimated_time = Column(Integer, nullable=False)  # in minutes
    queue_id = Column(Integer, ForeignKey('message_queues.id'), nullable=False)
    queue = relationship('MessageQueue', back_populates='enqueued_messages')
    created_at = Column(DateTime, default=func.now())
    email_thread_id = Column(String(255), nullable=True)
    recipient_email = Column(String(255), nullable=False)
    subject = Column(String(255), nullable=False)
    sent_at = Column(DateTime, nullable=True)
    response_listener = Column(String(255), nullable=True)

    def __repr__(self):
        return f'<EnqueuedMessage {self.id}>'
    
    def mark_as_sent(self, email_thread_id: str):
        self.sent_at = datetime.now()
        self.email_thread_id = email_thread_id
        db_session.commit()
