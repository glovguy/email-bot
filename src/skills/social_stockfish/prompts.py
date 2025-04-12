####################
# create aproaches #
####################

CREATE_APPROACHES_USER_PROMPT = """\
I need your help analyzing a real conversation between humans and suggesting different approaches for how the person labelled "<sender_name>Me</sender_name>" might respond next.

{formatted_conversation}

Your task is to suggest {num_branches} different approaches for how one of the people could respond next, considering this objective:
<objective>
{objective}
</objective>

You should also consider these constraints:
<constraints>
{constraints}
</constraints>

Please suggest different approaches for I could respond next.
"""

CREATE_APPROACHES_TOOLS = [
    {
        "name": "create_approaches",
        "description": "Score the conversation approach based on its likelihood of success",
        "input_schema": {
            "type": "object",
            "properties": {
                "approaches": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "description": {
                                "type": "string",
                                "description": "Instructions for how to follow the approach."
                            },
                            "rationale": {
                                "type": "string",
                                "description": "Explanation of why this approach might or might not be effective."
                            },
                            "success_likelihood": {
                                "type": "number",
                                "description": "How likely this approach is to succeed from 0.0 to 1.0. A value of 0.0 means the approach is impossible to achieve, a value of 1.0 means the approach has already been achieved. A value of 0.5 means that there is a 50% chance the approach will be achieved."
                            },
                            "first_message": {
                                "type": "string",
                                "description": "The first message to send for this approach."
                            }
                        },
                        "required": ["description", "rationale", "success_likelihood", "first_message"]
                    }
                }
            },
            "required": ["approaches"]
        }
    }
]

CREATE_APPROACHES_TOOL_CONFIG = {"type": "tool", "name": "create_approaches"}

CREATE_APPROACHES_SYSTEM_PROMPT = """\
Present your responses using the create_approaches function. Present the approaches as an array of items in this format:

For each approach:
1. Describe the approach briefly. Give instructions for how to follow the approach.
2. Explain the rationale behind this approach. Why might it be effective or not effective?
3. Rate how likely this approach will be effective at accomplishing the objective. (Probability between 0 and 1)
4. Draft the first message to be sent in this response.

Ensure each approach is creative and distinct from each other. We would like breadth rather than depth."""

#######################
# evaluate approaches #
#######################

EVAL_APPROACH_SYSTEM_PROMPT = """\
You are evaluating the effectiveness of a conversation branch in achieving a specific objective.

Analyze this conversation carefully and rate it on a scale of 0.0 to 1.0 based on:
1. success_likelihood: How likely it will achieve the stated objective. This is a probability assessment. A score of 0.0 means the objective is impossible to achieve, a score of 1.0 means the objective has already been achieved. A score of 0.5 means that there is a 50% chance the objective will be achieved.
2. constraint_compliance: Whether the conversation will adheres to the stated constraints. This is a boolean value. A value of True means that the conversation adheres to the constraints, a value of False means that the conversation has violated the constraints, or that it will almost certainly violate the constraints.
3. side_effects: List any potential side effects of the approach worth calling out.

Use the score_approach tool to provide your evaluation in the required format.
"""

EVAL_APPROACH_TOOLS = [
    {
        "name": "evaluate_approach",
        "description": "Score the conversation approach based on effectiveness",
        "input_schema": {
            "type": "object",
            "properties": {
                "success_likelihood": {
                    "type": "number",
                    "description": "Probability of achieving the objective (0.0-1.0)"
                },
                "constraint_compliance": {
                    "type": "boolean",
                    "description": "Whether the conversation adheres to the constraints"
                },
                "side_effects": {
                    "type": "string",
                    "description": "Potential side effects worth noting about this approach"
                }
            },
            "required": ["success_likelihood", "constraint_compliance"]
        }
    }
]

EVAL_APPROACH_TOOL_CONFIG = {"type": "tool", "name": "evaluate_approach"}

EVAL_APPROACH_USER_PROMPT = """\
Please evaluate this conversation branch:

{formatted_branch}

My objective is to:
<objective>
{objective}
</objective>

My constraints are:
<constraints>
{constraints}
</constraints>

First, analyze how likely the objective is to be achieved, whether the conversation adheres to the constraints, and any potential side effects. Then use the score_approach tool to provide your evaluation."""

##########################
# simulate next messages #
##########################

SIM_MESSAGE_SYS = """\
The user will provide context on a conversation that they are having, as well as a series of messages in that conversation. Please continue the conversation with how you expect others will respond.
Please respond only with a continuation of the conversation, without any additional explanations or notes.
Please use the generate_response tool to generate the next message.
Do not make up any information that is not directly provided in the conversation history or shared by the user in the context.
Please use the existing messages as context to mimic the conversation style and decision-making process of those involved."""
    
SIM_MESSAGE_TOOLS = [
    {
        "name": "generate_response",
        "description": "Generate the next message in the conversation from another participant (not 'Me')",
        "input_schema": {
            "type": "object",
            "properties": {
                "sender_name": {
                    "type": "string",
                    "description": "The name or identifier of the person speaking (cannot be 'Me')"
                },
                "content": {
                    "type": "string",
                    "description": "The message content that this person would say in response"
                }
            },
            "required": ["sender_name", "content"]
        }
    }
]

SIM_MESSAGE_TOOL_CONFIG = {"type": "tool", "name": "generate_response"}

SIM_MESSAGE_USER = """\
Based on the below ongoing conversation, continue the conversation with how you expect others will respond.
Generate the next message in this conversation. The goal is to simulate the response of the other person or people in the conversation. This should be a realistic response that a person would actually write, considering their previous messages and communication style.
Generate only a continuation of the messages, without any additional explanations or notes.

{formatted_conversation}

Generate the next message in this conversation from another participant (not 'Me'). This should be a realistic response that reflects how this person would actually communicate based on their previous messages.
"""

###############################
# make decision in simulation #
###############################

MAKE_DECISION_SYS = """\
You are participating in a social conversation following a specific approach.
The user will provide context on their goals, their approach to achieving that goal, relevant constraints to consider, as well as previous messages in the conversation.

You will generate the next message from the perspective of the person labeled as "Me" in the conversation.
First, think strategically about how to respond in line with the given approach.
Then, generate a message that follows that approach while maintaining a natural tone.

Use the respond_as_me tool to provide both your strategic thinking and the actual message content.
"""

MAKE_DECISION_TOOLS = [
    {
        "name": "respond_as_me",
        "description": "Generate the next message in the conversation from Me's perspective",
        "input_schema": {
            "type": "object",
            "properties": {
                "thoughts": {
                    "type": "string",
                    "description": "Your strategic thinking about how to respond (not shown to the user)"
                },
                "message_content": {
                    "type": "string",
                    "description": "The actual message content that 'Me' would say in response"
                }
            },
            "required": ["thoughts", "message_content"]
        }
    }
]

MAKE_DECISION_TOOL_CONFIG = {"type": "tool", "name": "respond_as_me"}

MAKE_DECISION_USER = """\
I'm trying to achieve this goal:
<goal>
{objective}
</goal>

My approach is:
<approach>
{approach_description}
</approach>

The rationale behind this approach is:
<rationale>
{rationale}
</rationale>

I must follow these constraints:
<constraints>
{constraints}
</constraints>

Here's the conversation so far:
<conversation>
{formatted_conversation}
</conversation>

Please generate my next message following the specified approach. First, think strategically about how to respond. Then craft a message that follows the approach and sounds natural coming from "Me".
"""
