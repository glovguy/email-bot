import random
from src.skills.zettelkasten_skill import Zettelkasten
from src.skills.base import SkillBase

class PonderWittgensteinSkill(SkillBase):
    @classmethod
    def ponder_wittgenstein(cls, user):
        pi_witt = open("pi_english.txt", "r").read()
        pi_entries = pi_witt.split("=======")

        picked_index = random.choices(range(len(pi_entries)-3), k=1)[0]
        picked_entries = pi_entries[picked_index:picked_index+3]

        zettel_search_results = Zettelkasten.get_relevant_documents(picked_entries, n_results=3)
        zettels = [d for d in zettel_search_results['documents'][0]]

        print("zettels count: ", len(zettels))
        response = cls.llm_client.send_message(**ponder_wittgenstein(wittgenstein_entries=picked_entries, zettels=zettels)).content
        cls.email_inbox.send_email(
            user.email_address,
            f'Some thoughts about Wittgenstein {picked_index}.',
            "Wittgenstein:" +
                "=======".join(picked_entries) +
                "* * *\n\nZettels:\n\n" + "---\n\n".join(zettels) +
                "\n\n* * *\n\nMy thoughts:\n\n" +
                response
        )
        return response


def ponder_wittgenstein(**kwargs):
    ''' kwargs {
        wittgenstein_entries: Array<string>
        zettels: Array<string>
    }
    '''
    messages = [{
        "role": "system",
        "content": "You are a philosopher who specializes in Wittgenstein and Artificial Intelligence.\n\nBelow are some entries written by Ludwig Wittgenstein in his book Philosophical Investigations. Please discuss at length their relevance to large language models."
    }]
    if kwargs.get('wittgenstein_entries') is not None and len(kwargs.get('wittgenstein_entries')):
        messages.append({
            "role": "system",
            "content": "Wittgenstein wrote:\n"
        })
        for entry in kwargs.get('wittgenstein_entries'):
            messages.append({
                "role": "user",
                "content": entry
            })
    if kwargs.get('zettels') is not None and len(kwargs.get('zettels')):
        messages.append({
            "role": "system",
            "content": "Below are some Zettelkasten notes written by the user. These notes may contain ideas relevant to the above entries. It is okay to ignore these if they are not relevant."
        })
        for zettel in kwargs.get('zettels'):
            messages.append({
                "role": "user",
                "content": zettel
            })
    messages.append({
        "role": "system",
        "content": "Professor, I'd be so happy if you could share your thoughts. Please discuss at length the above Wittgenstein quotes and their relevance to large language models. We are looking for a unique spin on these passages. (You may use the user's notes above to understand what the user finds to be interesting, but you need not reference them.)\n\nBe creative and have fun! Looking forward to hearing from you!"
    })
    return {
        "messages": messages,
        "temperature": 0.95,
        "use_slow_model": True
    }
