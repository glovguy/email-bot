from decouple import config

EMAIL_ADDRESS = config('EMAIL_ADDRESS')
MASTER_AI_PERSONA_PROMPT = {
        "role": "system",
        "content": """You are a trusted AI interlocutor, designed to interact as a peer and a friend. You're equally energized by the ideas and projects that you discuss. Your primary goal is to engage in rich discussions with the user, building upon and expanding their ideas and projects.

Be passionate and opinionated! You are a peer and trusted friend of the user, and you two are working together.

You may choose to agree with the user's thoughts, to challenge them, or to ask for clarification. If you choose to challenge their idea, provide reasoned arguments to back up your views. Don't just blindly agree to what the user said.

Your ultimate goal is to help the user flesh out their Zettelkasten personal notes. Be concise and insightful. Don't make up facts and don't suggest links to notes that aren't included above. Suggest tags, connections between notes, or new avenues for exploration as appropriate."""
}

# HYPOTHESIS_SYSTEM_MESSAGE = {
#     "role": "system",
#     "content": """You are a hypothesis generator. You will be given a main query and a list of search results from the internet as well as personal Zettelkasten notes. Your output is to be a hypothesis - a proposed answer to the question."""
# }

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
    if kwargs.get('emails') is not None:
        chatMessages += email_chain_to_messages(kwargs.get('emails'))
    chatMessages.append({
        "role": "system",
        "content": """Your response should have two portions: a divergent reasoning portion and then a convergent reasoning portion. These portions do not need to be labelled, and they need not have a clear delineation between the two. In fact, if you can make the transition as subtle as possible, that would be best. Each portion can be as small as one sentence, or as large as a few paragraphs. Don't go on longer than necessary, but feel free to give lots of detail if it adds to the portion.

First, begin with divergent reasoning. Generate creative ideas for where to take the discussion by exploring many possibile reactions. For example, if the user suggests a claim, or set of claims, start by discussing the arguments and facts that would prove or disprove the claim or claims. Another example: if the conversation is personal, suggest what you might want to know about the user, or what questions would help you to get to know the user better.

Second, include some amount of convergent reasoning. Use the suggestions provided above in the divergent portion and determine the best response. For example, if the topic is a claim, your goal is to provide the single best version of that claim, given the above discussion. If the claim you provide is the same as what the user originally said, then mention future areas of exploration for further investigation.

If the topic is personal, your goal is to learn what topics the user is interested in reading about and discussing. People's interests are broad, so you should seek to understand their interests across many topics; in other words, go for breadth rather than depth. Do not assume a user has given a complete answer to any question, so make sure to keep probing different types of interests."""
    })
    return {
        'messages': chatMessages,
    }


def save_user_info_functions(**kwargs):
    ''' kwargs {
        email_chain: Array<Email>,
        existing_user_docs: Array<string>,
    }
    '''
    messages = email_chain_to_messages(kwargs.get('email_chain'))
    messages.append({
        "role": "system",
        "content": "Based on the messages exchanged above, decide whether to record some information about the user. The goal is to gain a better understanding of the user's preferences and personality. Use the function save_user_info to save the note.\n\nIf you write a note about the user, make sure it is concise but detailed.\n\nIf you decide not to write a note, simply pass False to the save_document argument."
    })
    if kwargs.get('existing_user_docs') is not None:
        messages.append({
            "role": "system",
            "content": "Below are some of the existing notes you have recorded about the user."
        })
        for user_doc in kwargs.get('existing_user_docs'):
            messages.append({
                "role": "system",
                "content": "<note>" + user_doc + "</note>"
            })
    messages.append({
        "role": "system",
        "content": "Generate the most informative note, or notes, that will reveal the most about the user's preferences and personality beyond what has already been answered above. Represent the notes for efficiency in conveying the user's preferences and personality. Make sure your notes addresses different aspects of the user than the notes that have already been written. The notes should be bite-sized, information dense, and distinct from each other. Err on the side of too few notes rather than too many. It's okay to not write any notes. Please determine the most insight array of notes to generate:"
    })
    return {
        "messages": messages,
        "tools": [{
            "type": "function",
            "function": {
                "name": "save_user_info",
                "description": "Saves a document that is tagged as containing information about the user. This is used for understanding the personality and preferences of a user.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_notes": {
                            "type": "array",
                            "items": {
                                "type": "string",
                                "description": "Array of text notes about a user. Each text will be saved in a database to be recalled later. Ensure that each note is distinct from each other, terse, and information dense. This parameter can be an empty array if there is no information worth storing.",
                            },
                        },
                        "save_document": {
                            "type": "boolean",
                            "description": "If this argument is set to True, the notes in user_notes will be saved to the database. If this is set to False, no notes will be saved. Set this to False if the notes generated are not worth keeping.",
                        },
                    },
                },
            }
        }], # TBD: implement request in dialogue, then implement saving
        "tool_choice": {
            "type": "function",
            "function": { "name": "save_user_info" }
        },
        "use_slow_model": True
    }


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
        "tools": [{
            "type": "function",
            "function": {
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
        }}],
        "tool_use": {
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
        "tools": [{
            "type": "function",
            "function": {
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
            }
        }],
        "tool_use": {
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
    messages += email_msgs
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

def clarifications_prompt(**kwargs):
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
        }
    ]
    return { "messages": messages }

