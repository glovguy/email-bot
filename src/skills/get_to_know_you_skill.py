import json
import datetime
from typing import List
from src.event_bus import register_event_listener
from src.skills.zettelkasten_skill import Zettelkasten
from src.models import EmailOld
from src.skills.base import SkillBase, email_chain_to_prompt_messages
from src.skills.bot_brain import BotBrain

GET_TO_KNOW_DOC_NAMESPACE = 'get_to_know_you'
DOCUMENT_SEEN = 'get_to_know_you#document_seen'
BASE_PROMPT = {
    "role": "system",
    "content": "You are a friendly assistant who is interested in getting to know the user. \
You are a peer and trusted friend of the user.\n\n\
Your task is to learn what topics the user is interested in reading about and discussing. \
People's interests are broad, so you should seek to understand their interests across many topics; in other words, go for breadth rather than depth. \
Do not assume a user has given a complete answer to any question, so make sure to keep probing different types of interests."
}


class GetToKnowYouSkill(SkillBase):
    @classmethod
    def docs_not_seen(cls):
        documentProperties = ["documents", "ids", "metadatas"]
        allDocs = Zettelkasten.get_documents()
        print(allDocs.keys())
        out = {prop:[] for prop in documentProperties}
        print(out)
        for i in range(0, len(allDocs['ids'])):
            if allDocs['metadatas'][i].get(DOCUMENT_SEEN):
                continue
            for prop in documentProperties:
                out[prop].append(allDocs[prop][i])
        return out

    @classmethod
    def ask_get_to_know_you_latest_emails(cls, user):
        since = datetime.datetime.now() - datetime.timedelta(hours=48)
        latest_emails = EmailOld.query.filter_by(sender_user=user).filter(EmailOld.timestamp > since).all()
        if len(latest_emails) == 0:
            latest_emails = [EmailOld.query.filter_by(sender_user=user).order_by(EmailOld.timestamp).first()]

        latest_email_strings = [email.content for email in latest_emails]
        cls.ask_get_to_know_you(user, latest_email_strings)

    @classmethod
    def ask_get_to_know_you_latest_zettelkasten_notes(cls, user):
        uningested_zettel_docs = cls.docs_not_seen()
        # TODO: Fix this logic to get most distantly modified doc string
        # champ_i = 0
        # champ_datetime = datetime.datetime(uningested_zettel_docs["metadatas"][0].get("last_modified_at") or epoch)
        # for i in range(1, len(uningested_zettel_docs["ids"])):
        #     chall_datetime = datetime.datetime(uningested_zettel_docs["metadatas"][i].get("last_modified_at") or epoch)
        #     if chall_datetime is not None and chall_datetime > champ_datetime:
        #         champ_i = i
        #         champ_datetime = chall_datetime
        # latest_uningested_doc_string = uningested_zettel_docs["documents"][champ_i]
        latest_uningested_doc_string = uningested_zettel_docs["documents"][0]
        cls.ask_get_to_know_you(user, [latest_uningested_doc_string])
        Zettelkasten.update_document_metadata(uningested_zettel_docs["ids"][0], { DOCUMENT_SEEN: True })

    @classmethod
    def ask_get_to_know_you(cls, user, initial_query_docs):
        docs_similar_to_input = Zettelkasten.get_relevant_documents(
            initial_query_docs,
            n_results=25,
        )
        doc_strings_similar_to_input = [d for doc_string in docs_similar_to_input['documents'] for d in doc_string]
        existing_bot_notes = cls.existing_user_doc(user.id)["documents"][0]
        initial_question = cls.llm_client.send_message(
            **ask_get_to_know_user(
                initial_query_docs=initial_query_docs,
                zettels=doc_strings_similar_to_input,
                existing_bot_notes=[existing_bot_notes],
                use_slow_model=False
            )
        ).content
        print("initial_question: ", initial_question)
        # docs to answer initial question
        docs_similar_to_question = Zettelkasten.get_relevant_documents(
            [initial_question],
            n_results=10,
        )
        # exclude duplicates
        all_docs = doc_strings_similar_to_input # yeah I know it's not a deep copy
        # deduped_docs_similar_to_question = []
        # print('all_docs len:', len(all_docs))
        for i in range(0, len(docs_similar_to_question['ids'])):
            if docs_similar_to_question['ids'][i] in docs_similar_to_input['ids']:
                continue
            # print("appending: ", docs_similar_to_question['documents'][i][0])
            all_docs.append(docs_similar_to_question['documents'][i][0])
        # iterate on question based on existing notes
        iterated_question = cls.llm_client.send_message(
            **ask_get_to_know_user(
                initial_query_docs,
                all_docs,
                [existing_bot_notes],
                True
            )
        ).content
        email_subject = cls.llm_client.send_message(
            **draft_email_subject_line(
                iterated_question
            )
        ).content
        email_subject = 'Getting to know you - ' + email_subject
        response = cls.email_inbox.send_email(user.email_address, email_subject, iterated_question)
        return response

    @classmethod
    def existing_user_doc(cls, user_id):
        return BotBrain.get_document(GET_TO_KNOW_DOC_NAMESPACE, None, user_id=user_id)

    # listen to new document creation (not associated with an email received), ingest
    # keep track of which files were ingested (sha? uuid? filepath?)
    # create CRON script to iterate through uningested files
    @classmethod
    @register_event_listener('email_received')
    def save_user_info(cls, email):
        existing_user_doc = BotBrain.get_document(GET_TO_KNOW_DOC_NAMESPACE, None, user_id=email.sender_user.id)
        zettels = Zettelkasten.get_relevant_documents(
            [email.content for email in email.email_chain()],
            n_results=25,
        )
        zettels = [x for xs in zettels for x in xs] # flatten
        save_fn_resp = cls.llm_client.send_message_with_functions(
            **save_user_info_functions(email.email_chain(), existing_user_doc, zettels)
        )
        try:
            if save_fn_resp.get("tool_calls"):
                resp_args = json.loads(save_fn_resp.get("tool_calls")[0].get("function").get("arguments"))
                if resp_args.get("save_document"):
                    new_note = resp_args.get("user_notes")
                    edited_note_string = existing_user_doc['documents'][0] + "\n\n" + new_note
                    print("Going to save doc: ", new_note)
                    doc_id = BotBrain.update_document(
                        GET_TO_KNOW_DOC_NAMESPACE,
                        existing_user_doc['ids'][0],
                        edited_note_string
                    )
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


