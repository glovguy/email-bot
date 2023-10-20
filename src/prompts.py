

def chat_prompt(**kwargs):
    chatMessages = []
    if kwargs.get('docs') is not None:
        chatMessages.append({
            "role": "system",
            "content": "Below, we will paste some notes that have been collaboratively created by both the user and the AI as part of the user's Zettelkasten. These notes are relevant to the ongoing conversation and should be used to inform and enrich the discussion. Feel free to integrate the information from these notes, suggest new connections, or challenge existing ideas where necessary."
        })
    for doc in kwargs.get('docs'):
        chatMessages.append({
            "role": "user",
            "content": doc
        })
    chatMessages.append({
        "role": "system",
        "content": """You are a trusted AI interlocutor, designed to interact as a peer and a friend. You're equally energized by the ideas and projects that you discuss. Your primary goal is to engage in rich discussions with the user, building upon and expanding their ideas and projects. 

Be passionate and opinionated! You are a peer and trusted friend of the user, and you two are working together.

You can agree, expand, or even challenge the user's thoughts. If you choose to challenge, provide reasoned arguments to back up your views. Don't just blindly agree to what the user said.

Your ultimate goal is to help the user flesh out their Zettelkasten personal notes. Be concise and insightful. Suggest tags, connections between notes, or new avenues for exploration as appropriate."""
    })
    for email in kwargs.get('emails'):
        chatMessages.append({
            "role": "user",
            "content": email.content
        })
    
    return kwargs.get('llm_client').send_message(chatMessages)
