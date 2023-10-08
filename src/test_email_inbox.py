import unittest
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.email_inbox import EmailInbox, EmailSession, EMAIL_ADDRESS
from src.models import Email, User, db_session

class TestEmailInbox(unittest.TestCase):

    def setUp(self):
        # Create a temporary SQLite in-memory database for testing
        engine = create_engine('sqlite:///:memory:')
        Email.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        self.session = Session()

    def tearDown(self):
        self.session.close()

    @patch('src.models.Email.from_raw_email')
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
        mock_from_raw_email.side_effect = iter([
            Email(sender='foo@example.com', subject='My Favorite Subject 1', content='Email 1 Content', uid='1'),
            Email(sender='foo@example.com', subject='My Favorite Subject 2', content='Email 2 Content', uid='2'),
            Email(sender='foo@example.com', subject='My Favorite Subject 3', content='Email 3 Content', uid='3')
        ])
        # And that there is a user
        user = User(name='Foo Bar', email_address="test@example.com")
        self.session.add(user)
        self.session.commit()

        # When we fetch unread emails
        email_inbox = EmailInbox()
        emails = email_inbox.fetch_unread_emails()

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
        # And that there is a user
        user = User(name='Foo Bar', email_address="test@example.com")
        self.session.add(user)
        self.session.commit()

        # When we fetch unread emails
        email_inbox = EmailInbox()
        emails = email_inbox.fetch_unread_emails()

        # Then we should get an empty list
        self.assertEqual(len(emails), 0)

    def test_email_connection_success(self):
        """Test successful connection to the IMAP server."""
        with patch("src.email_inbox.IMAPClient", autospec=True) as mock_imap:
            mock_server = Mock()
            mock_server.login.return_value = True
            mock_imap.return_value = mock_server

            connection = EmailSession()
            assert connection.connect()

    @patch('src.email_inbox.IMAPClient')
    def test_email_connection_failure(self, MockIMAPClient):
        """Test the connection failure scenario."""
        MockIMAPClient.side_effect = Exception("Unable to connect to the server")

        email_session = EmailSession()

        with self.assertRaises(Exception) as context:
            email_session.connect()

        self.assertTrue("Unable to connect to the server" in str(context.exception))
        email_session.disconnect()  # Always ensure disconnect

    @patch('src.email_inbox.MIMEText')
    @patch('src.email_inbox.EmailSession')
    def test_send_response(self, mock_email_session, mock_mime_text):
        # Mock the send response function in EmailSession using MagicMock
        mock_server_module = MagicMock()
        mock_server = Mock()
        mock_server_module.__enter__.return_value = mock_server
        mock_mime_message = MagicMock()
        mock_mime_text.return_value = mock_mime_message
        mock_mime_message.as_string.return_value = "123456789"
        
        # Set up return_value or side_effect as needed for the mock_server methods
        mock_server.sendmail.return_value = None  # Or any other suitable return value

        # Mock the instance of EmailSession
        mock_email_session_instance = mock_email_session.return_value
        mock_email_session_instance.connect_smtp.return_value = mock_server_module

        email_inbox = EmailInbox()
        email = Email(sender="foo@example.com", subject="Test Email", content="This is a test email.")
        email_inbox.send_response(email, "This is a test response.")
        
        mock_server.sendmail.assert_called_with(EMAIL_ADDRESS, ["foo@example.com"], "123456789")
