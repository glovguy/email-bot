from sqlalchemy import Column, Float, Integer, ForeignKey
from src.models import db


class ZettelTopicAssociation(db.Model):
    __tablename__ = 'zettel_topic_association'

    zettel_id = Column(Integer, ForeignKey('zettels.id'), primary_key=True)
    topic_id = Column(Integer, ForeignKey('zettelkasten_topics.id'), primary_key=True)
    similarity_score = Column(Float)

    def __repr__(self):
        return f"<ZettelTopicAssociation(zettel_id={self.zettel_id}, topic_id={self.topic_id}, similarity_score={self.similarity_score})>"