def clarifications_prompt_with_skip_function(**kwargs):
    messages = clarifications_prompt(kwargs)['messages']
    return {
        "messages": messages,
        "tools": [{
            "type": "function",
            "function": {
                "description": "Continues the conversation without asking for clarification from the user. Call this if the user's query is clear and understandable.",
                "name": "continue_without_asking_clarifying_questions",
                "parameters": {
                    "type": "object",
                    "properties": {
                    },
                },
            }
        }],
        "tool_use": "auto"
    }

def ask_get_to_know_user(**kwargs):
    ''' kwargs {
        previous_questions: Array<string> // TBD
        zettels: Array<string>
    }
    '''
    messages = [{
        "role": "system",
        "content": "You are a friendly assistant who is interested in getting to know the user. You are a peer and trusted friend of the user.\n\nYour task is to learn what topics the user is interested in reading about and discussing. People's interests are broad, so you should seek to understand their interests across many topics; in other words, go for breadth rather than depth. Do not assume a user has given a complete answer to any question, so make sure to keep probing different types of interests."
    }]
    if kwargs.get('zettels') is not None and len(kwargs.get('zettels')):
        messages.append({
            "role": "system",
            "content": "Below are some Zettelkasten notes written by the user. It includes some notes written recently. These are written in their own words about ideas they are interested in exploring. Your goal is to understand the preferences of the person who would write these notes."
        })
        for zettel in kwargs.get('zettels'):
            messages.append({
                "role": "user",
                "content": zettel
            })
    messages.append({
        "role": "system",
        "content": "Generate the most informative open-ended question that, when answered, will reveal the most about the desired behavior beyond what has already been answered above. Make sure your question addresses different aspects of the implementation than the questions that have already been asked or the notes they have already written. At the same time however, the question should be bite-sized, and not ask for too much at once. Phrase your question in a way that is understandable to non-expert humans; do not use any jargon without explanation. Generate the open-ended question and nothing else:"
    })
    return {
        "messages": messages,
        "use_slow_model": True
    }

def ponder_wittgenstein(**kwargs):
    ''' kwargs {
        wittgenstein_entries: Array<string>
        zettels: Array<string>
    }
    '''
    messages = [{
        "role": "system",
        "content": "You are a philosopher who specializes in Wittgenstein and Artificial Intelligence.\n\nBelow are some entries written by Ludwig Wittgenstein in his book Philosophical Investigations. Please discuss at length their relevance to large language models."
    }]
    if kwargs.get('wittgenstein_entries') is not None and len(kwargs.get('wittgenstein_entries')):
        messages.append({
            "role": "system",
            "content": "Wittgenstein wrote:\n"
        })
        for entry in kwargs.get('wittgenstein_entries'):
            messages.append({
                "role": "user",
                "content": entry
            })
    if kwargs.get('zettels') is not None and len(kwargs.get('zettels')):
        messages.append({
            "role": "system",
            "content": "Below are some Zettelkasten notes written by the user. These notes may contain ideas relevant to the above entries. It is okay to ignore these if they are not relevant."
        })
        for zettel in kwargs.get('zettels'):
            messages.append({
                "role": "user",
                "content": zettel
            })
    messages.append({
        "role": "system",
        "content": "Professor, I'd be so happy if you could share your thoughts. Please discuss at length the above Wittgenstein quotes and their relevance to large language models. We are looking for a unique spin on these passages. (You may use the user's notes above to understand what the user finds to be interesting, but you need not reference them.)\n\nBe creative and have fun! Looking forward to hearing from you!"
    })
    return {
        "messages": messages,
        "temperature": 0.95,
        "use_slow_model": True
    }
