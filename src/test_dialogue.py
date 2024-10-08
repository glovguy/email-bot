import unittest
from unittest.mock import patch, Mock
from dialogue import Dialogue
from models import EmailOld

class DialogueTest(unittest.TestCase):

    @patch('dialogue.OpenAIClient')
    @patch('dialogue.EmailInbox')
    @patch('dialogue.Authorization')
    def test_process_authorized_email(self, mock_authorization, mock_email_inbox, mock_llm_client):
        # Setting up the mocks
        mock_authorization.is_authorized.return_value = True
        mock_llm_client_instance = Mock()
        mock_llm_client.return_value = mock_llm_client_instance
        mock_llm_client_instance.send_message.return_value = "Processed message by OpenAI"
        mock_email_inbox_instance = Mock()
        mock_email_inbox.return_value = mock_email_inbox_instance

        email = EmailOld(sender="authorized@example.com", subject="Test Email", content="This is a test email.")
        dialogue = Dialogue()
        
        response = dialogue.process(email)
        
        # Verifications
        mock_llm_client_instance.send_message.assert_called()
        mock_email_inbox_instance.send_response.assert_called_with(email, response)
        self.assertEqual(response, "Processed message by OpenAI")

    @patch('dialogue.OpenAIClient')
    @patch('dialogue.EmailInbox')
    @patch('dialogue.Authorization')
    def test_process_unauthorized_email(self, mock_authorization, mock_email_inbox, mock_llm_client):
        # Setting up the mocks
        mock_authorization.is_authorized.return_value = False
        mock_llm_client_instance = Mock()
        mock_llm_client.return_value = mock_llm_client_instance
        mock_email_inbox_instance = Mock()
        mock_email_inbox.return_value = mock_email_inbox_instance

        email = EmailOld(sender="unauthorized@example.com", subject="Test Email", content="This is a test email.")
        dialogue = Dialogue()
        
        response = dialogue.process(email)

        # Verifications
        mock_llm_client_instance.send_message.assert_not_called()
        mock_email_inbox_instance.return_value.send_response.assert_not_called()
        self.assertIsNone(response)
