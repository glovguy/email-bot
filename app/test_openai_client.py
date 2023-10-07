import unittest
from unittest.mock import patch
from openai_client import OpenAIClient

class OpenAIClientTest(unittest.TestCase):
    
    @patch('openai_client.openai')
    def test_send_message_to_openai(self, mock_openai):
        # Mock response from OpenAI
        mock_openai.Completion.create.return_value = {'choices': [{'message': {'content': 'Test Response'}}]}

        client = OpenAIClient()
        response = client.send_message("Hello, OpenAI!")

        self.assertEqual(response, "Test Response")
