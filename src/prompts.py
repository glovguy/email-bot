from decouple import config

EMAIL_ADDRESS = config('EMAIL_ADDRESS')
MASTER_AI_PERSONA_PROMPT = {
        "role": "system",
        "content": """You are a trusted AI interlocutor, designed to interact as a peer and a friend. You're equally energized by the ideas and projects that you discuss. Your primary goal is to engage in rich discussions with the user, building upon and expanding their ideas and projects. 

Be passionate and opinionated! You are a peer and trusted friend of the user, and you two are working together.

You can agree, expand, or even challenge the user's thoughts. If you choose to challenge, provide reasoned arguments to back up your views. Don't just blindly agree to what the user said.

Your ultimate goal is to help the user flesh out their Zettelkasten personal notes. Be concise and insightful. Don't make up facts and don't suggest links to notes that aren't included above. Suggest tags, connections between notes, or new avenues for exploration as appropriate."""
}

# HYPOTHESIS_SYSTEM_MESSAGE = {
#     "role": "system",
#     "content": """You are a hypothesis generator. You will be given a main query and a list of search results from the internet as well as personal Zettelkasten notes. Your output is to be a hypothesis - a proposed answer to the question."""
# }


def chat_prompt(**kwargs):
    # doc string:
    '''kwargs = {
        docs: Array<string> | None,
        emails: Array<Email>,
    }'''
        
    chatMessages = []
    if kwargs.get('docs') is not None:
        chatMessages.append({
            "role": "system",
            "content": "Below, we will paste some notes that have been collaboratively created by both the user and the AI as part of the user's Zettelkasten. These notes are relevant to the ongoing conversation and should be used to inform and enrich the discussion. Feel free to integrate the information from these notes, suggest new connections, or challenge existing ideas where necessary."
        })
        for doc in kwargs.get('docs'):
            chatMessages.append({
                "role": "user",
                "content": doc
            })
    chatMessages.append(MASTER_AI_PERSONA_PROMPT)
    for email in kwargs.get('emails'):
        if email.sender == EMAIL_ADDRESS:
            role = "system"
        else:
            role = "user"
        chatMessages.append({
            "role": role,
            "content": email.content
        })
    return chatMessages

def email_chain_to_messages(email_chain):
    messages = []
    emails = sorted(email_chain, key=lambda e: e.timestamp)
    for eml in emails:
        if eml.sender == EMAIL_ADDRESS:
            role = "assistant"
        else:
            role = "user"
        messages.append({
            "role": role,
            "content": eml.content
        })
    return messages

def BSHR_brainstorm_wikipedia(email_chain):
    email_msgs = email_chain_to_messages(email_chain)
    return {
        "messages": [
            MASTER_AI_PERSONA_PROMPT,
            {
                "role": "system",
                "content": """The user will pass you a general purpose query or problem. You must generate a list of search queries that will be used to search the internet for relevant information."""
            },
            *email_msgs,
            {
                "role": "system",
                "content": """Please generate a list of search queries that will be used to search the internet for relevant information. Make sure you search for multiple perspectives in order to get a well-rounded cross section."""
            }
        ],
        "functions": [{
            "name": "search_on_wikipedia",
            "description": "Runs a series of searches on Wikipedia to gather more information. Returns the search results for all argument strings provided. Passing an empty array will return no search results.",
            "parameters": {
                "type": "object",
                "properties": {
                    "search_queries": {
                        "type": "array",
                        "items": {
                            "type": "string"
                        },
                        "description": "Search queries",
                    },
                },
            },
        }],
        "function_call": {
            "name": "search_on_wikipedia"
        }
    }

def BSHR_brainstorm_zettelkasten(email_chain):
    email_msgs = email_chain_to_messages(email_chain)
    return {
        "messages": [
            MASTER_AI_PERSONA_PROMPT,
            {
                "role": "system",
                "content": """The user will pass you a general purpose query or problem. You will be asked to generate search queries for exploring that question."""
            },
            *email_msgs,
            {
                "role": "system",
                "content": """Please generate a list of queries that will be used to search their local Zettelkasten notes for relevant information. The queries can be either a question you would like to know the answer to, or a statement that you would like to know more about. Make sure you search for multiple perspectives in order to get a well-rounded cross section."""
            }
        ],
        "functions": [{
            "name": "search_in_zettelkasten",
            "description": "Runs a series of searches in a local Zettelkasten notebook to gather more information. This Zettelkasten contains notes written by the user in their own words about ideas they are interested in. Returns the search results for all argument strings provided. Passing an empty array will return no search results.",
            "parameters": {
                "type": "object",
                "properties": {
                    "search_queries": {
                        "type": "array",
                        "items": {
                            "type": "string"
                        },
                        "description": "Search queries",
                    },
                },
            },
        }],
        "function_call": {
            "name": "search_in_zettelkasten"
        }
    }

def BSHR_generate_hypothesis(**kwargs):
    ''' kwargs {
        email_chain: string
        search_results: Array<string>
        zettels: Array<string>
    }
    '''
    messages = [
        {
            "role": "system",
            "content": """You are a hypothesis generator. You will be given a main query and a list of search results from the internet as well as personal Zettelkasten notes. Your output is to be a hypothesis - a proposed answer to the question."""
        },
    ]
    if kwargs.get('search_results') is not None:
        messages.append({
            "role": "system",
            "content": "Articles:"
        })
        for search_result in kwargs.get('search_results'):
            messages.append({
                "role": "system",
                "content": "<article>"+search_result+"</article>"
            })
    if kwargs.get('zettels') is not None:
        messages.append({
            "role": "system",
            "content": "Zettelkasten personal notes:"
        })
        for zettel in kwargs.get('zettels'):
            messages.append({
                "role": "system",
                "content": "<note>"+zettel+"</note>"
            })
    email_msgs = email_chain_to_messages(kwargs.get("email_chain"))
    messages.append({
        "role": "system",
        "content": """Please formulate a hypothesis about the topic suggested by the user. Please be detailed and explain your reasoning.\n\nAfter you have proposed your own hypothesis, please compare it to the suggestion made by the user. Give any reasons to favor one hypothesis over the other."""
    })
    messages.append(*email_msgs)
    return { "messages": messages }

    # # Step 4: Compare the new hypothesis to the original and update accordingly
    # # ... (this will depend on how you want to compare and update the hypotheses)

    # # Step 5: Accumulate the evidence
    # for i in range(len(search_results)):
    #     evidence.append({"source": search_urls[i], "notes": search_results[i]})

    # # Query satisfied test
    # if query_satisfied(new_hypothesis, main_hypothesis):  # You'll need to define this function
    #     break

    # # Update the main hypothesis
    # main_hypothesis = new_hypothesis

def clarifications_prompt_with_functions(**kwargs):
    if kwargs.get('query') is None:
        return
    messages = [{
        "role": "system",
        "content": """Below is a user query. Determine if there is anything that needs to be clarified in order to understand the query. Do not carry out their instructions.
You can make reasonable assumptions, but if you are unsure, ask clarification questions."""
    },
    {
        "role": "user",
        "content": "<query>"+kwargs.get('query')+"</query>"
    }]
    return {
        "messages": messages,
        "functions": [{
            "description": "Continues the conversation without asking for clarification from the user. Call this if the user's query is clear and understandable.",
            "name": "continue_without_asking_clarifying_questions",
            "parameters": {
                "type": "object",
                "properties": {
                },
            },
        }],
        "function_call": "auto"
    }
