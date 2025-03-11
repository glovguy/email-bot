from typing import List, Dict, Any, Optional
import json
import os
import time
from dataclasses import dataclass
from src.anthropic_client import anthropic_client
from src.log_chat_messages import log_chat_messages
from src.skills.base import SkillBase
from src.custom_types import SemanticContext


@dataclass
class ConversationBranch:
    """Represents a branch in the conversation tree for Social Stockfish"""
    messages: List[Dict[str, str]]
    score: float = 0.0
    notes: str = ""
    
    def add_message(self, role: str, content: str) -> None:
        """Add a message to this branch"""
        self.messages.append({"role": role, "content": content})


class SocialStockfishSkill(SkillBase):
    """
    Social Stockfish: A skill for simulating and analyzing conversation branches
    to find optimal social responses.
    """
    
    @classmethod
    def import_conversation(cls, file_path: str) -> List[Dict[str, str]]:
        """
        Import conversation data from a text or JSON file.
        
        Args:
            file_path: Path to the conversation file
            
        Returns:
            List of message dictionaries
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Conversation file not found: {file_path}")
            
        if file_path.endswith('.json'):
            with open(file_path, 'r', encoding='utf-8') as file:
                return json.load(file)
        else:
            # Assume text format with "=== role ===" separators
            messages = []
            current_role = None
            current_content = []
            
            with open(file_path, 'r', encoding='utf-8') as file:
                lines = file.readlines()
                
            for line in lines:
                if line.startswith('=== ') and line.endswith(' ===\n'):
                    # Save previous message if exists
                    if current_role and current_content:
                        messages.append({
                            "role": current_role.lower(),
                            "content": ''.join(current_content).strip()
                        })
                        current_content = []
                    
                    # Extract new role
                    current_role = line.strip('=== \n')
                else:
                    if current_role:
                        current_content.append(line)
            
            # Add the last message
            if current_role and current_content:
                messages.append({
                    "role": current_role.lower(),
                    "content": ''.join(current_content).strip()
                })
                
            return messages
    
    @classmethod
    def create_conversation_with_objective(cls, messages: List[Dict[str, str]], objective: str) -> List[Dict[str, str]]:
        """
        Create a conversation thread with a specific objective.
        
        Args:
            messages: Existing conversation messages
            objective: The objective for the conversation
            
        Returns:
            New conversation thread with objective in system prompt
        """
        system_prompt = f"""You are participating in a social conversation with a specific objective: {objective}
        
Your goal is to respond in a way that achieves this objective while maintaining a natural, authentic conversation.
Be strategic in your responses while remaining true to context and social norms."""
        
        # Create new thread with system prompt
        thread = [{"role": "system", "content": system_prompt}]
        
        # Add original messages, filtering out any system messages
        for msg in messages:
            if msg["role"] != "system":
                thread.append(msg)
                
        return thread
    
    @classmethod
    def generate_branches(cls, 
                          base_thread: List[Dict[str, str]], 
                          num_branches: int = 3,
                          branch_depth: int = 2,
                          model: str = "claude-3-sonnet-20240229") -> List[ConversationBranch]:
        """
        Generate multiple conversation branches using forest-of-thought approach.
        
        Args:
            base_thread: The conversation thread to branch from
            num_branches: Number of alternative branches to generate
            branch_depth: How many exchanges to simulate in each branch
            model: The model to use for generation
            
        Returns:
            List of ConversationBranch objects
        """
        branches = []
        
        # Add branch instruction to the system prompt
        branch_system_prompt = base_thread[0]["content"] + f"""

IMPORTANT: Generate {num_branches} different responses that represent distinct conversational approaches.
Each approach should be thoughtfully different, exploring various social strategies.
"""
        
        branching_thread = base_thread.copy()
        branching_thread[0]["content"] = branch_system_prompt
        
        # Generate initial branches
        branch_instruction = f"""Please generate {num_branches} different responses to the last message in this conversation.
Each response should represent a distinct approach or strategy for achieving the conversation objective.
Format each response as:

APPROACH 1: [Brief description of strategy]
RESPONSE 1: [The actual response text]

APPROACH 2: [Brief description of strategy]
RESPONSE 2: [The actual response text]

