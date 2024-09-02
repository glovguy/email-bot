from .oauth_credential import OAuthCredential
from .gmail_client import GmailClient
from .email import Email


def check_mailbox():
    print("checking mailbox...")
    credential = OAuthCredential.query.filter_by(user_id=1).first()
    gmail_client = GmailClient(credential.to_credentials())

    gmail_client.fetch_emails()

    # unprocessed_emails = Email.query.filter_by(is_processed=False).all()
    # print(len(unprocessed_emails), " unprocessed emails.")
    # for email in unprocessed_emails:
    #     print("Processing email: ", email)
    #     ProcessEmailSkill.process(email)


__all__ = ['Email', 'check_mailbox']
