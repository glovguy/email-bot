

def chat_prompt(**kwargs):
    chatMessages = [{
        "role": "system",
        "content": "You are a helpful assistant."
        }]
    for email in kwargs.get('emails'):
        chatMessages.append({
            "role": "user",
            "content": email.content
        })
    return kwargs.get('llm_client').send_message(chatMessages)
