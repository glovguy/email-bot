from src.models import User, db_session

class Authorization:
    @staticmethod
    def is_authorized(email_address):
        """Determine if the given email is authorized to be read and acted on by the bot."""
        # email is sent by an existing user
        user = db_session.query(User).filter_by(email_address=email_address).first()
        return user is not None
