import chromadb
from datetime import datetime
from hashlib import sha256
from InstructorEmbedding import INSTRUCTOR
import uuid6
import os

os.environ["TOKENIZERS_PARALLELISM"] = "false"

chroma_client = chromadb.PersistentClient(path="./documents_collection")
default_embeddings_model = INSTRUCTOR('hkunlp/instructor-base')