def draft_email_subject_line(email_content):
    messages = [{
        "role": "system",
        "content": "Given the following email body that will be sent, please draft a email subject line that summarizes it. Make it enticing so that the user will want to open it!"
    }, {
        "role": "assistant",
        "content": email_content
    }]
    return {
        "messages": messages,
        "use_slow_model": False
    }

def ask_get_to_know_user(initial_query_docs: List[str], zettels: List[str], existing_bot_notes: List[str], use_slow_model: bool = True):
    messages = [{
        "role": "system",
        "content": "You are a friendly assistant who is interested in getting to know the user. \
You are a peer and trusted friend of the user.\n\n\
Your task is to learn what topics the user is interested in reading about and discussing. \
People's interests are broad, so you should seek to understand their interests across many topics; in other words, go for breadth rather than depth. \
Do not assume a user has given a complete answer to any question, so make sure to keep probing different types of interests."
    }, {
        "role": "system",
        "content": "Below is a note (or notes) written by the user recently for their Zettelkasten. \
They wrote this in their own words about something they find interesting. \
Please use this note as the inspiration for the question you will ask. \
You have not seen this note yet and your goal is to understand the preferences of the person who would write this."
    }]
    for note in initial_query_docs:
        messages.append({
            "role": "user",
            "content": note
        })
    if len(zettels) > 0:
        messages.append({
            "role": "system",
            "content": "Below are Zettelkasten notes written by the user. \
You likely have already seen them, but they are related to the above note you are considering. \
These are written in their own words about ideas they are interested in exploring. \
They should provide some additional context to the note you are considering above, but your question should be primarily inspired by the previous note."
        })
        for zettel in zettels:
            messages.append({
                "role": "user",
                "content": zettel
            })
    if len(existing_bot_notes) > 0:
        messages.append({
            "role": "system",
            "content": "Below are the existing notes written about the user. \
These are the notes that you as an AI assistant have recorded already. \
The answer to your question will inform how these notes will be extended, so be mindful of how we can learn something new about the user.\
The open-ended question you ask should not be answered by any of the information provided below. \
Ideally you will be able to ask a question that gives information about the user's personality and preferences that isn't yet recorded below.\
Alternatively, you can ask a question that adds detail and nuance to the notes below.\
Please do what will provide the deepest understanding of the user's personality and preferences."
        })
        for note in existing_bot_notes:
            messages.append({
                "role": "user",
                "content": note
            })
    messages.append({
        "role": "system",
        "content": "Generate the most informative open-ended question that, when answered, \
will reveal the most about the desired behavior beyond what has already been answered above. \
Make sure your question addresses different aspects of the implementation than the questions \
that have already been asked or the notes they have already written. \
Look primarily at the note written be the user at the top.\
The question should be bite-sized, and not ask for too much at once. \
Phrase your question in a way that is understandable to non-expert humans; do not use any jargon without explanation. \
Generate the open-ended question and nothing else:"
    })
    return {
        "messages": messages,
        "use_slow_model": use_slow_model
    }

