from typing import List, Dict, Any, Optional
import json
import os
import time
from dataclasses import dataclass
from src.anthropic_client import anthropic_client
from src.log_chat_messages import log_chat_messages
from src.skills.base import SkillBase
from src.skills.social_stockfish.models import ConversationHistory, Objective, Simulation, SelectedApproach
from src.models import User, db_session
import traceback


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
    def save_conversation_history(cls, 
                                  conversation: List[Dict[str, str]],
                                  title: str,
                                  user_id: int,
                                  objective_text: str = None,
                                  source: str = None) -> ConversationHistory:
        """
        Save conversation history to database
        
        Args:
            conversation: List of conversation messages
            title: Title of the conversation
            user_id: User ID
            objective_text: Objective text
            source: Source of the conversation
            
        Returns:
            ConversationHistory instance
        """
        # Create conversation history
        conv_history = ConversationHistory(
            title=title,
            user_id=user_id,
            messages=conversation,
            description=f"Conversation imported with objective: {objective_text}" if objective_text else None,
            source=source
        )
        
        db_session.add(conv_history)
        db_session.commit()
        
        # Add objective if provided
        if objective_text:
            objective = Objective(
                conversation_history_id=conv_history.id,
                description=objective_text,
                priority=1
            )
            db_session.add(objective)
            db_session.commit()
        
        return conv_history
    
    @classmethod
    def save_simulation(cls,
                        conversation_history_id: int,
                        branch: ConversationBranch,
                        is_selected: bool = False) -> Simulation:
        """
        Save a simulated branch to database
        
        Args:
            conversation_history_id: ID of the conversation history
            branch: ConversationBranch instance
            is_selected: Whether this is the selected branch
        
        Returns:
            Simulation instance
        """
        simulation = Simulation(
            conversation_history_id=conversation_history_id,
            messages=branch.messages,
            description=branch.notes.split("\n\nEVALUATION:")[0] if "\n\nEVALUATION:" in branch.notes else branch.notes,
            evaluation_score=branch.score,
            evaluation_notes=branch.notes.split("\n\nEVALUATION:")[1] if "\n\nEVALUATION:" in branch.notes else None,
            is_selected=is_selected
        )
        
        db_session.add(simulation)
        db_session.commit()
        
        # If this is the selected branch, create a SelectedApproach
        if is_selected:
            selected = SelectedApproach(
                conversation_history_id=conversation_history_id,
                simulation_id=simulation.id,
                rationale="Initial selected approach"
            )
            db_session.add(selected)
            db_session.commit()
        
        return simulation
    
    @classmethod
    def analyze_conversation(cls, conversation_history: List[Dict[str, str]], objective: str, 
                            num_branches: int = 3, branch_depth: int = 2, model: str = None) -> Dict:
        """
        Analyzes a conversation and generates alternative response branches
        
        Args:
            conversation_history: List of conversation history messages between humans
            objective: What you want to achieve with this conversation
            num_branches: Number of alternative approaches to generate
            branch_depth: How many back-and-forth exchanges to simulate
            model: Optional model override
            
        Returns:
            Dictionary containing the analysis and alternative responses
        """
        # Convert the model name if using newer Claude models
        model_mapping = {
            "claude-3-5-haiku-latest": "claude-3-haiku-20240307",
            "claude-3-7-sonnet-latest": "claude-3-sonnet-20240229",
            "claude-3-opus-latest": "claude-3-opus-20240229"
        }
        
        # Use the specified model or map to compatible model
        if not model:
            model = "claude-3-sonnet-20240229"  # Default model
        elif model in model_mapping:
            model = model_mapping[model]  # Map new model names to compatible ones
        
        print(f"Using model: {model} for conversation analysis")
        
        # Format the human conversation for analysis
        # This transforms the human-to-human conversation into a format suitable for analysis
        formatted_conversation = cls._format_human_conversation(conversation_history)
        
        try:
            # Step 1: Generate alternative approaches
            prompt = cls._create_approach_prompt(formatted_conversation, objective, num_branches)
            print(f"Prompt: {prompt}")
            approaches_response = anthropic_client.messages.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2048
            )
            approaches = cls._parse_approaches(approaches_response)
            
            if not approaches:
                print("Warning: Failed to parse approaches.")
                approaches = [{
                    "approach": "Direct and informative response",
                    "rationale": "Providing clear information is a default approach when specific approaches cannot be generated.",
                    "score": 0.7
                }]
            
            # Limit to requested number of branches
            approaches = approaches[:num_branches]
            
            # Step 2: Generate simulated responses for each approach
            detailed_analysis = {"all_approaches": approaches, "simulated_branches": []}
            
            # Generate the best response
            best_approach = approaches[0]
            best_response = cls._generate_response(
                formatted_conversation, 
                best_approach["approach"], 
                model=model
            )
            
            # Simulate conversation branches
            for approach in approaches:
                try:
                    print(f"Simulating branch with approach: {approach['approach'][:50]}...")
                    
                    branch = cls._simulate_conversation_branch(
                        formatted_conversation,
                        approach["approach"],
                        branch_depth,
                        model=model
                    )
                    
                    detailed_analysis["simulated_branches"].append({
                        "approach": approach["approach"],
                        "messages": branch,
                        "score": approach["score"]
                    })
                except Exception as e:
                    print(f"Error simulating branch: {str(e)}")
                    traceback.print_exc()
                    # Add a placeholder for the failed branch
                    detailed_analysis["simulated_branches"].append({
                        "approach": approach["approach"],
                        "messages": [{"role": "assistant", "content": f"[Error simulating this branch: {str(e)}]"}],
                        "score": approach["score"]
                    })
            
            # Generate comparative analysis if we have multiple branches
            if len(detailed_analysis["simulated_branches"]) > 1:
                comparative_analysis = cls._generate_comparative_analysis(
                    formatted_conversation,
                    detailed_analysis["simulated_branches"],
                    objective,
                    model=model
                )
                detailed_analysis["comparative_analysis"] = comparative_analysis
            
            return {
                "best_response": best_response,
                "detailed_analysis": detailed_analysis
            }
        except Exception as e:
            error_msg = f"Error analyzing conversation: {str(e)}"
            traceback.print_exc()
            print(error_msg)
            
            # Return a graceful error response
            return {
                "best_response": f"I encountered an error analyzing this conversation: {str(e)}. Please try again with different parameters or check the console for details.",
                "detailed_analysis": {
                    "all_approaches": [{
                        "approach": "Error occurred",
                        "rationale": f"An error occurred: {str(e)}",
                        "score": 0
                    }],
                    "simulated_branches": [],
                    "error": str(e),
                    "traceback": traceback.format_exc()
                }
            }
    
    @classmethod
    def _format_human_conversation(cls, conversation_history: List[Dict[str, str]]) -> str:
        """
        Formats a human-to-human conversation history for analysis.
        
        This method takes a list of messages from a human conversation (like iMessage)
        and formats it as a single string with clear speaker identification.
        
        Args:
            conversation_history: List of message dictionaries from human conversation
            
        Returns:
            Formatted conversation string for analysis
        """
        # Initialize formatted conversation string
        formatted_text = "The following is a conversation between two people:\n\n"
        
        # Determine if we have proper sender information
        has_sender_info = any('sender' in msg for msg in conversation_history)
        
        # Format each message
        for msg in conversation_history:
            # Get sender name or role
            if has_sender_info and 'sender' in msg:
                speaker = msg['sender']
            elif 'role' in msg and msg['role'] == 'user':
                speaker = "Person A"
            elif 'role' in msg and msg['role'] == 'assistant':
                speaker = "Person B"
            else:
                speaker = "Unknown Speaker"
            
            # Add the message to the formatted text
            content = msg.get('content', '')
            if content:
                formatted_text += f"{speaker}: {content}\n\n"
        
        return formatted_text

    @classmethod
    def _create_approach_prompt(cls, formatted_conversation: str, objective: str, num_branches: int) -> str:
        """
        Creates a prompt for generating conversation approaches.
        
        Args:
            formatted_conversation: Formatted conversation text
            objective: The conversation objective
            
        Returns:
            Complete prompt for the AI
        """
        prompt = f"""I need your help analyzing a real conversation between humans and suggesting different approaches for how one person might respond next.

{formatted_conversation}

Your task is to suggest {num_branches} different approaches for how one of the people could respond next, considering this objective: "{objective}"

For each approach:
1. Describe the approach in 1-2 sentences
2. Explain the rationale behind this approach
3. Rate how effective you think this approach would be (0-10 scale)

Present your response in this JSON format:
{{
  "approaches": [
    {{
      "approach": "Description of approach 1",
      "rationale": "Explanation of why this approach might be effective",
      "score": 8.5 // Score between 0 and 10
    }},
    ...additional approaches...
  ]
}}

Ensure your approaches are creative, diverse, and ordered from most to least promising.
"""
        return prompt

    @classmethod
    def _parse_approaches(cls, response):
        """
        Parses the approaches from the model's response.
        
        Args:
            response: The response from the LLM
            
        Returns:
            List of approach dictionaries
        """
        try:
            # Extract the JSON part of the response
            if hasattr(response, 'content'):
                content = response.content[0].text
            else:
                content = response
            
            # Try to find JSON block
            import re
            json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
            
            if json_match:
                json_str = json_match.group(1)
            else:
                # Look for JSON-like structure without markdown
                json_match = re.search(r'(\{.*\})', content, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1)
                else:
                    # Just try with the whole content
                    json_str = content
            
            # Parse the JSON
            import json
            data = json.loads(json_str)
            
            # Extract approaches
            approaches = data.get("approaches", [])
            
            # Normalize scores to 0-1 range if they're on a 0-10 scale
            for approach in approaches:
                if "score" in approach and approach["score"] > 1:
                    approach["score"] = approach["score"] / 10.0
            
            return approaches
        except Exception as e:
            print(f"Error parsing approaches: {str(e)}")
            traceback.print_exc()
            return []

    @classmethod
    def _generate_response(cls, formatted_conversation: str, approach: str, model: str = None) -> str:
        """
        Generates a response using the specified approach.
        
        Args:
            formatted_conversation: Formatted conversation text
            approach: The approach to use for generating the response
            model: Optional model override
            
        Returns:
            Generated response
        """
        prompt = f"""Based on this conversation:

{formatted_conversation}

Please generate the next message in the conversation, following this approach:
{approach}

Generate only the text of the message, without any additional explanations or notes.
"""
        
        response = anthropic_client.messages.create(
            model=model or "claude-3-sonnet-20240229",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024
        )
        
        return response.content[0].text

    @classmethod
    def _simulate_conversation_branch(cls, formatted_conversation: str, approach: str, 
                                     branch_depth: int, model: str = None) -> List[Dict[str, str]]:
        """
        Simulates a conversation branch with multiple back-and-forth exchanges.
        
        Args:
            formatted_conversation: Formatted conversation text
            approach: The approach to use for the simulation
            branch_depth: Number of exchanges to simulate
            model: Optional model override
            
        Returns:
            List of simulated messages
        """
        # Start with the initial response
        initial_response = cls._generate_response(formatted_conversation, approach, model)
        
        # Initialize the branch with the first response
        branch_messages = [{"role": "assistant", "content": initial_response}]
        
        # Determine who spoke last in the original conversation
        # This helps us figure out who should respond next in our simulation
        conversation_lines = formatted_conversation.strip().split('\n')
        last_speaker_line = None
        for line in reversed(conversation_lines):
            if ':' in line:
                last_speaker_line = line
                break
        
        last_speaker = "Unknown"
        if last_speaker_line:
            last_speaker = last_speaker_line.split(':', 1)[0].strip()
        
        # Build the updated conversation for the next round
        updated_conversation = formatted_conversation + f"\n\n{last_speaker}'s counterpart: {initial_response}\n\n"
        
        # Simulate the specified number of back-and-forth exchanges
        for i in range(branch_depth - 1):
            # Alternate between user and assistant responses
            next_role = "user" if i % 2 == 0 else "assistant"
            
            # Who needs to respond now?
            if next_role == "user":
                prompt = f"""Based on this ongoing conversation:

{updated_conversation}

Generate {last_speaker}'s response to the last message. This should be a realistic response that a person might actually write, considering their previous messages and communication style.

Generate only the text of the message, without any additional explanations or notes.
"""
            else:
                prompt = f"""Based on this ongoing conversation:

{updated_conversation}

Generate {last_speaker}'s counterpart's response to the last message, following this approach:
{approach}

Generate only the text of the message, without any additional explanations or notes.
"""
            
            # Generate the next message
            response = anthropic_client.messages.create(
                model=model or "claude-3-sonnet-20240229",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1024
            )
            
            next_message = response.content[0].text
            
            # Add message to the branch
            branch_messages.append({"role": next_role, "content": next_message})
            
            # Update the conversation for the next round
            if next_role == "user":
                updated_conversation += f"{last_speaker}: {next_message}\n\n"
            else:
                updated_conversation += f"{last_speaker}'s counterpart: {next_message}\n\n"
        
        return branch_messages

    @classmethod
    def _generate_comparative_analysis(cls, formatted_conversation: str, 
                                      branches: List[Dict], objective: str, 
                                      model: str = None) -> str:
        """
        Generates a comparative analysis of multiple conversation branches.
        
        Args:
            formatted_conversation: Formatted conversation text
            branches: List of simulated branches
            objective: The conversation objective
            model: Optional model override
            
        Returns:
            Comparative analysis text
        """
        # Format the branches for analysis
        branches_text = ""
        
        for i, branch in enumerate(branches):
            approach = branch.get("approach", f"Approach {i+1}")
            messages = branch.get("messages", [])
            
            branches_text += f"### Branch {i+1}: {approach}\n\n"
            
            # Add the messages
            for msg in messages:
                role = "Assistant" if msg["role"] == "assistant" else "User"
                branches_text += f"{role}: {msg['content']}\n\n"
            
            branches_text += "---\n\n"
        
        # Create the analysis prompt
        prompt = f"""Based on this conversation:

{formatted_conversation}

I've simulated different approaches for continuing the conversation:

{branches_text}

The objective for this conversation is: "{objective}"

Please provide a comparative analysis of these different approaches:
1. Which approach is most likely to achieve the objective and why?
2. What are the key strengths and weaknesses of each approach?
3. How might each approach be received by the other person?
4. Which approach would you recommend and why?

Format your analysis with clear headings and concise explanations.
"""
        
        # Generate the analysis
        response = anthropic_client.messages.create(
            model=model or "claude-3-sonnet-20240229",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2048
        )
        
        return response.content[0].text