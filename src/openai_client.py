import openai
from decouple import config

GPT_4 = "gpt-4"
GPT_3_5 = "gpt-3.5-turbo"

class OpenAIClient:
    def __init__(self):
        openai.api_key = config('OPENAI_API_KEY')

    def send_message(self, messages):
        response = openai.ChatCompletion.create(model=GPT_3_5, messages=messages)
        return response.get('choices')[0]['message']['content']
