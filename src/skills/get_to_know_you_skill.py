import datetime
from src.prompts import *
from src.skills.zettelkasten_skill import Zettelkasten
from src.models import Email
from src.skills.base import SkillBase

class GetToKnowYouSkill(SkillBase):
    def ask_get_to_know_you(self, user):
        since = datetime.datetime.now() - datetime.timedelta(hours=48)
        latest_emails = Email.query.filter_by(sender_user=user).filter(Email.timestamp > since).all()
        if len(latest_emails) == 0:
            latest_emails = Email.query.filter_by(sender_user=user).order_by(Email.timestamp).first()

        latest_email_strings = [email.content for email in latest_emails]
        zettel_search_results = Zettelkasten.get_relevant_documents(latest_email_strings, n_results=3)
        zettels = [d for d in zettel_search_results['documents'][0]]
        zettels += latest_email_strings
        print("zettels count: ", len(zettels))
        response = self.llm_client.send_message(**ask_get_to_know_user(zettels=zettels)).content
        self.email_inbox.send_email(user.email_address, 'Getting to know you', response)
        return response
