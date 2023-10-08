import unittest
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import models

class TestEmailModel(unittest.TestCase):

    def setUp(self):
        # Create a temporary SQLite in-memory database for testing
        self.engine = create_engine('sqlite:///:memory:')
        models.Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
        self.session.commit()

        self.mock_db_session = patch.object(models, 'db_session', self.session).start()

    def tearDown(self):
        models.Base.metadata.drop_all(bind=self.engine)
        self.session.close()
        patch.stopall()

    def test_email_parsing(self):
        # Given: A raw email string and its UID
        email_uid = "123-foo"
        raw_email = { b'BODY[]': """MIME-Version: 1.0
Subject: this is the subject of the email
From: Gmail Team <some_expected_sender@example.com>
To: John Smith <test@example.com>
Content-Type: multipart/alternative; boundary="000000000000123456789"

--000000000000123456789
Content-Type: text/plain; charset="UTF-8"
Content-Transfer-Encoding: quoted-printable

foo bar baz
--000000000000123456789
Content-Type: text/html; charset="UTF-8"
Content-Transfer-Encoding: quoted-printable

<!DOCTYPE html><html><head><meta=
/><title>this is the subject of the email</title></head><b=
ody>foo</body></html=>""" }

        # When: We use the from_raw_email method
        email = models.Email.from_raw_email(raw_email, email_uid)

        # Then: The email should be correctly parsed
        self.assertEqual(email.sender, 'some_expected_sender@example.com')
        self.assertEqual(email.subject, 'this is the subject of the email')
        self.assertEqual(email.content, 'foo bar baz')
        self.assertEqual(email.uid, email_uid)
        # self.assertEqual(email.user_id, 321) # need to init user for this test

    def test_insert_email(self):
        # Given: Some email data
        email_data = {
            'sender': 'test@example.com',
            'subject': 'Test Email',
            'content': 'This is a test email content',
            'parent_id': None,
            'sender_user_id': 123,
        }

        # When: We create an Email object and add it to the session
        email = models.Email(**email_data)
        self.session.add(email)
        self.session.commit()

        # Then: We should be able to retrieve it from the database
        retrieved_email = self.session.query(models.Email).filter_by(sender='test@example.com').first()
        self.assertIsNotNone(retrieved_email)
        self.assertEqual(retrieved_email.subject, 'Test Email')
        self.assertEqual(retrieved_email.content, 'This is a test email content')
        self.assertEqual(retrieved_email.sender_user_id, 123)

if __name__ == '__main__':
    unittest.main()
