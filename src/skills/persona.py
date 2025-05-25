from sqlalchemy import Column, Integer, String
from src.user import User
from src.models import Base
from src.custom_types import SemanticContext

class Persona(Base):
    __tablename__ = 'personas'

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=False)
    system_prompt = Column(String, nullable=False)

    def __init__(self, name: str, description: str, system_prompt: str):
        self.name = name
        self.description = description
        self.system_prompt = system_prompt

    def __str__(self):
        return f"{self.name}: {self.description} ({self.system_prompt})"
    
    def __repr__(self):
        return f"{self.name}: {self.description} ({self.system_prompt})"
    
    def as_semantic_context(self) -> SemanticContext:
        return {
            "name": self.name,
            "description": self.description,
            "system_prompt": self.system_prompt
        }

    def create_conversation(self):
        """Create a conversation with this persona"""
        from src.conversation import PersonaConversation
        return PersonaConversation(self)
