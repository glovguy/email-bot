from typing import List, Tuple, Type, Optional
from decouple import config
import hashlib
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, func, Index, event
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql.expression import cast
import uuid
from src.skills.base import default_embeddings_model
from src.models import db, Vector, db_session
from .zettel_topic_association import ZettelTopicAssociation


LOCAL_DOCS_FOLDER = config('LOCAL_DOCS_FOLDER')

def instructor_note_embed(doc_string) -> List[float]:
    instruction = "Represent the personal Zettelkasten note for storing and retrieving personal insights: "
    vec = default_embeddings_model.encode([[instruction, doc_string]]).tolist()
    return vec[0]

class Zettel(db.Model):
    __tablename__ = "zettels"

    id = Column(Integer, primary_key=True)
    uuid = Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False)
    sha = Column(String(64), nullable=False)
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
    content = Column(Text, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user = relationship("User", back_populates="zettels")
    title = Column(String(255), nullable=False)
    filepath = Column(String(255), nullable=False, unique=True)
    instructor_base_embedding = Column(Vector(768))
    topics = relationship("ZettelkastenTopic", secondary="zettel_topic_association", back_populates="zettels")

    __table_args__ = (
        Index('ix_zettel_embedding', 'instructor_base_embedding', postgresql_using='ivfflat'),
    )

    def __repr__(self) -> str:
        return f'<Zettel user_id: {self.user_id} uuid: {self.uuid} title: {self.title[:30]}>'

    @classmethod
    def doc_sha(cls, doc_string) -> str:
        return hashlib.sha256(doc_string.encode('utf-8')).hexdigest()

    @classmethod
    def find_similar(cls, doc_string, limit=5) -> List[Tuple[Type["Zettel"], float]]:
        """Returns list containing elements of [Zettel, float sim score]"""
        comparison_embedding = instructor_note_embed(doc_string)
        return cls.vector_search(comparison_embedding, limit)

    @classmethod
    def vector_search(cls, comparison_embedding: List[List[float]], limit=5) -> List[Tuple[Type["Zettel"], float]]:
        """Returns list containing elements of [Zettel, float sim score]"""
        vector_cast = func.vector(cast(comparison_embedding, cls.instructor_base_embedding.type))
        similarity_scores = func.cosine_similarity(cls.instructor_base_embedding, vector_cast)
        query = db_session.query(cls).with_entities(cls, similarity_scores).order_by(similarity_scores.desc()).limit(limit).all()
        return [(item[0], item[1]) for item in query]

    def similarity_score_for_topic(self, topic_id: int) -> Optional[float]:
        association = ZettelTopicAssociation.query.filter_by(topic_id=topic_id, zettel_id=self.id).first()
        return association.similarity_score if association else None


def on_change_content(target, value, _oldvalue, _initiator):
    target.instructor_base_embedding = instructor_note_embed(value)
    target.sha = Zettel.doc_sha(value)

event.listen(Zettel.content, 'set', on_change_content)
