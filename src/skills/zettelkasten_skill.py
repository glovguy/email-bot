from decouple import config
import os
import time
from src.skills.base import DocumentsBase, SkillBase, chroma_client, default_embeddings_model
from src.event_bus import register_event_listener

def zettel_note_embed(doc_string):
    instruction = "Represent the personal Zettelkasten note for storing and retrieving personal insights: "
    vec = default_embeddings_model.encode([[instruction, doc_string[0]]]).tolist()
    return vec

documents_collection = chroma_client.get_or_create_collection(name="documents_collection", embedding_function=zettel_note_embed)

'''
Zettelkasten document
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
    title
    filepath
}
'''
# TODO: Tidy up the messy sync scripts
# Question: Should Zettelkasten notes always have user_id, even if synced locally?

LOCAL_DOCS_FOLDER = config('LOCAL_DOCS_FOLDER')

class ZettelkastenSkill(SkillBase):
    @classmethod
    @register_event_listener('email_received')
    def save_document(cls, email):
        title = email.subject
        if title == '':
            title = str(int(time.time()*1000))
        title += '.md'
        filepath = os.path.join(LOCAL_DOCS_FOLDER, title)
        print("creating file at ", filepath)
        f = open(filepath, "x")
        f.write(email.content)

        doc_uuid = Zettelkasten.add_document(
            email.content,
            {
                'user_id': email.sender_user_id,
                'source_email_id': email.id
            }
        )
        return doc_uuid

class Zettelkasten(DocumentsBase):
    @classmethod
    def get_documents(cls, ids=None, where={}):
        '''e.g. get_document(sha="foo-bar")'''
        return documents_collection.get(
            ids=ids,
            where=where
        )

    @classmethod
    def get_relevant_documents(cls, doc_strings, n_results=25, where={}, include=['documents']):
        results = documents_collection.query(
            query_texts=doc_strings,
            n_results=n_results,
            where=where,
            where_document={},
            include=include
        )
        # I could put in re-ranking?
        return results

    @classmethod
    def add_document(cls, doc_string, metadata={}):
        if doc_string == '':
            print('err: empty doc_string, skipping')
            return

        keys_to_keep = ['user_id', 'source_email_id', 'title', 'filepath']
        metad = {k: metadata[k] for k in keys_to_keep if k in metadata}
        uuid = cls.generate_uuid()
        sha = cls.doc_sha(doc_string)
        now = cls.now_str()
        meta = {
            "sha": sha,
            "created_at": now,
            "last_modified_at": now,
            **metad
        }
        documents_collection.add(
            documents=[doc_string],
            metadatas=[meta],
            ids=[uuid]
        )
        return uuid

    @classmethod
    def check_for_existing_email_doc(cls, email):
        sha = cls.doc_sha(email.content)
        return cls.get_documents(where={ '$or': [{'sha': sha}, {'source_email_id': email.id}] })

    @classmethod
    def check_for_existing_file_doc(cls, fileStr):
        sha = cls.doc_sha(fileStr)
        return documents_collection.get(
            ids=[],
            where={ 'sha': sha }
        )

    @classmethod
    def upsert_documents(cls, ids, metadatas, documents):
        now = cls.now_str()
        metads = [{**m, "last_modified_at": now} for m in metadatas]
        return documents_collection.update(
            ids=ids,
            metadatas=metads,
            documents=documents,
        )
    
    @classmethod
    def update_document_metadata(cls, ids, metadatas):
        existing_metadatas = documents_collection.get(ids)['metadatas']
        now = cls.now_str()
        metads = [{ **existing_metadatas[i], **metadatas, "last_modified_at": now } for i in range(0, len(metadatas))]
        return documents_collection.update(
            ids=ids,
            metadatas=metads,
        )

    @classmethod
    def delete_documents(cls, ids):
        return documents_collection.delete(
            ids=ids,
        )
