from typing import List, Dict
from abc import ABC, abstractmethod

class Conversation(ABC):
    """Base class for conversations with AI assistants"""
    
    def __init__(self, name: str, description: str, system_prompt: str):
        self.name = name
        self.description = description
        self.system_prompt = system_prompt
        self.thread = self.create_initial_thread()
    
    def create_initial_thread(self) -> List[Dict[str, str]]:
        """Create the initial thread with system prompt"""
        return [{"role": "system", "content": self.system_prompt}]
    
    def reset(self) -> None:
        """Reset the conversation to its initial state"""
        self.thread = self.create_initial_thread()
    
    def add_message(self, role: str, content: str) -> None:
        """Add a message to the conversation thread"""
        self.thread.append({"role": role, "content": content})
    
    def get_messages(self, ui_only: bool = True) -> List[Dict[str, str]]:
        """Get conversation messages
        
        Args:
            ui_only: If True, exclude system messages
        """
        if ui_only:
            return [msg for msg in self.thread if msg["role"] != "system"]
        return self.thread.copy()
    
    @abstractmethod
    def get_ai_response(self, **kwargs) -> str:
        """Get a response from the AI model based on the current thread"""
        pass


class PersonaConversation(Conversation):
    """Conversation implementation for a persona"""
    
    def __init__(self, persona):
        """Initialize a conversation with the given persona
        
        Args:
            persona: A Persona DB model instance
        """
        super().__init__(
            name=persona.name,
            description=persona.description,
            system_prompt=persona.system_prompt
        )
        self.persona_id = persona.id
    
    def get_ai_response(self, **kwargs) -> str:
        """Get a response from Anthropic Claude based on the current thread"""
        from src.anthropic_client import anthropic_client
        
        model = kwargs.get("model", "claude-3-sonnet-20240229")
        max_tokens = kwargs.get("max_tokens", 1024)
        
        response = anthropic_client.messages.create(
            model=model,
            max_tokens=max_tokens,
            messages=self.thread
        )
        content = response.content[0].text
        self.add_message("assistant", content)
        return content
