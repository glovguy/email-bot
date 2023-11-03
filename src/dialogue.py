import os
import time
import requests
import json
from src.openai_client import OpenAIClient
from src.email_inbox import EmailInbox
from src.authorization import Authorization
from src.prompts import *
from src.documents import Zettelkasten, LOCAL_DOCS_FOLDER
from src.models import db_session

class Dialogue:

    def __init__(self):
        self.llm_client = OpenAIClient()
        self.email_inbox = EmailInbox()

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
            
            return self.BSHR_single_round_chat(email)


            docs = Zettelkasten.get_relevant_documents([email.content])
            print('found ', len(docs), ' relevant docs')
            
            email_chain = email.email_chain()
            chatMessages = chat_prompt(llm_client=self.llm_client, emails=email_chain, docs=docs)
            print("\n\n", chatMessages, "\n\n")
            response = self.llm_client.send_message(chatMessages, True)['content']
            self.send_response(email, response)['content']

            return response
        except Exception as e:
            print("Could not process email: ", email, " due to exception ", e)

    def compose_clarifying_questions(self, email):
        msg = self.llm_client.send_message_with_functions(**clarifications_prompt_with_functions(query=email.content))
        # if "nothing to clarify" in msg.lower() or msg.lower().startswith("no"):
        #     return
        # return msg
        # if msg.get("function_call") and msg["function_call"]["name"] == "ask_clarifying_questions":
            # Note: the JSON response may not always be valid; be sure to handle errors
        print("Clarifying questions response: ", msg)
        if msg.get("function_call"):
            return
        return msg['content']
        # try:
        #     return json.loads(msg["function_call"]["arguments"])["search_queries"]
        # except:
        #     print("unable to parse OpenAI function call")
        #     return []

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
        # if msg.get("function_call") and msg["function_call"]["name"] == "search_in_zettelkasten":
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
