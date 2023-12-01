import json
import datetime
from src.event_bus import EventBus
from src.skills.zettelkasten_skill import Zettelkasten
from src.models import Email
from src.skills.base import SkillBase, email_chain_to_prompt_messages
from src.skills.bot_brain import BotBrain

class GetToKnowYouSkill(SkillBase):
    @classmethod
    def ask_get_to_know_you(cls, user):
        since = datetime.datetime.now() - datetime.timedelta(hours=48)
        latest_emails = Email.query.filter_by(sender_user=user).filter(Email.timestamp > since).all()
        if len(latest_emails) == 0:
            latest_emails = Email.query.filter_by(sender_user=user).order_by(Email.timestamp).first()

        latest_email_strings = [email.content for email in latest_emails]
        zettel_search_results = Zettelkasten.get_relevant_documents(latest_email_strings, n_results=3)
        zettels = [d for d in zettel_search_results['documents'][0]]
        zettels += latest_email_strings
        response = cls.llm_client.send_message(**ask_get_to_know_user(zettels=zettels)).content
        cls.email_inbox.send_email(user.email_address, 'Getting to know you', response)
        return response

    @classmethod
    def save_user_info(cls, email):
        docs = BotBrain.get_relevant_documents(email.content)
        save_fn_resp = cls.llm_client.send_message_with_functions(
            **save_user_info_functions(email_chain=email.email_chain(), existing_user_docs=docs)
        )
        try:
            if save_fn_resp.get("tool_calls"):
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

    @classmethod
    def user_interests_doc_id(cls, email_address):
        return email_address + "-interests"

EventBus.add_listener('email_received', GetToKnowYouSkill.save_user_info)

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
