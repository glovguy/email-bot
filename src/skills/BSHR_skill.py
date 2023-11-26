import json
from src.prompts import *
from src.skills.base import SkillBase

class BSHRSkill(SkillBase):

    def compose_clarifying_questions(self, email):
        msg = self.llm_client.send_message_with_functions(**clarifications_prompt_with_skip_function(query=email.content))
        if msg.get("tool_calls"):
            return
        return msg['content']

    def BSHR_single_round_chat(self, email):
        # First ask for any clarifications from user
        if len(email.email_chain()) == 1:
            clarifying_questions = self.compose_clarifying_questions(email)
            if clarifying_questions is not None:
                self.send_response(email, clarifying_questions)
                return

        response_message = self.llm_client.send_message_with_functions(
            **BSHR_brainstorm_wikipedia(email.email_chain())
        )
        print("\n\nsearch_queries_json: ", response_message)
        try:
            search_queries = json.loads(response_message["function_call"]["arguments"])["search_queries"]
        except:
            print("Failed to parse")
            search_queries = []

        # Step 2: Search the internet
        wikipedia_search_results = []
        search_urls = []
        for query in search_queries:
            content, url = self.search_wikipedia(query)
            wikipedia_search_results.append(content)
            search_urls.append(url)

        msg = self.llm_client.send_message_with_functions(
            **BSHR_brainstorm_zettelkasten(email.email_chain())
        )
        print("zettelkasten_queries: ", msg)
        try:
            zettelkasten_queries = json.loads(msg["function_call"]["arguments"])["search_queries"]
            zettel_search_results = Zettelkasten.get_relevant_documents(zettelkasten_queries)
            zettels = [d for d in zettel_search_results['documents'][0]]
        except Exception as err:
            print("Failed to get Zettelkasten queries due to error: ", err)
            zettels = []

        response = self.llm_client.send_message(
            **BSHR_generate_hypothesis(
                email_chain=email.email_chain(),
                zettels=zettels,
                search_results=wikipedia_search_results
            ),
            use_slow_model=True
        )['content']

        self.send_response(email, response)
        return response
