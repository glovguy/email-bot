import chromadb
from datetime import datetime
from decouple import config
from hashlib import sha256
from InstructorEmbedding import INSTRUCTOR
import os
import requests
import uuid6
from src.openai_client import OpenAIClient
from src.email_inbox import EmailInbox
from src.prompts import *
from src.models import db_session

EMAIL_ADDRESS = config('EMAIL_ADDRESS')
os.environ["TOKENIZERS_PARALLELISM"] = "false"

documents_collection_path = config('DOCUMENTS_COLLECTION_PATH', default="./documents_collection")
chroma_client = chromadb.PersistentClient(path=documents_collection_path)
default_embeddings_model = INSTRUCTOR('hkunlp/instructor-base')

class SkillBase(object):
    def __init__(self):
        self.llm_client = OpenAIClient()
        self.email_inbox = EmailInbox()

    def print_traceback(self, e):
        trace = []
        tb = e.__traceback__
        while tb is not None:
            trace.append({
                "filename": tb.tb_frame.f_code.co_filename,
                "name": tb.tb_frame.f_code.co_name,
                "lineno": tb.tb_lineno
            })
            tb = tb.tb_next
        print(
            'type: ', type(e).__name__,
            '\nmessage: ', str(e),
            '\ntrace: ', "\n".join(f"{v}" for v in trace)
        )

    def send_response(self, email, response):
        print("\n\nAttempting to send response to email ", email, "\n\nResponse:\n\n", response)
        self.email_inbox.send_email(email.sender, email.subject, response, parent_email=email)
        email.is_processed = True
        db_session.commit()

    # could later add SEP:
    # https://plato.stanford.edu/search/searcher.py?query=something
    def search_wikipedia(self, query):
        url = 'https://en.wikipedia.org/w/api.php'
        search_params = {
            'action': 'query',
            'list': 'search',
            'srsearch': query,
            'format': 'json'
        }

        response = requests.get(url, params=search_params)
        data = response.json()

        # Get the title of the first result
        title = data['query']['search'][0]['title']

        content_params = {
            'action': 'query',
            'prop': 'extracts',
            'exintro': True,
            'explaintext': True,
            'titles': title,
            'format': 'json'
        }

        response = requests.get(url, params=content_params)
        data = response.json()

        # Get the page ID of the first page
        page_id = list(data['query']['pages'].keys())[0]

        # Get the content of the page
        content = data['query']['pages'][page_id]['extract']

        # Get the URL of the page
        url = f"https://en.wikipedia.org/?curid={page_id}"

        return content, url

class DocumentsBase:
    @classmethod
    def generate_uuid(cls):
        return str(uuid6.uuid7())

    @classmethod
    def doc_sha(cls, doc_string):
        return sha256(doc_string.encode('utf-8')).hexdigest()

    @classmethod
    def now_str(cls):
        return str(datetime.now())

def email_chain_to_prompt_messages(email_chain):
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

MASTER_AI_PERSONA_PROMPT = {
        "role": "system",
        "content": """You are a trusted AI interlocutor, designed to interact as a peer and a friend. You're equally energized by the ideas and projects that you discuss. Your primary goal is to engage in rich discussions with the user, building upon and expanding their ideas and projects.

Be passionate and opinionated! You are a peer and trusted friend of the user, and you two are working together.

You may choose to agree with the user's thoughts, to challenge them, or to ask for clarification. If you choose to challenge their idea, provide reasoned arguments to back up your views. Don't just blindly agree to what the user said.

Your ultimate goal is to help the user flesh out their Zettelkasten personal notes. Be concise and insightful. Don't make up facts and don't suggest links to notes that aren't included above. Suggest tags, connections between notes, or new avenues for exploration as appropriate."""
}