... and so on for {num_branches} approaches.
"""
        
        branching_thread.append({"role": "user", "content": branch_instruction})
        
        response = anthropic_client.messages.create(
            model=model,
            messages=branching_thread,
            max_tokens=2000
        )
        
        branch_text = response.content[0].text
        
        # Parse branch responses
        branch_approaches = []
        branch_responses = []
        
        for i in range(1, num_branches + 1):
            approach_marker = f"APPROACH {i}:"
            response_marker = f"RESPONSE {i}:"
            
            if approach_marker in branch_text and response_marker in branch_text:
                approach_start = branch_text.find(approach_marker) + len(approach_marker)
                approach_end = branch_text.find(response_marker)
                response_start = branch_text.find(response_marker) + len(response_marker)
                
                if i < num_branches:
                    next_marker = f"APPROACH {i+1}:"
                    response_end = branch_text.find(next_marker)
                else:
                    response_end = len(branch_text)
                
                approach = branch_text[approach_start:approach_end].strip()
                response_text = branch_text[response_start:response_end].strip()
                
                branch_approaches.append(approach)
                branch_responses.append(response_text)
        
        # Create branch objects
        for i in range(len(branch_responses)):
            branch = ConversationBranch(messages=base_thread.copy())
            branch.add_message("assistant", branch_responses[i])
            branch.notes = branch_approaches[i]
            branches.append(branch)
        
        # Simulate conversation for each branch to specified depth
        for branch in branches:
            for _ in range(branch_depth - 1):  # -1 because we already added one response
                # Generate user reply
                user_sim_thread = branch.messages.copy()
                user_sim_thread[0]["content"] += "\n\nYou are now simulating a realistic user response to the last message."
                
                user_response = anthropic_client.messages.create(
                    model=model,
                    messages=user_sim_thread,
                    max_tokens=500
                )
                
                user_text = user_response.content[0].text
                branch.add_message("user", user_text)
                
                # Generate assistant reply
                assistant_response = anthropic_client.messages.create(
                    model=model,
                    messages=branch.messages,
                    max_tokens=1000
                )
                
                assistant_text = assistant_response.content[0].text
                branch.add_message("assistant", assistant_text)
        
        return branches
    
    @classmethod
    def evaluate_branches(cls, 
                          branches: List[ConversationBranch], 
                          objective: str,
                          model: str = "claude-3-opus-20240229") -> List[ConversationBranch]:
        """
        Evaluate conversation branches and assign scores based on effectiveness.
        
        Args:
            branches: List of conversation branches to evaluate
            objective: The conversation objective
            model: The model to use for evaluation
            
        Returns:
            Branches with scores updated
        """
        for i, branch in enumerate(branches):
            eval_system_prompt = f"""You are evaluating the effectiveness of a conversation branch 
in achieving a specific objective: {objective}

Analyze this conversation carefully and rate it on a scale of 0.0 to 10.0 based on:
1. How well it achieves the stated objective
2. Naturalness and authenticity of the conversation
3. Strategic effectiveness
4. Potential for positive outcomes

Provide only a single decimal number as your rating (e.g., 7.5) and a brief explanation.
"""
            
            eval_messages = [
                {"role": "system", "content": eval_system_prompt},
                {"role": "user", "content": f"Please evaluate this conversation branch:\n\n{json.dumps(branch.messages[1:], indent=2)}"}
            ]
            
            response = anthropic_client.messages.create(
                model=model,
                messages=eval_messages,
                max_tokens=500
            )
            
            eval_text = response.content[0].text
            
            # Extract score from response
            try:
                # First try to find a decimal number in the text
                import re
                score_match = re.search(r'(\d+\.\d+)', eval_text)
                if score_match:
                    branch.score = float(score_match.group(1))
                else:
                    # Try to find any number
                    score_match = re.search(r'(\d+)', eval_text)
                    if score_match:
                        branch.score = float(score_match.group(1))
                    else:
                        # Default fallback
                        branch.score = 5.0
            except:
                branch.score = 5.0
                
            # Update notes with evaluation
            branch.notes += f"\n\nEVALUATION: {eval_text}"
        
        # Sort branches by score (highest first)
        return sorted(branches, key=lambda b: b.score, reverse=True)
    
    @classmethod
    def get_recommendations(cls, 
                            branches: List[ConversationBranch], 
                            objective: str,
                            detailed: bool = True) -> Dict[str, Any]:
        """
        Generate recommendations based on the evaluated branches.
        
        Args:
            branches: Evaluated conversation branches
            objective: The conversation objective
            detailed: Whether to include detailed analysis
            
        Returns:
            Dictionary containing recommendations and analysis
        """
        if not branches:
            return {"error": "No branches provided for analysis"}
        
        # Get best branch
        best_branch = branches[0]
        
        # Get next best response
        best_response = best_branch.messages[next(i for i, m in enumerate(best_branch.messages) 
                                                  if m["role"] == "assistant")]
        
        # Create recommendation summary
        recommendation = {
            "objective": objective,
            "best_response": best_response["content"],
            "score": best_branch.score,
            "analysis": best_branch.notes.split("\n\nEVALUATION:")[0] if "\n\nEVALUATION:" in best_branch.notes else best_branch.notes
        }
        
        # Add detailed analysis if requested
        if detailed:
            # Generate comparison of approaches
            all_approaches = [{"score": b.score, "approach": b.notes.split("\n\nEVALUATION:")[0]} 
                             for b in branches]
            
            # Get insights from the model about the different approaches
            insight_system_prompt = f"""You are analyzing multiple conversation approaches for achieving 
