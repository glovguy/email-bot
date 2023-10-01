import unittest
from unittest.mock import Mock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from email_session import EmailInbox, EmailSession

class TestEmailInbox(unittest.TestCase):

    def setUp(self):
        # Create a temporary SQLite in-memory database for testing
        engine = create_engine('sqlite:///:memory:')
        # Email.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        self.session = Session()

    def tearDown(self):
        self.session.close()

    @patch.object(EmailSession, 'connect')
    def test_fetch_unread_emails_success(self, mock_connect):
        """Test fetching unread emails successfully."""
        # Given there is a mock email server session and 3 unread emails
        mock_server = Mock()
        mock_connect.return_value = mock_server
        mock_server.search.return_value = ['1', '2', '3']
        mock_server.fetch.return_value = {
            '1': {b'BODY[]': b'Email 1 Content'},
            '2': {b'BODY[]': b'Email 2 Content'},
            '3': {b'BODY[]': b'Email 3 Content'},
        }

        # When we fetch unread emails
        email_inbox = EmailInbox()
        emails = email_inbox.fetch_unread_emails(self.session)

        # Then we should get 3 emails
        self.assertEqual(len(emails), 3)  # We've mocked 3 unread emails

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
