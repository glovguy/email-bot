import json
from src.skills.base import SkillBase, email_chain_to_prompt_messages, MASTER_AI_PERSONA_PROMPT
from src.authorization import Authorization
from src.prompts import *
from src.skills.bot_brain import BotBrain
from src.skills.zettelkasten_skill import Zettelkasten
from src.models import db_session

class ProcessEmailSkill(SkillBase):
    def process(self, email):
        """
        Process the email by checking its authorization and if authorized,
        sending its content to OpenAI and responding to the email with the result.

        Args:
            email (Email): The email object to process

        Returns:
            str: The response from OpenAI if the email is authorized, None otherwise
        """
        try:
            if not Authorization.is_authorized(email.sender):
                email.is_processed = True
                db_session.commit()
                return None

            if email.recipient_is_save_address():
                self.save_document(email)
                email.is_processed = True
                db_session.commit()
                return

            docs = BotBrain.get_relevant_documents(email.content)
            save_fn_resp = self.llm_client.send_message_with_functions(
                **save_user_info_functions(email_chain=email.email_chain(), existing_user_docs=docs)
            )

            try:
                if save_fn_resp.get("tool_calls"): # and save_fn_resp.get("tool_calls")[0].get("function").get("arguments").get("save_document"):
                    resp_args = json.loads(save_fn_resp.get("tool_calls")[0].get("function").get("arguments"))
                    if resp_args.get("save_document"):
                        new_docs = resp_args.get("user_notes")
                        print("Going to save docs: ", new_docs)
                        for new_doc in new_docs:
                            doc_id = BotBrain.add_document(new_doc, { 'user_id': email.sender_user.id })
                            print("Saved doc ", doc_id)
                else:
                    print("Skipping saving a user info doc")
                    print("save_fn_resp: ", save_fn_resp)
            except:
                print("Error trying to navigate response.\nSkipping saving a user info doc")
                print("save_fn_resp: ", save_fn_resp)

            docs = Zettelkasten.get_relevant_documents([email.content])
            print('found ', len(docs), ' relevant docs')

            email_chain = email.email_chain()
            response = self.llm_client.send_message(**chat_prompt(emails=email_chain, docs=docs))['content']
            self.send_response(email, response)

            return response
        except Exception as e:
            print("Could not process email: ", email, " due to exception ", e)
            self.print_traceback(e)

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
        chatMessages += email_chain_to_prompt_messages(kwargs.get('emails'))
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
    messages = email_chain_to_prompt_messages(kwargs.get('email_chain'))
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