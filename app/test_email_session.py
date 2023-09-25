import pytest
import unittest
from unittest.mock import Mock, patch
from app.email_session import EmailSession
import imapclient

class TestEmailSession(unittest.TestCase):
    def test_email_connection_success(self):
        """Test successful connection to the IMAP server."""
        with patch("app.email_session.IMAPClient", autospec=True) as mock_imap:
            mock_server = Mock()
            mock_server.login.return_value = True
            mock_imap.return_value = mock_server

            connection = EmailSession()
            assert connection.connect()

    @patch('app.email_session.IMAPClient')
    def test_email_connection_failure(self, MockIMAPClient):
        """Test the connection failure scenario."""
        MockIMAPClient.side_effect = Exception("Unable to connect to the server")

        email_session = EmailSession()

        with self.assertRaises(Exception) as context:
            email_session.connect()

        self.assertTrue("Unable to connect to the server" in str(context.exception))
        email_session.disconnect()  # Always ensure disconnect
