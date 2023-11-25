import os
import time
import random
import requests
import json
import datetime
from src.dialogues.dialogue_base import DialogueBase
from src.authorization import Authorization
from src.prompts import *
from src.documents import BotBrain, Zettelkasten
from src.models import db_session

class ProcessEmailDialogue(DialogueBase):
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
