import chromadb
from decouple import config
from datetime import datetime
from hashlib import sha256
from InstructorEmbedding import INSTRUCTOR
import uuid6
import os

os.environ["TOKENIZERS_PARALLELISM"] = "false"

chroma_client = chromadb.PersistentClient(path="./documents_collection")
default_embeddings_model = INSTRUCTOR('hkunlp/instructor-base')


def botbrain_note_embed(doc_string):
    instruction = "Represent this note written about the user's preferences and personality: "
    vec = default_embeddings_model.encode([[instruction, doc_string[0]]]).tolist()
    return vec

botbrain_collection = chroma_client.get_or_create_collection(name="botbrain_collection", embedding_function=botbrain_note_embed)


'''
BotBrain document
metadata
{
    uuid
    sha
    created_at
    last_modified_at
    content
    vectored_content
    user_id
}
'''
# to add: title, filepath
# That way I can add the title in prompts
# then re-add the local files via a script? Or maybe a "repair" script would be better?


class BotBrain:
    @classmethod
    def get_relevant_documents(cls, doc_strings, n_results=5, where={}, include=['documents']):
        results = botbrain_collection.query(
            query_texts=doc_strings,
            n_results=n_results,
            where=where,
            where_document={},
            include=include
        )
        return results

    @classmethod
    def add_document(cls, doc_string, metadata={}):
        if doc_string == '' or metadata.get('user_id') is None:
            return

        keys_to_keep = ['user_id', 'title']
        metad = {k: metadata[k] for k in keys_to_keep if k in metadata}
        uuid = str(uuid6.uuid7())
        sha = cls.doc_sha(doc_string)
        now = str(datetime.now())
        meta = {
            "sha": sha,
            "created_at": now,
            **metad
        }
        botbrain_collection.add(
            documents=[doc_string],
            metadatas=[meta],
            ids=[uuid]
        )
        return uuid

    @classmethod
    def get_document(cls, **kwargs):
        '''e.g. get_document(sha="foo-bar")'''
        ids = []
        if kwargs.get('uuid') is not None:
            ids = [kwargs.get('uuid')]
        return botbrain_collection.get(
            ids=ids,
            where=kwargs
        )

    @classmethod
    def doc_sha(cls, doc_string):
        return sha256(doc_string.encode('utf-8')).hexdigest()
