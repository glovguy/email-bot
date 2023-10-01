import unittest
from unittest.mock import Mock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.email_inbox import EmailInbox, EmailSession
from app.models import Email

class TestEmailInbox(unittest.TestCase):

    def setUp(self):
        # Create a temporary SQLite in-memory database for testing
        engine = create_engine('sqlite:///:memory:')
        Email.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        self.session = Session()

    def tearDown(self):
        self.session.close()

    @patch('models.Email.from_raw_email')
    @patch.object(EmailSession, 'connect')
    def test_fetch_unread_emails_success(self, mock_connect, mock_from_raw_email):
        """Test fetching unread emails successfully."""
        # Given there is a mock email server session and 3 unread emails
        mock_server = Mock()
        mock_connect.return_value = mock_server
        mock_server.select_folder.return_value = None
        mock_server.search.return_value = ['1', '2', '3']
        mock_server.fetch.return_value = {
            '1': {b'BODY[]': b'Email 1 Content'},
            '2': {b'BODY[]': b'Email 2 Content'},
            '3': {b'BODY[]': b'Email 3 Content'},
        }
        mock_from_raw_email.side_effect = [
            Email(sender='foo@example.com', subject='My Favorite Subject 1', content='Email 1 Content', uid='1'),
            Email(sender='foo@example.com', subject='My Favorite Subject 2', content='Email 2 Content', uid='2'),
            Email(sender='foo@example.com', subject='My Favorite Subject 3', content='Email 3 Content', uid='3')
        ]

        # When we fetch unread emails
        email_inbox = EmailInbox()
        emails = email_inbox.fetch_unread_emails(self.session)

        # Then we should get 3 emails
        self.assertEqual(len(emails), 3)

    @patch.object(EmailSession, 'connect')
    def test_fetch_no_unread_emails(self, mock_connect):
        """Test when there are no unread emails."""
        # Given there is a mock email server session and no unread emails
        mock_server = Mock()
        mock_connect.return_value = mock_server
        # Mock the search method to return empty list (no emails)
        mock_server.search.return_value = []

        # When we fetch unread emails
        email_inbox = EmailInbox()
        emails = email_inbox.fetch_unread_emails(self.session)

        # Then we should get an empty list
        self.assertEqual(len(emails), 0)

    def test_email_connection_success(self):
        """Test successful connection to the IMAP server."""
        with patch("app.email_inbox.IMAPClient", autospec=True) as mock_imap:
            mock_server = Mock()
            mock_server.login.return_value = True
            mock_imap.return_value = mock_server

            connection = EmailSession()
            assert connection.connect()

    @patch('app.email_inbox.IMAPClient')
    def test_email_connection_failure(self, MockIMAPClient):
        """Test the connection failure scenario."""
        MockIMAPClient.side_effect = Exception("Unable to connect to the server")

        email_session = EmailSession()

        with self.assertRaises(Exception) as context:
            email_session.connect()

        self.assertTrue("Unable to connect to the server" in str(context.exception))
        email_session.disconnect()  # Always ensure disconnect
