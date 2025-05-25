from src.user import User
from src.anthropic_client import AnthropicClient
from src.skills.email.email import Email
from src.skills.mcp_client import MCPClient
from src.models import db_session
from src.skills.email.message_queue import MessageQueue


async def default_listener(email: Email) -> None:
    """
    Default listener for handling emails that don't have a listener defined.
    This listener can perform research using Perplexity MCP when requested.
    """
    print("Default listener called")
    # Get the sender's user record
    sender_email = email.from_address
    user = db_session.query(User).filter_by(email_address=sender_email).first()
    if not user:
        # TODO: Handle unknown senders
        return

    # Get or create the user's message queue
    message_queue = MessageQueue.get_or_create(1, "research_requests")

    # Send acknowledgment email
    acknowledgment_body = f"""
    Hi {user.name},

    I've received your research request and will begin working on it shortly. 
    I'll send you another email with the results when I'm done.

    Best regards,
    Your Email Bot
    """
    message_queue.enqueue_message(
        content=acknowledgment_body,
        recipient_email=sender_email,
        subject="Research Request Received",
        parent_message_id=email.get('message_id')
    )

    # Perform research using Perplexity MCP
    
    async with MCPClient("src/skills/perplexity_mcp.py") as session:
        # Initialize the connection
        # Get a prompt
        prompt = await session.get_prompt(
            "research-request-prompt", arguments={"user_message": email.body}
        )
        tools = await session.list_tools()
        anthropic_client = AnthropicClient()
        response = anthropic_client.messages.create(
            model="claude-3-5-sonnet-latest",
            messages=[{"role": "user", "content": prompt}],
            tools=tools,
            tool_choice="auto",
        )
        research_results = ""
        for msg in response.messages:
            if msg.type == "tool_use":
                tool_result = await session.call_tool(msg.name, arguments=msg.arguments)
                for content in tool_result.content:
                    if content.type == "text":
                        research_results = research_results + "\n\n" + content.text
                    elif content.type == "resource" and hasattr(content.resource, "text"):
                        research_results = research_results + "\n\n" + content.resource.text
                    elif content.type == "resource" and hasattr(content.resource, "blob"):
                        research_results = research_results + "\n\n" + content.resource.blob
                    elif content.type == "image":
                        research_results = research_results + "\n\n" + content.data
            else:
                research_results += msg.content

        # Send research results email
        message_queue.enqueue_message(
            content=research_results,
            recipient_email=sender_email,
            subject="Research Results",
            parent_message_id=email.get('message_id')
        )
    