from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON, Boolean, Float, func
from sqlalchemy.orm import relationship
from src.models import Base, db_session
import uuid
from typing import List, Dict, Any
import datetime


class ConversationHistory(Base):
    """
    Stores imported conversations and their messages for analysis.
    """
    __tablename__ = "conversation_histories"

    id = Column(Integer, primary_key=True)
    uuid = Column(String(36), default=lambda: str(uuid.uuid4()), unique=True, nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user = relationship("User", backref="conversation_histories")
    messages = Column(JSON, nullable=False)  # Stores the full conversation as a list of message objects
    source = Column(String(255), nullable=True)  # Where the conversation was imported from

    objectives = relationship("Objective", back_populates="conversation_history", cascade="all, delete-orphan")
    simulations = relationship("Simulation", back_populates="conversation_history", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f'<ConversationHistory id: {self.id} title: {self.title}>'

    @classmethod
    def from_message_list(cls, message_list: List[Dict[str, Any]], title: str, user_id: int, 
                         description: str = None, source: str = None):
        """Create a conversation record from a list of message objects"""
        conversation = cls(
            title=title,
            description=description,
            user_id=user_id,
            messages=message_list,
            source=source
        )
        db_session.add(conversation)
        db_session.commit()
        return conversation


class Objective(Base):
    """
    Represents what the user wants to achieve in the conversation.
    """
    __tablename__ = "objectives"

    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
    conversation_history_id = Column(Integer, ForeignKey("conversation_histories.id"), nullable=False)
    conversation_history = relationship("ConversationHistory", back_populates="objectives")
    description = Column(Text, nullable=False)
    priority = Column(Integer, default=1, nullable=False)  # Allow prioritizing multiple objectives
    
    def __repr__(self) -> str:
        return f'<Objective id: {self.id} priority: {self.priority}>'


class Simulation(Base):
    """
    Represents a simulated conversation branch with potential approaches.
    """
    __tablename__ = "simulations"

    id = Column(Integer, primary_key=True)
    uuid = Column(String(36), default=lambda: str(uuid.uuid4()), unique=True, nullable=False)
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
    conversation_history_id = Column(Integer, ForeignKey("conversation_histories.id"), nullable=False)
    conversation_history = relationship("ConversationHistory", back_populates="simulations")
    messages = Column(JSON, nullable=False)  # Stores the simulated messages
    description = Column(Text, nullable=True)  # Description of this approach
    evaluation_score = Column(Float, nullable=True)  # Numerical score (1-10)
    evaluation_notes = Column(Text, nullable=True)  # Qualitative assessment
    is_selected = Column(Boolean, default=False, nullable=False)  # Whether this was the chosen approach
    
    def __repr__(self) -> str:
        return f'<Simulation id: {self.id} score: {self.evaluation_score} selected: {self.is_selected}>'

    def select_as_best_approach(self):
        """Mark this simulation as the selected approach and unselect others"""
        # First, unselect all simulations for this conversation
        db_session.query(Simulation)\
            .filter(Simulation.conversation_history_id == self.conversation_history_id)\
            .update({"is_selected": False})
        
        # Then select this one
        self.is_selected = True
        db_session.commit()
        
        # Create or update the SelectedApproach record
        selected_approach = SelectedApproach.query.filter_by(conversation_history_id=self.conversation_history_id).first()
        if selected_approach:
            selected_approach.simulation_id = self.id
            selected_approach.rationale = f"Updated selection to simulation {self.id}"
        else:
            selected_approach = SelectedApproach(
                conversation_history_id=self.conversation_history_id,
                simulation_id=self.id,
                rationale=f"Initial selection of simulation {self.id}"
            )
            db_session.add(selected_approach)
        
        db_session.commit()
        return selected_approach


class SelectedApproach(Base):
    """
    Represents the final selected best approach for a conversation.
    """
    __tablename__ = "selected_approaches"

    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
    conversation_history_id = Column(Integer, ForeignKey("conversation_histories.id"), nullable=False, unique=True)
    conversation_history = relationship("ConversationHistory", backref="selected_approach", uselist=False)
    simulation_id = Column(Integer, ForeignKey("simulations.id"), nullable=False)
    simulation = relationship("Simulation")
    rationale = Column(Text, nullable=True)  # Explanation for why this approach was selected
    
    def __repr__(self) -> str:
        return f'<SelectedApproach id: {self.id} for conversation: {self.conversation_history_id}>'


class Contact(Base):
    """Model representing a contact from the address book"""
    __tablename__ = 'contacts'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    identifier = Column(String(255), nullable=False, index=True)  # Phone or email
    identifier_type = Column(String(50), nullable=False)  # 'phone' or 'email'
    normalized_identifier = Column(String(255), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    created_at = Column(DateTime, default=datetime.datetime.now(datetime.UTC))
    updated_at = Column(DateTime, default=datetime.datetime.now(datetime.UTC), onupdate=datetime.datetime.now(datetime.UTC))
    
    user = relationship('User', back_populates='contacts')
    
    def __repr__(self):
        return f"<Contact {self.name}: {self.identifier}>"
    
    @classmethod
    def normalize_identifier(cls, identifier: str, identifier_type: str) -> str:
        """Normalize the identifier to a standard format"""
        if identifier_type == 'phone':
            return f"phone_{identifier.replace("-", "").replace("+1", "")}"
        elif identifier_type == 'email':
            return f"email_{identifier.lower().strip()}"
        else:
            raise ValueError(f"Invalid identifier type: {identifier_type}")
