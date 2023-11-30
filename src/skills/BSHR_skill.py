import json
from src.prompts import *
from src.skills.base import SkillBase, email_chain_to_prompt_messages

class BSHRSkill(SkillBase):
    def compose_clarifying_questions(self, email):
        msg = self.llm_client.send_message_with_functions(**clarifications_prompt_with_skip_function(query=email.content))
        if msg.get("tool_calls"):
            return
        return msg['content']

    def BSHR_single_round_chat(self, email):
        # First ask for any clarifications from user
        if len(email.email_chain()) == 1:
            clarifying_questions = self.compose_clarifying_questions(email)
            if clarifying_questions is not None:
                self.send_response(email, clarifying_questions)
                return

        response_message = self.llm_client.send_message_with_functions(
            **BSHR_brainstorm_wikipedia(email.email_chain())
        )
        print("\n\nsearch_queries_json: ", response_message)
        try:
            search_queries = json.loads(response_message["function_call"]["arguments"])["search_queries"]
        except:
            print("Failed to parse")
            search_queries = []

        # Step 2: Search the internet
        wikipedia_search_results = []
        search_urls = []
        for query in search_queries:
            content, url = self.search_wikipedia(query)
            wikipedia_search_results.append(content)
            search_urls.append(url)

        msg = self.llm_client.send_message_with_functions(
            **BSHR_brainstorm_zettelkasten(email.email_chain())
        )
        print("zettelkasten_queries: ", msg)
        try:
            zettelkasten_queries = json.loads(msg["function_call"]["arguments"])["search_queries"]
            zettel_search_results = Zettelkasten.get_relevant_documents(zettelkasten_queries)
            zettels = [d for d in zettel_search_results['documents'][0]]
        except Exception as err:
            print("Failed to get Zettelkasten queries due to error: ", err)
            zettels = []

        response = self.llm_client.send_message(
            **BSHR_generate_hypothesis(
                email_chain=email.email_chain(),
                zettels=zettels,
                search_results=wikipedia_search_results
            ),
            use_slow_model=True
        )['content']

        self.send_response(email, response)
        return response


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


def BSHR_brainstorm_wikipedia(email_chain):
    email_msgs = email_chain_to_prompt_messages(email_chain)
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
    email_msgs = email_chain_to_prompt_messages(email_chain)
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
    email_msgs = email_chain_to_prompt_messages(kwargs.get("email_chain"))
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
