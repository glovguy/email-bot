from decouple import config
import re
import numpy as np
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, func
from sqlalchemy.engine.url import URL
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.sql import text, expression
from sqlalchemy.types import UserDefinedType
from src.base import Base

EMAIL_ADDRESS = config('EMAIL_ADDRESS')
POSTGRES_DATABASE_NAME = "bot_memory"
POSTGRES_USERNAME = config("POSTGRES_USERNAME")
POSTGRES_PASSWORD = config("POSTGRES_PASSWORD")

POSTGRES_DATABASE_URL = URL.create(
    drivername="postgresql+psycopg2",
    username=POSTGRES_USERNAME,
    password=POSTGRES_PASSWORD,
    host="localhost",
    port=5432,
    database=POSTGRES_DATABASE_NAME,
)
SQLALCHEMY_DATABASE_URI = POSTGRES_DATABASE_URL.render_as_string(hide_password=False)

def init_session():
    engine = create_engine(POSTGRES_DATABASE_URL.render_as_string(hide_password=False))
    SessionLocal = sessionmaker(autoflush=True, bind=engine)
    db_session = scoped_session(SessionLocal)
    return engine, db_session

engine, db_session = init_session()
Base.query = db_session.query_property()

class Vector(UserDefinedType):
    def __init__(self, dim):
        self.dim = dim

    def get_col_spec(self):
        return f"vector({self.dim})"

    def bind_expression(self, bindvalue):
        return expression.cast(bindvalue, self)

    def bind_processor(self, _dialect):
        def process(value):
            if value is None:
                return None
            if isinstance(value, list):
                return value
            raise ValueError("Vector values must be lists")
        return process

    def result_processor(self, _dialect, _coltype):
        def process(value):
            if value is None:
                return None
            value = value.strip('[]')
            return [float(x) for x in re.split(r',\s*(?=(?:[^"]*"[^"]*")*[^"]*$)', value)]
        return process


def cosine_similarity(a, b):
    if not isinstance(a, np.ndarray):
        a = np.array(a)
    if not isinstance(b, np.ndarray):
        b = np.array(b)

    dot_product = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)

    similarity = dot_product / (norm_a * norm_b)
    return similarity


def create_vector_extension():
    db_session.execute(text('CREATE EXTENSION IF NOT EXISTS vector'))
    db_session.execute(text("""
    CREATE OR REPLACE FUNCTION cosine_similarity(a vector, b vector)
    RETURNS float AS $$
    SELECT 1 - (a <=> b);
    $$ LANGUAGE SQL IMMUTABLE STRICT;
    """))
    db_session.commit()


def setup_db():
    print("running setup!")
    # Create database if it doesn't exist
    temp_engine = create_engine(f"postgresql+psycopg2://{POSTGRES_USERNAME}:{POSTGRES_PASSWORD}@localhost/postgres")
    conn = temp_engine.connect()
    conn.execute(text("commit"))
    try:
        conn.execute(text(f"CREATE DATABASE {POSTGRES_DATABASE_NAME}"))
    except:
        pass
    conn.close()
    temp_engine.dispose()

    # Import all models to ensure they're registered with SQLAlchemy
    from src.user import User
    from src.skills.email_skill.oauth_credential import OAuthCredential
    from src.skills.email_skill.email import Email
    from src.skills.email_skill.message_queue import MessageQueue
    from src.skills.email_skill.enqueued_message import EnqueuedMessage
    from src.app_setting import AppSetting
    from src.skills.social_stockfish.models import Contact

    # Create models
    Base.metadata.create_all(bind=engine)
    create_vector_extension()
