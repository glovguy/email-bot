from typing import Optional
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from src.base import Base
from src.models import db_session


import datetime


class AppSetting(Base):
    """Model for storing application settings"""
    __tablename__ = 'app_settings'

    id = Column(Integer, primary_key=True)
    key = Column(String(255), nullable=False, unique=True, index=True)
    value = Column(Text, nullable=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    user = relationship("User", back_populatess="app_settings")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    @classmethod
    def get(cls, key: str, user_id: Optional[int] = None, default: Optional[str] = None) -> str | None:
        """Get a setting value by key and optional user_id"""
        setting = db_session.query(cls).filter(cls.key == key, cls.user_id == user_id).first()
        return setting.value if setting else default

    @classmethod
    def set(cls, key: str, value: str, user_id: Optional[int] = None):
        """Set a setting value by key and optional user_id"""
        setting = db_session.query(cls).filter(cls.key == key, cls.user_id == user_id).first()
        if setting:
            setting.value = value
        else:
            setting = cls(key=key, value=value, user_id=user_id)
            db_session.add(setting)
        db_session.commit()