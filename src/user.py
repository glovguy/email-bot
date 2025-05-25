from src.base import Base
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship


class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    email_address = Column(String, unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    oauth_credential = relationship("OAuthCredential", back_populates="user", uselist=False)
    zettels = relationship("Zettel", back_populates="user")
    topics = relationship("ZettelkastenTopic", back_populates="user")
    message_queues = relationship("MessageQueue", back_populates="user")
    emails = relationship("Email", back_populates="user")
    contacts = relationship("Contact", back_populates="user")
    hour_awake = Column(Integer, default=9) # when we would expect the user to read and respond to emails
    hour_bedtime = Column(Integer, default=17)
    # open_questions = relationship("src.skills.interest.open_question.OpenQuestion", back_populates="user")
    app_settings = relationship("AppSetting", back_populates="user")
    conversation_histories = relationship("ConversationHistory", back_populates="user")

    def __repr__(self):
        return f"<User(id={self.id}, name='{self.name}', email_address='{self.email_address}')>"
