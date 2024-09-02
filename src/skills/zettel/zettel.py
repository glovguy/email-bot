from decouple import config
from src.models import db, db_session
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship


LOCAL_DOCS_FOLDER = config('LOCAL_DOCS_FOLDER')

class Zettel(db.Model):
    __tablename__ = "zettel"

    id = Column(Integer, primary_key=True)
    uuid = Column(String(512), nullable=False)
    sha = Column(String(512), nullable=False)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)
    content = Column(Text, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user = relationship("User", back_populates="zettels")
    title = Column(Text, nullable=False)
    filepath = Column(Text, nullable=False)

    def __repr__(self):
        return f'<Zettel user_id: {self.user_id} uuid: {self.uuid} title: {self.title[:30]}>'
