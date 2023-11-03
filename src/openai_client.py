import openai
from decouple import config

GPT_4 = "gpt-4"
GPT_3_5 = "gpt-3.5-turbo"

class OpenAIClient:
    def __init__(self):
        openai.api_key = config('OPENAI_API_KEY')

    def send_message(self, messages, use_slow_model=False):
        if use_slow_model:
            model = GPT_4
        else:
            model = GPT_3_5
        print("Requesting chat completion with the following messages: ", messages)
        response = openai.ChatCompletion.create(model=model, messages=messages)
        return response.get('choices')[0]['message'] #['content']

    def send_message_with_functions(self, messages, use_slow_model=False, functions=[], function_call=None):
        if use_slow_model:
            model = GPT_4
        else:
            model = GPT_3_5
        print("Requesting chat completion with the following messages: ", messages)
        response = openai.ChatCompletion.create(model=model, messages=messages, functions=functions, function_call=function_call)
        return response.get('choices')[0]['message']
