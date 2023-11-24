import openai
from decouple import config

GPT_4 = "gpt-4"
GPT_3_5 = "gpt-3.5-turbo"

class OpenAIClient:
    def __init__(self):
        openai.api_key = config('OPENAI_API_KEY')

    def send_message(self, messages, use_slow_model=False, temperature=1):
        if use_slow_model:
            model = GPT_4
        else:
            model = GPT_3_5
        # print("Requesting chat completion with the following messages: ", messages)
        print("Requesting chat completion with the following: ")
        print("\n".join(f"{k}\t{v}" for k, v in locals().items()))
        response = openai.ChatCompletion.create(model=model, messages=messages, temperature=temperature)
        try:
            return response.get('choices')[0]['message']
        except KeyError as e:
            print(f"KeyError: {e}")
            print("Response might not have the expected structure.")

    def send_message_with_functions(self, messages, use_slow_model=False, temperature=1, tools=[], tool_choice=None):
        if use_slow_model:
            model = GPT_4
        else:
            model = GPT_3_5
        print("Requesting chat completion with the following: ")
        print("\n".join(f"{k}\t{v}" for k, v in locals().items()))
        response = openai.ChatCompletion.create(model=model, messages=messages, temperature=temperature, tools=tools, tool_choice=tool_choice)
        try: 
            return response.get('choices')[0]['message']
        except KeyError as e:
            print(f"KeyError: {e}")
            print("Response might not have the expected structure.")