def rerank_zettels(query: str, zettels: List[str]):
    messages =[{
        "role": "system",
        "content": "Below is a question about the user's preferences and personality."
    }, {
        "role": "assistant",
        "content": query
    }, {
        "role": "system",
        "content": "Please take a look at the below notes and provide them scores for how relevant they are to the above question. These notes are written by the user."
    }]
    for i in range(0, len(zettels)):
        zettel = zettels[i]
        messages.append({
            "role": "assistant",
            "content": "<note" + str(i) + ">"
        })
        messages.append({
            "role": "user",
            "content": zettel
        })
        messages.append({
            "role": "assistant",
            "content": "</note" + str(i) + ">"
        })
    messages.append({
        "role": "system",
        "content": "Please indicate the relevance of each of the above notes to the question at the beginning.\n\nUse the function note_relevance to indicate the relevance of each note. Please pass in each note name and its relevance value. Be sure not to forget any notes in this list!"
    })
    return {
        "messages": messages,
        "tools": [{
            "type": "function",
            "function": {
                "name": "note_relevance",
                "description": "Stores how relevant each note is to the main question at hand. Each ",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "notes": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {
                                        "type": "string",
                                        "description": "This is the name of the note, which have been provided above. Each note has a unique name. The name should be something like \"note1\", \"note2\", etc.",
                                    },
                                    "relevance": {
                                        "type": "string",
                                        "description": "Indicates the amount of relevance. The allowed values are: [\"very_relevant\", \"somewhat_relevant\", \"not_relevant\"]. This argument must be one of these values.",
                                    },
                                }
                            }
                        }
                    },
                },
            }
        }],
        "tool_choice": {
            "type": "function",
            "function": { "name": "note_relevance" }
        },
        "use_slow_model": False
    }

def save_user_info_functions(email_chain: List[EmailOld], existing_user_doc: str, zettels: List[str]):
    messages = [
        BASE_PROMPT, 
        {
            "role": "system",
            "content": "Below is an email conversation between the user and their AI assistant. \
Use the conversation here to determine what the user is interested in."
        }
    ]
    messages.append(email_chain_to_prompt_messages(email_chain))
    if len(zettels) > 0:
        messages.append({
            "role": "system",
            "content": "Below are some notes written by the user. They may be relevant to the discussion. \
The user wrote these in their own words about things they find interesting.\
You likely have already seen them while taking notes about this user, but they could provide some background context on what the user thinks."
        })
    for zettel in zettels:
        messages.append({
            "role": "user",
            "content": zettel
        })
    messages.append({
        "role": "system",
        "content": "Below are the existing notes that have been recorded about the user about their personality and preferences. \
This was retrieved by the database and was written by you, the AI assistant."
    })
    messages.append({
        "role": "assistant",
        "content": existing_user_doc
    })
    # messages.append({
    #     "role": "system",
    #     "content": "Generate the most informative note that will reveal the most about the user's preferences and personality beyond what has already been answered above. Represent the note for efficiency in conveying the user's preferences and personality. Make sure your notes addresses different aspects of the user than the notes that have already been written. The notes should be bite-sized, information dense, and distinct from each other. Err on the side of too few notes rather than too many. It's okay to not write any notes if there is nothing new to include. Please determine the most insightful notes to generate:"
    # })
    messages.append({
        "role": "system",
        "content": "Based on the emails exchanged above, as well as the user's personal Zettelkasten notes, decide whether to record some information about the user. Generate the most informative note that will reveal the most about the user's personality and preferences beyond what has already been answered above. These notes should give insight into the tendencies that affect how the user typically feels, thinks, behaves, and how they interact with the world. You will later use these notes to make judgments about the user's likes, dislikes, values, and motivations with respect to some situation.\
\n\n\
Represent your note for efficiency in conveying the user's preferences and personality. These notes should be unique and information-dense. The goal is to gain a better understanding of the user's preferences and personality. Do not write a note that is already recorded about the user. If you write a note about the user, please make sure it is concise, but informative.\
\n\n\
Use the function save_user_info to save the note. This will append it to your notes about the user and save to the database. You do not have to save a note if there is nothing worthwhile to record. If you decide not to write a note, simply pass False to the save_document argument."
    })
    return {
        "messages": messages,
        "tools": [{
            "type": "function",
            "function": {
                "name": "save_user_info",
                "description": "Saves a note into a document about the user. This is used for understanding the personality and preferences of that user.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "explanation": {
                            "type": "string",
                            "description": "An explanation of how the answer was created."
                        },
                        "user_notes": {
                            "type": "string",
                            "description": "Text notes about a user. This text will be saved in a database to be recalled later. Ensure that the note is terse and information-dense.",
                        },
                        "save_document": {
                            "type": "boolean",
                            "description": "If this argument is set to True, the notes in user_notes will be saved to the database. If this is set to False, the user_notes field will be ignore and nothing will be saved. Set this to False if there is nothing worth keeping.",
                        },
                    },
                    "required": ["explanation", "save_document"]
                },
            }
        }],
        "tool_choice": {
            "type": "function",
            "function": { "name": "save_user_info" }
        },
        "use_slow_model": True,
        "temperature": 0.2
    }
