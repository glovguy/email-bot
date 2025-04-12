from typing import List, Dict, Union, TypedDict
from src.anthropic_client import anthropic_client
from src.skills.base import SkillBase
# from src.skills.social_stockfish.models import Contact
import traceback
import src.skills.social_stockfish.prompts as prompts
from src.skills.social_stockfish.imessage_import import MessageDict


class ApproachEvaluationDict(TypedDict):
    """Evaluation of an approach."""
    success_likelihood: float
    constraint_compliance: float
    side_effects: str # possible side effects of the approach worth calling out

class SimulatedConversationNodeDict(TypedDict):
    """A node of a simulated conversation branch. Contains full conversation history of the simulated branch and score of that node."""
    full_simulated_messages: List[MessageDict]
    new_simulated_messages: List[MessageDict]
    evaluation: ApproachEvaluationDict

class ApproachDict(TypedDict):
    """A particular approach to a conversation for accomplishing a goal."""
    description: str
    rationale: str
    success_likelihood: float
    first_message: str
    simulated_conversation_nodes: List[SimulatedConversationNodeDict]

class DetailedAnalysisDict(TypedDict):
    """Detailed analysis of conversation approaches."""
    approaches: List[ApproachDict]

class AnalysisErrorDict(TypedDict):
    """Error information when analysis fails."""
    approaches: List[ApproachDict]
    error: str
    traceback: str


