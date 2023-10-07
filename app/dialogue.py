from openai_client import OpenAIClient
from email_inbox import EmailInbox
from authorization import Authorization

class Dialogue:

    def __init__(self):
        self.openai_client = OpenAIClient()
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

        response = self.openai_client.send_message(email.content)
        
        self.email_inbox.send_response(email.sender, "Re: " + email.subject, response)

        return response
