from typing import TypedDict
from typing import Protocol, List, Dict, Any

class SemanticContext(Protocol):
    name: str
    description: str
    system_prompt: str

    def init_thread(self, others: List['SemanticContext']) -> List[Dict[str, str]]:
        """Initialize a new chat thread with this context"""
        ...
        
    def on_new_message(self, thread: List[Dict[str, str]], message: Dict[str, str]) -> List[Dict[str, str]]:
        """Handle a new message being added to the thread"""
        ...
