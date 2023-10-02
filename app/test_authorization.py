from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import unittest
from app.models import Email, User
from app.authorization import Authorization

class TestAuthorizationService(unittest.TestCase):

    def setUp(self):
        # Create a temporary SQLite in-memory database for testing
        engine = create_engine('sqlite:///:memory:')
        Email.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        self.session = Session()

    def tearDown(self):
        self.session.close()

    def test_verify_valid_user(self):
        # Given a user in our database
        user = User(name="John Test", email_address="valid_user@example.com")
        self.session.add(user)
        self.session.commit()
        email = Email(sender="valid_user@example.com")
        
        # When an email that that user sends is checked for authorization
        result = Authorization.is_authorized(email)

        # Then the email is authorized
        self.assertTrue(result)

    def test_verify_invalid_user(self):
        # Given an email from invalid user
        email = Email(sender="invalid_user@example.com")

        # When the email is checked for authorization
        result = Authorization.is_authorized(email)

        # Then the email is not authorized
        self.assertFalse(result)

if __name__ == '__main__':
    unittest.main()
