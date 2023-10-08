from src.openai_client import OpenAIClient
from src.email_inbox import EmailInbox
from src.authorization import Authorization

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

        chatMessages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": email.content}
        ]
        response = self.openai_client.send_message(chatMessages)
        
        self.email_inbox.send_response(email, response)

        return response
