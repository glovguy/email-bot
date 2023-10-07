import openai
from decouple import config

class OpenAIClient:
    def __init__(self):
        openai.api_key = config('OPENAI_API_KEY')

    def send_message(self, message):
        response = openai.Completion.create(model="gpt-3.5-turbo", prompt=message, max_tokens=100)
        print("openai client response: ", response)
        return response.get('choices')[0]['message']['content']
