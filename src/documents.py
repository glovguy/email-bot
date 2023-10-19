import chromadb
from decouple import config
from datetime import datetime
from hashlib import sha256
from InstructorEmbedding import INSTRUCTOR
import uuid6


chroma_client = chromadb.PersistentClient(path="./documents_collection")
embeddings_model = INSTRUCTOR('hkunlp/instructor-base')

def embed(doc_string):
    print("embed doc_string: ", type(doc_string), doc_string)
    instruction = "Represent the personal Zettelkasten note for storing and retrieving personal insights: "
    vec = embeddings_model.encode([[instruction, doc_string[0]]]).tolist()
    print("vec type: ", type(vec))
    return vec

documents_collection = chroma_client.get_or_create_collection(name="documents_collection", embedding_function=embed)

'''
metadata
{
    uuid
    sha
    created_at
    last_modified_at
    content
    vectored_content
    source_email_id
    user_id
}
'''

LOCAL_DOCS_FOLDER = config('LOCAL_DOCS_FOLDER')

class DocsFolder:
    @classmethod
    def add_document(cls, doc_string, metadata={}):
        keys_to_keep = ['user_id', 'source_email_id']
        metad = {k: metadata[k] for k in keys_to_keep if k in metadata}
        uuid = str(uuid6.uuid7())
        # doc_sha = sha256(doc_string.encode('utf-8')).hexdigest()
        sha = cls.doc_sha(doc_string)
        now = str(datetime.now())
        meta = {
            "sha": sha,
            "created_at": now,
            **metad
        }
        documents_collection.add(
            documents=[doc_string],
            metadatas=[meta],
            ids=[uuid]
        )
        return uuid
    
    @classmethod
    def get_document(cls, **kwargs):
        ids = []
        if [kwargs.get('uuid')] is not None:
            ids = [kwargs.get('uuid')]
        return documents_collection.get(
            ids=ids,
            where=kwargs
        )
    
    @classmethod
    def doc_sha(cls, doc_string):
        return sha256(doc_string.encode('utf-8')).hexdigest()
