import json
import time
import os
from typing import List, TypedDict, Dict, Any

CHAT_LOGS_DIR = "chat_logs"
os.makedirs(CHAT_LOGS_DIR, exist_ok=True)

class LlmChatMessage(TypedDict):
    role: str
    message: str

def log_chat_messages(messages: List[LlmChatMessage], system_prompt: str | None = None, metadata: Dict[Any, Any] | None = None):
    """
    Write an array of message dictionaries to a text file.
    The filename is the current Unix timestamp.

    Args:
    messages (list): A list of message dictionaries.
    directory (str): The directory to save the file in. Defaults to 'chat_logs'.
    """
    # Create the directory if it doesn't exist

    # Generate filename using current Unix timestamp
    timestamp = int(time.time() * 1000)
    filename = f"{timestamp}.txt"
    filepath = os.path.join(CHAT_LOGS_DIR, filename)

    with open(filepath, 'w', encoding='utf-8') as file:
        if metadata:
            file.write(f"=== Metadata ===\n\n{json.dumps(metadata, indent=2)}\n\n")
        if system_prompt:
            file.write(f"=== System ===\n\n{system_prompt}\n\n")
        for message in messages:
            role = message.get('role', 'Unknown')
            content = message.get('content', '')
            file.write(f"=== {role} ===\n\n{content}\n\n")
    print(f"Chat log saved to {filepath}")
