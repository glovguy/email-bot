from typing import List
from decouple import config
from sqlalchemy import Column, Integer, Text, DateTime, ForeignKey, func, Index, event
from sqlalchemy.orm import relationship
from src.skills.base import default_embeddings_model
from src.models import db, Vector, db_session
from src.skills.email.message_queue import MessageQueue
import anthropic
from src.skills.email import GmailClient


def instructor_note_embed(doc_string):
    instruction = "Represent an open question or problem that the user is interested in: "
    vec = default_embeddings_model.encode([[instruction, doc_string]]).tolist()
    return vec[0]

class OpenQuestion(db.Model):
    __tablename__ = "open_questions"

    id = Column(Integer, primary_key=True)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    # user = relationship("User", back_populates="open_questions")
    instructor_base_embedding = Column(Vector(768))

    __table_args__ = (
        Index('ix_open_question_embedding', 'instructor_base_embedding', postgresql_using='ivfflat'),
    )

    def __repr__(self):
        return f'<OpenQuestion {self.id}>'
    
    @classmethod
    def speculate_open_questions_from_topic(cls, topic):
        zettels = topic.zettels[:20]
        zettel_strings = ["# "+ztl.title+"\n\n"+ztl.content for ztl in zettels]
        client = anthropic.Anthropic(
            api_key=config('ANTHROPIC_API_KEY')
        )
        prompt_message = f"""The following are notes from my Zettelkasten. They are representative notes for a certain topic.
            {"\n\n---\n\n".join(zettel_strings)}
            I would like to make a list of the top interesting problems and open questions \
            about topics I am interested in, similar to how Feynman would keep track of his favorite problems. \
            He said: \"You have to keep a dozen of your favorite problems constantly present in your mind, although by and large they \
            will lay in a dormant state. Every time you hear or read a new trick or a new result, test it against each of your twelve \
            problems to see whether it helps. Every once in a while there will be a hit, and people will say, \"How did he do it? He must be a genius!\"
            
            The notes above are relevant to a particular topic and should indicate the kinds of thoughts and ideas I am interested in. \
            Please speculate problems and open questions that I might have about this topic. \
            These open questions should be open ended and not answerable with a simple yes or no, but they should be \
            in principle answerable with more research.
            Your goal is to distill and capture the questions and problems I am interested in.
            Based on the response to your message, you will have a chance to save these open questions in a database. \
            This is to allow you to keep track of what ideas I am interested in."""
        speculation_messages = [
            {
                "role": "user", 
                "content": prompt_message
            }
        ]
        speculation_response = client.messages.create(
            messages=speculation_messages,
            model="claude-3-5-sonnet-20240620",
            max_tokens=1000,
            temperature=1.4,
            system="You are a helpful assistant. The user will provide notes that fit in a Zettelkasten topic group. They are written in markdown. Please speculate the open questions and problems they are interested in. Please be concise. Please do not speculate more than 10 open questions. Pick only the most interesting ones. Do not use generic jargon. Feel free to use technical terms, but do not use them if they are not relevant. Imitate the tone and style of the notes, but not their content. Please respond in the form of an inquiry to the user to confirm these questions and problems. Do not use markdown."
        ).content[0].text

        message_queue = MessageQueue.get_or_create(topic.user_id, "open_questions")
        message_queue.enqueue_message(speculation_response, topic.user.email_address, response_listener=handle_open_question_user_response, subject=f"Open questions about {topic.name}")
        return speculation_response

    @classmethod
    def store_open_questions(cls, open_questions: List[str], user_id: int):
        for open_question in open_questions:
            db_session.add(OpenQuestion(content=open_question, user_id=user_id))
        db_session.commit()

def on_change_content(target, value, _oldvalue, _initiator):
    target.instructor_base_embedding = instructor_note_embed(value)

event.listen(OpenQuestion.content, 'set', on_change_content)


email_response_tool_specs = [
    {
        "name": "store_open_question",
        "description": "Store a list of open questions in the database",
        "input_schema": {
            "type": "object",
            "properties": {
                "open_questions": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "description": "The open questions or interesting problems to store in the database"
                }
            },
            "required": ["open_questions"]
        }
    }
]

def handle_open_question_user_response(email):
    print("handling email! email.to_email_address: ", email.to_email_address)
    if email.to_email_address != config('EMAIL_ADDRESS'):
        print("email not sent to bot, skipping")
        return
    client = anthropic.Anthropic(
        api_key=config('ANTHROPIC_API_KEY')
    )
    user_id = 1
    gmail_client = GmailClient(user_id=user_id)
    chat_history = gmail_client.thread_as_chat_history(email.thread_id)
    print("chat_history: ", chat_history)
    open_question_bot_response = client.messages.create(
        messages=chat_history,
        model="claude-3-5-sonnet-20240620",
        max_tokens=1000,
        system="The user has responded to a question about the open questions and problems they would find interesting. Also provided are Zettelkasten notes written by the user that fit in a topic group. They are written in markdown. If the user's answer is sufficient to determine the open questions or problems they are interested in, please use the store_open_question tool to store them in the database. If it is not clear, simply ask the user for clarification. Do not use generic jargon. Feel free to use technical terms, but do not use them if they are not relevant.Please be concise. Please do not speculate more than 10 open questions. Pick only the most interesting ones. Imitate the tone and style of the user, but not their content. Do not use markdown.",
        tools=email_response_tool_specs
    )
    print("open_question_bot_response: ", open_question_bot_response)
    email_response_content = ""
    send_email = False
    for msg in open_question_bot_response.content:
        if msg.type == "tool_use" and msg.name == "store_open_question":
            OpenQuestion.store_open_questions(msg.input["open_questions"], user_id)
            email_response_content += "\n\n[Storing open questions]\n- " + "\n- ".join(msg.input["open_questions"]) + "\n[End of storing open questions]\n\n"
        elif msg.type == "text":
            send_email = True
            email_response_content += msg.text
        else:
            print("unknown message type: ", msg)
    if send_email:
        print("enqueueing email response")
        message_queue = MessageQueue.get_or_create(user_id, "open_questions")
        message_queue.enqueue_message(
            email_response_content, 
            email.from_email_address, 
            response_listener=handle_open_question_user_response, 
            email_thread_id=email.thread_id, 
            subject=f"RE: {email.subject}"
        )
