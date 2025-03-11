from typing import List, Dict, Any, Optional
from src.custom_types import SemanticContext
from src.anthropic_client import anthropic_client
from src.skills.social_stockfish.social_stockfish_skill import SocialStockfishSkill

class SocialStockfishConversation(SemanticContext):
    """Conversation implementation for Social Stockfish"""
    
    def __init__(self, 
                objective: str = "Build rapport and maintain a positive, engaging conversation",
                num_branches: int = 3,
                branch_depth: int = 1):
        """Initialize a Social Stockfish conversation
        
        Args:
            objective: The conversation objective
            num_branches: Number of alternative branches to generate
            branch_depth: How many exchanges to simulate in each branch
        """
        self.name = "Social Stockfish"
        self.description = "AI-powered conversation analysis and optimization"
        self.system_prompt = f"""You are using Social Stockfish, an AI-powered conversation simulator
that helps optimize social interactions toward specific objectives.

Current objective: {objective}

Social Stockfish analyzes multiple possible conversation paths and recommends optimal responses.
"""
        self.thread = []
        self.objective = objective
        self.num_branches = num_branches
        self.branch_depth = branch_depth
        
    def init_thread(self, others: List[SemanticContext] = None) -> List[Dict[str, str]]:
        """Initialize a new chat thread with this context"""
        thread = [{"role": "system", "content": self.system_prompt}]
        self.thread = thread
        return thread
    
    def on_new_message(self, thread: List[Dict[str, str]], message: Dict[str, str]) -> List[Dict[str, str]]:
        """Handle a new message being added to the thread"""
        self.thread = thread
        return thread
    
    def get_ai_response(self, model: str = "claude-3-sonnet-20240229", max_tokens: int = 4000) -> Dict[str, Any]:
        """Get an optimized response using Social Stockfish analysis
        
        Returns:
            Dictionary with best response and analysis
        """
        # Create a copy of the thread for analysis
        if not self.thread:
            self.init_thread()
            
        analysis_thread = self.thread.copy()
        
        # Run Social Stockfish analysis
        recommendations = SocialStockfishSkill.analyze_conversation(
            conversation=analysis_thread,
            objective=self.objective,
            num_branches=self.num_branches,
            branch_depth=self.branch_depth
        )
        
        # Add the best response to the conversation
        best_response = recommendations["best_response"]
        self.thread.append({"role": "assistant", "content": best_response})
        
        # Return the response and analysis
        return {
            "content": best_response,
            "analysis": recommendations
        }