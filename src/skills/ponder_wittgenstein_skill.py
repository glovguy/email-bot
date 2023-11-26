import random
from src.prompts import *
from src.documents import Zettelkasten
from src.skills.skill_base import SkillBase

class PonderWittgensteinSkill(SkillBase):
    def ponder_wittgenstein(self, user):
        pi_witt = open("pi_english.txt", "r").read()
        pi_entries = pi_witt.split("=======")

        picked_index = random.choices(range(len(pi_entries)-3), k=1)[0]
        picked_entries = pi_entries[picked_index:picked_index+3]

        zettel_search_results = Zettelkasten.get_relevant_documents(picked_entries, n_results=3)
        zettels = [d for d in zettel_search_results['documents'][0]]

        print("zettels count: ", len(zettels))
        response = self.llm_client.send_message(**ponder_wittgenstein(wittgenstein_entries=picked_entries, zettels=zettels)).content
        self.email_inbox.send_email(
            user.email_address,
            f'Some thoughts about Wittgenstein {picked_index}.',
            "Wittgenstein:" +
                "=======".join(picked_entries) +
                "* * *\n\nZettels:\n\n" + "---\n\n".join(zettels) +
                "\n\n* * *\n\nMy thoughts:\n\n" +
                response
        )
        return response
