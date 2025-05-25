from anthropic import Anthropic
import logging
from typing import Any, Dict, List, Optional
from src.log_chat_messages import log_chat_messages

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("anthropic_client")

class AnthropicClient:
    """Wrapper for Anthropic client that logs all calls to .messages.create()"""

    def __init__(self, client: Optional[Anthropic] = None):
        """
        Initialize with an optional client instance.

        Args:
            client: Optional Anthropic client instance. If None, creates a new one.
        """
        self._client = client or Anthropic()
        self.messages = self.MessagesProxy(self._client.messages)

    class MessagesProxy:
        """Proxy for the messages attribute of the Anthropic client"""

        def __init__(self, messages_client: Any) -> None:
            """
            Initialize with the original messages client.

            Args:
                messages_client: The original Anthropic messages client
            """
            self._messages_client = messages_client

        def create(self, *args, **kwargs) -> Any: # type: ignore
            """
            Wrap the create method to log calls before passing to the real client.

            Args:
                *args: Positional arguments for the create method
                **kwargs: Keyword arguments for the create method

            Returns:
                The result from the original client
            """
            # Basic request logging
            model = str(kwargs.get("model", "unknown"))
            logger.info(f"Anthropic API Request to model: {model}")

            # Extract messages for logging
            if "messages" in kwargs:
                messages: List[Dict[str, Any]] = kwargs["messages"]

                system_prompt: Optional[str] = kwargs.get("system", None)
                non_system_messages: List[Dict[str, Any]] = []

                for msg in messages:
                    if msg.get("role") == "system":
                        system_prompt: str = msg.get("content", "")
                    else:
                        non_system_messages.append(msg)

                log_chat_messages(non_system_messages, system_prompt, metadata=kwargs)

            # Call the original method
            return self._messages_client.create(*args, **kwargs)

    # Pass through any other attributes to the wrapped client
    def __getattr__(self, name: str):
        return getattr(self._client, name)

anthropic_client = AnthropicClient()
