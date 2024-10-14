import math
import inspect
from src.models import db, db_session
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime, timedelta
from .enqueued_message import EnqueuedMessage
from .gmail_client import GmailClient
from .email import Email
from .email_event_bus import EmailEventBus


class MessageQueue(db.Model):
    __tablename__ = 'message_queues'

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    user = relationship('User', back_populates='message_queues')
    created_at = Column(DateTime, default=func.now())
    enqueued_messages = relationship('EnqueuedMessage', back_populates='queue')
    user_attention_bandwidth_minutes = Column(Integer, nullable=False, default=120)

    def __repr__(self):
        return f'<MessageQueue {self.name} user_id={self.user_id}>'

    @classmethod
    def get_or_create(cls, user_id: int, queue_name: str):
        message_queue = db_session.query(cls).filter_by(user_id=user_id, name=queue_name).first()
        if not message_queue:
            message_queue = MessageQueue(user_id=user_id, name=queue_name)
            db_session.add(message_queue)
            db_session.commit()
        return message_queue

    def send_next_message_if_bandwidth_available(self):
        remaining_bandwidth = self.user_remaining_attention_bandwidth()
        print(f"Remaining bandwidth: {remaining_bandwidth}")
        next_message = self.get_next_message(remaining_bandwidth)
        if next_message:
            self.send_enqueued_message(next_message)

    def enqueue_message(self, content, recipient_email, email_thread_id=None, subject=None, estimated_time=None, response_listener=None):
        if email_thread_id is None and subject is None:
            raise ValueError("email_thread_id or subject must be provided")
        if email_thread_id is None and response_listener is None:
            raise ValueError("email_thread_id or response_listener must be provided")
        if email_thread_id is not None and subject is None:
            latest_email_in_thread = Email.query.filter_by(thread_id=email_thread_id).order_by(Email.id.desc()).first()
            subject = latest_email_in_thread.subject
        if estimated_time is None:
            estimated_time = len(content.split(" ")) / 250 * 60 # 250 wpm
        if response_listener is not None:
            if inspect.ismethod(response_listener):
                raise ValueError("classmethods are not supported for response_listener")
            elif inspect.isfunction(response_listener):
                module = inspect.getmodule(response_listener)
                response_listener = f"{module.__name__}.{response_listener.__name__}"
            elif isinstance(response_listener, str):
                pass
            else:
                raise ValueError("response_listener must be a function or a string")

        message = EnqueuedMessage(
            content=content,
            queue_id=self.id,
            estimated_time=estimated_time,
            recipient_email=recipient_email,
            email_thread_id=email_thread_id,
            subject=subject,
            response_listener=response_listener
        )
        db_session.add(message)
        db_session.commit()
        return message

    def user_remaining_attention_bandwidth(self):
        now = datetime.now()
        thirty_six_hours_ago = now - timedelta(hours=36)

        sent_messages = EnqueuedMessage.query.filter(
            EnqueuedMessage.queue_id == self.id,
            EnqueuedMessage.sent_at >= thirty_six_hours_ago,
            EnqueuedMessage.sent_at <= now
        ).all()

        total_weighted_time = 0
        for message in sent_messages:
            hours_since_sent = (now - message.sent_at).total_seconds() / 3600
            decay_factor = math.exp(-hours_since_sent / 12)  # Half-life of 12 hours
            total_weighted_time += message.estimated_time * decay_factor

        remaining_bandwidth = self.user_attention_bandwidth_minutes - total_weighted_time

        return max(0, remaining_bandwidth)

    def send_enqueued_message(self, enqueued_message):
        gmail_response = GmailClient(user_id=self.user_id).send_message(enqueued_message)
        thread_id = enqueued_message.email_thread_id or gmail_response['threadId']
        EmailEventBus.register_listener(thread_id, enqueued_message.response_listener)
        enqueued_message.mark_as_sent(thread_id)

    def get_next_message(self, estimated_time_threshold=None):
        query = db_session.query(EnqueuedMessage).filter(EnqueuedMessage.queue_id == self.id, EnqueuedMessage.sent_at == None)
        if estimated_time_threshold:
            query = query.filter(EnqueuedMessage.estimated_time <= estimated_time_threshold)
        return query.order_by(EnqueuedMessage.created_at).first()
