from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import unittest
from unittest.mock import patch
import models
import src.authorization
from src.authorization import Authorization

class TestAuthorizationService(unittest.TestCase):

    def setUp(self):
        # Create a temporary SQLite in-memory database for testing
        self.engine = create_engine('sqlite:///:memory:')
        models.Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
        self.session.commit()

        self.mock_db_session = patch.object(src.authorization, 'db_session', self.session).start()

    def tearDown(self):
        models.Base.metadata.drop_all(bind=self.engine)
        self.session.close()
        patch.stopall()

    def test_verify_valid_user(self):
        # Given a user in our database
        valid_address = "valid_user@example.com"
        user = models.User(name="John Test", email_address=valid_address)
        self.session.add(user)
        self.session.commit()
        
        # When an email that that user sends is checked for authorization
        result = Authorization.is_authorized(valid_address)

        # Then the email is authorized
        self.assertTrue(result)

    def test_verify_invalid_user(self):
        # Given an email from invalid user
        invalid_email_address = "invalid_user@example.com"

        # When the email is checked for authorization
        result = Authorization.is_authorized(invalid_email_address)

        # Then the email is not authorized
        self.assertFalse(result)

if __name__ == '__main__':
    unittest.main()
