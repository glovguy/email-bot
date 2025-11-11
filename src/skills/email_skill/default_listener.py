from src.user import User
from src.anthropic_client import AnthropicClient
from src.skills.email_skill.email import Email
# from src.skills.mcp_client import MCPClient
from fastmcp import Client
from src.models import db_session
from src.skills.email_skill.message_queue import MessageQueue


async def default_listener(email: Email) -> None:
    """
    Default listener for handling emails that don't have a listener defined.
    This listener can perform research using Perplexity MCP when requested.
    """
    print("Default listener called")
    # Get the sender's user record
    sender_email = email.from_email_address
    user = db_session.query(User).filter_by(email_address=sender_email).first()
    if not user:
        print(f"Unknown sender: {sender_email}")
        return

    print(f"User: {user}")
    
    # Get or create the user's message queue
    message_queue = MessageQueue.get_or_create(user.id, "research_requests")

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
        parent_message_id=email.message_id
    )
    
    try:
        async with Client("src/skills/perplexity_mcp.py") as client:
            research_results = await client.call_tool("research_chat_completion", {"messages": [{"role": "user", "content": email.body}]})
            
            # prompt = await session.get_prompt(
            #     "research-request-prompt", arguments={"user_message": email.body}
            # )
            # tools = await session.list_tools()
            # anthropic_client = AnthropicClient()
            # response = anthropic_client.messages.create(
            #     model="claude-3-5-sonnet-latest",
            #     messages=[{"role": "user", "content": prompt}],
            #     tools=tools,
            #     tool_choice="auto",
            # )
            
            # for msg in response.messages:
            #     if msg.type == "tool_use":
            #         tool_result = await session.call_tool(msg.name, arguments=msg.arguments)
            #         for content in tool_result.content:
            #             if content.type == "text":
            #                 research_results += f"\n\n{content.text}"
            #             elif content.type == "resource":
            #                 # Handle both text and blob resources safely
            #                 resource_text = getattr(content.resource, "text", None)
            #                 resource_blob = getattr(content.resource, "blob", None)
            #                 if resource_text is not None:
            #                     research_results += f"\n\n{resource_text}"
            #                 elif resource_blob is not None:
            #                     research_results += f"\n\n{resource_blob}"
            #             elif content.type == "image":
            #                 research_results += f"\n\n{content.data}"
            #     else:
            #         research_results += msg.content

            # Send research results email
            message_queue.enqueue_message(
                content=research_results.get("content", ""),
                recipient_email=sender_email,
                subject="Research Results",
                parent_message_id=email.message_id
            )
    except Exception as e:
        error_message = f"An error occurred while processing your research request: {str(e)}"
        message_queue.enqueue_message(
            content=error_message,
            recipient_email=sender_email,
            subject="Research Request Error",
            parent_message_id=email.message_id
        )
        raise
    