from src.openai_client import OpenAIClient
from src.email_inbox import EmailInbox
from src.authorization import Authorization
from src.prompts import *

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
        if not Authorization.is_authorized(email.sender):
            return None
        
        if email.recipient_is_save_address():
            self.save_document(email)
            return
        # chatMessages = [
        #     {"role": "system", "content": "You are a helpful assistant."},
        #     {"role": "user", "content": email.content}
        # ]
        # response = self.llm_client.send_message(chatMessages)
        response = chat_prompt(llm_client=self.llm_client, emails=[email])
        self.email_inbox.send_response(email, response)

        return response
    
    def save_document(self, email):
        print("I want to save this email!", email)
        # email.content
