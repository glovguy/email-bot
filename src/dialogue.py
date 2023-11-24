import os
import time
import random
import requests
import json
import datetime
from src.openai_client import OpenAIClient
from src.email_inbox import EmailInbox
from src.authorization import Authorization
from src.prompts import *
from src.documents import BotBrain, LOCAL_DOCS_FOLDER, Zettelkasten
from src.models import db_session, Email

class Dialogue:
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

    def send_response(self, email, response):
        print("\n\nAttempting to send response to email ", email, "\n\nResponse:\n\n", response)
        self.email_inbox.send_email(email.sender, email.subject, response, parent_email=email)
        email.is_processed = True
        db_session.commit()

    def ask_get_to_know_you(self, user):
        since = datetime.datetime.now() - datetime.timedelta(hours=48)
        latest_emails = Email.query.filter_by(sender_user=user).filter(Email.timestamp > since).all()
        if len(latest_emails) == 0:
            latest_emails = Email.query.filter_by(sender_user=user).order_by(Email.timestamp).first()

        latest_email_strings = [email.content for email in latest_emails]
        zettel_search_results = Zettelkasten.get_relevant_documents(latest_email_strings, n_results=3)
        zettels = [d for d in zettel_search_results['documents'][0]]
        zettels += latest_email_strings
        print("zettels count: ", len(zettels))
        response = self.llm_client.send_message(**ask_get_to_know_user(zettels=zettels)).content
        self.email_inbox.send_email(user.email_address, 'Getting to know you', response)
        return response

    def ponder_wittgenstein(self, user):
        pi_witt = open("pi_english.txt", "r").read()
        pi_entries = pi_witt.split("=======")

        picked_index = random.choices(range(len(pi_entries)-3), k=1)[0]
        picked_entries = pi_entries[picked_index:picked_index+3]

        zettel_search_results = Zettelkasten.get_relevant_documents(picked_entries, n_results=3)
        zettels = [d for d in zettel_search_results['documents'][0]]

        print("zettels count: ", len(zettels))
        response = self.llm_client.send_message(**ponder_wittgenstein(wittgenstein_entries=picked_entries, zettels=zettels)).content
        self.email_inbox.send_email(
            user.email_address,
            f'Some thoughts about Wittgenstein {picked_index}.',
            "Wittgenstein:" +
                "=======".join(picked_entries) +
                "* * *\n\nZettels:\n\n" + "\n\n---".join(zettels) +
                "\n\n* * *\n\nMy thoughts:\n\n" +
                response
        )
        return response

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
