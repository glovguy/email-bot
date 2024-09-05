from decouple import config
import hashlib
import uuid
from src.skills.base import default_embeddings_model
from src.models import db, Vector
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, func, Index, event
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID


LOCAL_DOCS_FOLDER = config('LOCAL_DOCS_FOLDER')

def instructor_note_embed(doc_string):
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

    __table_args__ = (
        Index('ix_zettel_embedding', 'instructor_base_embedding', postgresql_using='ivfflat'),
    )

    def __repr__(self):
        return f'<Zettel user_id: {self.user_id} uuid: {self.uuid} title: {self.title[:30]}>'

    @classmethod
    def doc_sha(cls, doc_string):
        return hashlib.sha256(doc_string.encode('utf-8')).hexdigest()

    @classmethod
    def find_similar(cls, doc_string, limit=5):
        comparison_embedding = instructor_note_embed(doc_string)
        return cls.query.order_by(
            func.cosine_similarity(cls.instructor_embedding, comparison_embedding).desc()
        ).limit(limit).all()


def on_change_content(target, value, _oldvalue, _initiator):
    target.instructor_base_embedding = instructor_note_embed(value)
    target.sha = Zettel.doc_sha(value)

event.listen(Zettel.content, 'set', on_change_content)
