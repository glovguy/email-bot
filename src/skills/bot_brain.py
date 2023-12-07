from src.skills.base import DocumentsBase, chroma_client, default_embeddings_model

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
    namespace
}
'''

class BotBrain(DocumentsBase):
    @classmethod
    def get_relevant_documents(cls, namespace, doc_strings, where, n_results=5, include=['documents']):
        results = botbrain_collection.query(
            query_texts=doc_strings,
            n_results=n_results,
            where={ "$and": [ {**where}, {"namespace": namespace}] },
            where_document={},
            include=include
        )
        return results

    @classmethod
    def add_document(cls, namespace, doc_string, metadata={}):
        if doc_string == '' or metadata.get('user_id') is None:
            return

        keys_to_keep = ['user_id', 'title']
        metad = {k: metadata[k] for k in keys_to_keep if k in metadata}
        uuid = cls.generate_uuid()
        sha = cls.doc_sha(doc_string)
        now = cls.now_str()
        meta = {
            **metad,
            "namespace": namespace,
            "sha": sha,
            "created_at": now,
            "last_modified_at": now,
        }
        botbrain_collection.add(
            documents=[doc_string],
            metadatas=[meta],
            ids=[uuid]
        )
        return uuid

    @classmethod
    def get_document(cls, namespace, uuid=None, **kwargs):
        '''e.g. get_document(sha="foo-bar")'''
        ids = []
        if uuid is not None:
            ids = [uuid]
        print('hdsjkdsfkjd', uuid, { "$and": [{**kwargs}, {"namespace": namespace}] })
        return botbrain_collection.get(
            ids=ids,
            where={ "$and": [{**kwargs}, {"namespace": namespace}] }
        )

    @classmethod
    def update_document(cls, namespace, id, doc_string):
        metad = {
            "namespace": namespace,
            "last_modified_at": cls.now_str()
        }
        botbrain_collection.update(
            ids=[id],
            metadatas=[metad],
            documents=[doc_string],
        )
