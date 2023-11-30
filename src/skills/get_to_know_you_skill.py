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

def ask_get_to_know_user(**kwargs):
    ''' kwargs {
        previous_questions: Array<string> // TBD
        zettels: Array<string>
    }
    '''
    messages = [{
        "role": "system",
        "content": "You are a friendly assistant who is interested in getting to know the user. You are a peer and trusted friend of the user.\n\nYour task is to learn what topics the user is interested in reading about and discussing. People's interests are broad, so you should seek to understand their interests across many topics; in other words, go for breadth rather than depth. Do not assume a user has given a complete answer to any question, so make sure to keep probing different types of interests."
    }]
    if kwargs.get('zettels') is not None and len(kwargs.get('zettels')):
        messages.append({
            "role": "system",
            "content": "Below are some Zettelkasten notes written by the user. It includes some notes written recently. These are written in their own words about ideas they are interested in exploring. Your goal is to understand the preferences of the person who would write these notes."
        })
        for zettel in kwargs.get('zettels'):
            messages.append({
                "role": "user",
                "content": zettel
            })
    messages.append({
        "role": "system",
        "content": "Generate the most informative open-ended question that, when answered, will reveal the most about the desired behavior beyond what has already been answered above. Make sure your question addresses different aspects of the implementation than the questions that have already been asked or the notes they have already written. At the same time however, the question should be bite-sized, and not ask for too much at once. Phrase your question in a way that is understandable to non-expert humans; do not use any jargon without explanation. Generate the open-ended question and nothing else:"
    })
    return {
        "messages": messages,
        "use_slow_model": True
    }
