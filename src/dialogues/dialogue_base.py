import os
import time
import requests
from src.openai_client import OpenAIClient
from src.email_inbox import EmailInbox
from src.prompts import *
from src.documents import LOCAL_DOCS_FOLDER, Zettelkasten
from src.models import db_session

class DialogueBase(object):
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

    def save_document(self, email):
        title = email.subject
        if title == '':
            title = str(int(time.time()*1000))
        title += '.md'
        filepath = os.path.join(LOCAL_DOCS_FOLDER, title)
        print("creating file at ", filepath)
        f = open(filepath, "x")
        f.write(email.content)

        doc_uuid = Zettelkasten.add_document(
            email.content,
            {
                'user_id': email.sender_user_id,
                'source_email_id': email.id
            }
        )
        return doc_uuid