class SocialStockfishSkill(SkillBase):
    """
    Social Stockfish: A skill for simulating and analyzing conversation branches
    to find optimal social responses.
    """

    def __init__(self,
                 conversation_history: List[MessageDict],
                 model: str = "claude-3-7-sonnet-latest",
                 contacts_data: Dict[str, str] = {} # key is the contact identifier, value is the contact name
                ):
        self.model = model
        self.conversation_history = conversation_history
        self.contacts_data = contacts_data
        self.formatted_conversation_history = self._format_human_conversation(
            self.conversation_history
        )

    def analyze_conversation(self,
                             objective: str,
                             constraints: str | None = "No constraints provided. Act with civility and decency.",
                             num_branches: int = 3,
                             branch_depth: int = 2
                            ) -> Union[DetailedAnalysisDict, AnalysisErrorDict]:
        """
        Analyzes a conversation and generates alternative response branches

        Args:
            objective: What you want to achieve with this conversation
            constraints: Relevant constraints to consider
            num_branches: Number of alternative approaches to generate
            branch_depth: How many back-and-forth exchanges to simulate
            model: Optional model override

        Returns:
            Dictionary containing the analysis and alternative responses
        """
        self.objective = objective
        self.constraints = constraints

        try:
            # Step 1: Generate alternative approaches
            approaches_user_prompt = prompts.CREATE_APPROACHES_USER_PROMPT.format(
                formatted_conversation=self.formatted_conversation_history,
                num_branches=num_branches,
                objective=objective,
                constraints=constraints,
            )
            response = anthropic_client.messages.create(
                model=self.model,
                messages=[{"role": "user", "content": approaches_user_prompt}],
                system=prompts.CREATE_APPROACHES_SYSTEM_PROMPT,
                max_tokens=2048,
                tools=prompts.CREATE_APPROACHES_TOOLS,
                tool_choice=prompts.CREATE_APPROACHES_TOOL_CONFIG
            )
            tool_response = None
            for content in response.content:
                if content.type == "tool_use" and content.name == "create_approaches":
                    tool_response = content.input
                    break
            if tool_response is None:
                raise Exception("No valid tool response received")
            approaches: List[ApproachDict] = [
                {
                    "description": approach["description"],
                    "rationale": approach["description"],
                    "success_likelihood": approach["success_likelihood"],
                    "first_message": approach["first_message"],
                    "simulated_conversation_nodes": [],
                } 
                for approach in tool_response["approaches"][:num_branches]
            ]

            # Step 2: Generate simulated responses for each approach
            for approach in approaches:
                try:
                    print(f"Simulating branch with approach: {approach['description']}")
                    
                    simulation_nodes = self._simulate_conversation_branch(
                        approach,
                        branch_depth,
                    )
                    approach["simulated_conversation_nodes"] = simulation_nodes
                    branch_terminal_evaluation = simulation_nodes[-1]["evaluation"]
                    if branch_terminal_evaluation["constraint_compliance"]:
                        approach["success_likelihood"] = branch_terminal_evaluation["success_likelihood"]
                    else:
                        approach["success_likelihood"] = 0.0
                except Exception as e:
                    # will remove after testing
                    print(f"Error simulating branch: {str(e)}")
                    traceback.print_exc()

            return {
                "approaches": approaches
            }
        except Exception as e:
            error_msg = f"Error analyzing conversation: {str(e)}"
            traceback.print_exc()
            print(error_msg)
            return {
                "approaches": [],
                "error": error_msg,
                "traceback": traceback.format_exc()
            }

    def evaluate_branch(self, simulated_messages: List[MessageDict]) -> ApproachEvaluationDict:
        """
        Evaluate conversation branches and assign scores based on effectiveness.

        Args:
            branch: The conversation branch to evaluate

        Returns:
            The evaluation of the branch as an ApproachEvaluationDict
        """
        formatted_branch = self._format_human_conversation(
            [*self.conversation_history, *simulated_messages]
        )
        eval_prompt = prompts.EVAL_APPROACH_USER_PROMPT.format(
            formatted_branch=formatted_branch,
            objective=self.objective,
            constraints=self.constraints,
        )
        try:
            response = anthropic_client.messages.create(
                model=self.model,
                system=prompts.EVAL_APPROACH_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": eval_prompt}],
                max_tokens=1024,
                tools=prompts.EVAL_APPROACH_TOOLS,
                tool_choice=prompts.EVAL_APPROACH_TOOL_CONFIG
            )
            tool_response = None
            for content in response.content:
                if content.type == "tool_use" and content.name == "evaluate_approach":
                    tool_response = content.input
                    break

            if tool_response is None:
                raise Exception("No valid tool response received")
            return {
                "constraint_compliance": tool_response["constraint_compliance"],
                "success_likelihood": tool_response["success_likelihood"],
                "side_effects": tool_response.get("side_effects", None)
            }
        except Exception as e:
            traceback.print_exc()
            print(f"Error evaluating branch: {str(e)}")
            print(f"response: {response if 'response' in locals() else '(no response)'}") # type: ignore
            print("returning default values")
            
            # Return default values if evaluation fails
            return {
                "success_likelihood": 0.5,  # Neutral likelihood
                "constraint_compliance": True,  # Assume compliant by default
                "side_effects": f"Error during evaluation: {str(e)}"
            }

    def _format_human_conversation(self, branch_messages: List[MessageDict], include_end_tag: bool = True) -> str:
        """
        Formats a human-to-human conversation history for analysis.

        This method takes a list of messages from a human conversation (like iMessage)
        and formats it as a single string with clear speaker identification.

        Args:
            branch_messages: List of message dictionaries from human conversation, including simulated messages

        Returns:
            Formatted conversation string for analysis
        """
        formatted_text = "The following is a text conversation:\n\n"

        for msg in branch_messages:
            sender_name = msg.get('sender_name')
            content = msg.get('content', None)
            formatted_text += f"<message>\n<sender_name>{sender_name}</sender_name>\n<content>\n{content}\n</content>\n</message>\n\n"

        end_tag = "\n</messages>" if include_end_tag else ""
        return f"<messages>\n{formatted_text}{end_tag}"

    def _simulate_conversation_branch(
            self,
            approach: ApproachDict,
            branch_depth: int
        ) -> List[SimulatedConversationNodeDict]:
        """
        Simulates a conversation branch with multiple back-and-forth exchanges.

        Args:
            approach: The approach to use for the simulation
            branch_depth: Number of exchanges to simulate

        Returns:
            List of simulated conversation nodes
        """
        simulated_messages: List[MessageDict] = [
            {
                "sender_name": "Me",
                "content": approach["first_message"]
            }
        ]
        simulated_conversation_nodes: List[SimulatedConversationNodeDict] = []

        for _ in range(branch_depth - 1):
            generated_messages = self.simulate_next_messages(
                [*self.conversation_history, *simulated_messages]
            )
            simulated_messages.extend(generated_messages)
            next_decision_messages = self.make_next_decision(
                simulated_messages,
                approach
            )
            simulated_messages.extend(next_decision_messages)
            evaluation = self.evaluate_branch(simulated_messages)
            simulated_conversation_nodes.append({
                "full_simulated_messages": simulated_messages,
                "new_simulated_messages": [*generated_messages, *next_decision_messages],
                "evaluation": evaluation
            })

        return simulated_conversation_nodes

    def simulate_next_messages(self, simulated_conversation_history: List[MessageDict]) -> List[MessageDict]:
        """
        Simulates the next non-Me messages in the conversation.
        
        Uses tool calling to ensure responses are properly formatted in XML.
        """
        try:
            formatted_conversation = self._format_human_conversation(
                simulated_conversation_history,
                include_end_tag=False
            )
            prompt = prompts.SIM_MESSAGE_USER.format(
                formatted_conversation=formatted_conversation
            )
            response = anthropic_client.messages.create(
                model=self.model,
                system=prompts.SIM_MESSAGE_SYS,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1024,
                tools=prompts.SIM_MESSAGE_TOOLS,
                tool_choice=prompts.SIM_MESSAGE_TOOL_CONFIG
            )
            tool_response = None
            for content in response.content:
                if content.type == "tool_use" and content.name == "generate_response":
                    tool_response = content.input
                    break
            if tool_response is None:
                raise Exception("No valid tool response received")
            return [{
                "sender_name": tool_response["sender_name"],
                "content": tool_response["content"]
            }]
            
        except Exception as e:
            print(f"Error in simulate_next_messages: {str(e)}")
            traceback.print_exc()
            
            # Return a generic message if everything fails
            raise Exception(f"Error in simulate_next_messages: {str(e)}")

    def make_next_decision(
            self,
            simulated_messages: List[MessageDict],
            approach: ApproachDict,
        ) -> List[MessageDict]:
        """
        Makes the next decision in the conversation based on the specified approach.

        This method generates the next response from the "Me" perspective in the conversation,
        following the given approach strategy.

        Args:
            conversation_history: The original conversation history
            simulated_messages: Messages that have been simulated so far
            approach: The approach strategy to follow
            model: Optional model override

        Returns:
            List containing the next message from the "Me" perspective
        """
        # Format all messages for context
        branch_messages = [*self.conversation_history, *simulated_messages]
        formatted_conversation = self._format_human_conversation(
            branch_messages, 
            include_end_tag=False
        )
        prompt = prompts.MAKE_DECISION_USER.format(
            objective=self.objective,
            approach_description=approach["description"],
            rationale=approach["rationale"],
            constraints=self.constraints,
            formatted_conversation=formatted_conversation
        )

        try:
            response = anthropic_client.messages.create(
                model=self.model,
                system=prompts.MAKE_DECISION_SYS,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1024,
                tools=prompts.MAKE_DECISION_TOOLS,
                tool_choice=prompts.MAKE_DECISION_TOOL_CONFIG
            )
            tool_response = None
            for content in response.content:
                if content.type == "tool_use" and content.name == "respond_as_me":
                    tool_response = content.input
                    break
            if tool_response is None:
                raise Exception("No valid tool response received")
            print(f"Response thoughts: {tool_response['thoughts']}")
            return [{
                "sender_name": "Me",
                "content": tool_response["message_content"]
            }]
            
        except Exception as e:
            print(f"Error in make_next_decision: {str(e)}")
            traceback.print_exc()
            raise Exception(f"Error in make_next_decision: {str(e)}")

    def _generate_comparative_analysis(self, approaches: List[ApproachDict]) -> str:
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
        branches_text = ""

        for i, approach in enumerate(approaches):
            approach_description = approach.get("description", f"Approach {i+1}")
            approach_rationale = approach.get("rationale", f"Approach {i+1}")

            final_simulated_node = approach["simulated_conversation_nodes"][-1]
            formatted_conversation = self._format_human_conversation(final_simulated_node["full_simulated_messages"])
            branches_text += f"""### Branch {i+1}
<approach_description>
{approach_description}
</approach_description>
<approach_rationale>
{approach_rationale}
</approach_rationale>

<simulated_conversation>
{formatted_conversation}
</simulated_conversation>

Success Likelihood: {final_simulated_node["evaluation"]["success_likelihood"]}
Constraint Compliance: {final_simulated_node["evaluation"]["constraint_compliance"]}
Side Effects: {final_simulated_node["evaluation"]["side_effects"]}
"""

        prompt = f"""Based on this conversation:

<conversation_history>
{self.formatted_conversation_history}
</conversation_history>

I've simulated different approaches for continuing the conversation:

{branches_text}

The objective for this conversation is:
<objective>
{self.objective}
</objective>

and the constraints are:
<constraints>
{self.constraints}
</constraints>

Please provide a comparative analysis of these different approaches:
1. Which approach is most likely to achieve the objective and why?
2. What are the key strengths and weaknesses of each approach?
3. How might each approach be received by the other person?
4. Which approach would you recommend and why?

Format your analysis with clear headings and concise explanations.
"""

        # Generate the analysis
        response = anthropic_client.messages.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2048
        )

        try:
            return response.content[0].text
        except Exception as e:
            print(f"Error in _generate_comparative_analysis: {str(e)}")
            traceback.print_exc()
            try:
                return response.content
            except Exception as e:
                print(f"Error in _generate_comparative_analysis: {str(e)}")
                traceback.print_exc()
                return "Error in _generate_comparative_analysis"