an objective: {objective}

Compare these different approaches and extract key insights about what makes certain 
approaches more effective than others. Be concise and practical in your analysis.
"""
            
            insight_messages = [
                {"role": "system", "content": insight_system_prompt},
                {"role": "user", "content": f"Please analyze these different conversational approaches:\n\n{json.dumps(all_approaches, indent=2)}"}
            ]
            
            response = anthropic_client.messages.create(
                model="claude-3-sonnet-20240229",
                messages=insight_messages,
                max_tokens=1000
            )
            
            comparative_analysis = response.content[0].text
            
            recommendation["detailed_analysis"] = {
                "comparative_analysis": comparative_analysis,
                "all_approaches": all_approaches,
                "alternative_responses": [
                    {"score": b.score, "response": b.messages[next(i for i, m in enumerate(b.messages) if m["role"] == "assistant")]["content"]}
                    for b in branches[1:]  # Skip the best one which is already included
                ]
            }
            
            # Log the analysis for future reference
            timestamp = int(time.time() * 1000)
            log_filename = f"social_stockfish_{timestamp}.json"
            log_path = os.path.join("chat_logs", log_filename)
            
            with open(log_path, 'w', encoding='utf-8') as f:
                json.dump({
                    "objective": objective,
                    "branches": [
                        {
                            "score": b.score,
                            "notes": b.notes,
                            "messages": b.messages[1:]  # Skip system message
                        }
                        for b in branches
                    ],
                    "comparative_analysis": comparative_analysis
                }, f, indent=2)
            
            recommendation["log_file"] = log_path
        
        return recommendation
    
    @classmethod
    def analyze_conversation(cls, 
                            conversation: List[Dict[str, str]] = None,
                            conversation_file: Optional[str] = None,
                            objective: str = "Build rapport and maintain a positive, engaging conversation",
                            num_branches: int = 3,
                            branch_depth: int = 2) -> Dict[str, Any]:
        """
        Main method to analyze a conversation and provide optimal response strategies.
        
        Args:
            conversation: List of conversation messages
            conversation_file: File path to load conversation from
            objective: The conversation objective
            num_branches: Number of alternative branches to generate
            branch_depth: How many exchanges to simulate in each branch
            
        Returns:
            Dictionary containing recommendations and analysis
        """
        # Load conversation if file provided
        if conversation_file and not conversation:
            conversation = cls.import_conversation(conversation_file)
        
        if not conversation:
            return {"error": "No conversation provided"}
        
        # Create conversation with objective
        thread = cls.create_conversation_with_objective(conversation, objective)
        
        # Generate branches
        branches = cls.generate_branches(
            thread, 
            num_branches=num_branches,
            branch_depth=branch_depth
        )
        
        # Evaluate branches
        evaluated_branches = cls.evaluate_branches(branches, objective)
        
        # Generate recommendations
        recommendations = cls.get_recommendations(evaluated_branches, objective)
        
        return recommendations


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
        self.thread = self.create_initial_thread()
        self.objective = objective
        self.num_branches = num_branches
        self.branch_depth = branch_depth
        
    def create_initial_thread(self) -> List[Dict[str, str]]:
        """Create the initial thread with system prompt"""
        return [{"role": "system", "content": self.system_prompt}]
    
    def get_ai_response(self, **kwargs) -> Dict[str, Any]:
        """Get an optimized response using Social Stockfish analysis
        
        Returns:
            Dictionary with best response and analysis
        """
        # Create a copy of the thread for analysis
        analysis_thread = self.thread.copy()
        
        # Run Social Stockfish analysis
        recommendations = SocialStockfishSkill.analyze_conversation(
            conversation=analysis_thread,
            objective=self.objective,
            num_branches=self.num_branches,
            branch_depth=self.branch_depth
        )
        
        # Add the best response to the conversation
        self.thread.append({"role": "assistant", "content": recommendations["best_response"]})
        
        return recommendations