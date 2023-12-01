from decouple import config
import os
import time
from src.skills.base import DocumentsBase, SkillBase, chroma_client, default_embeddings_model

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
}
'''
# to add: title, filepath
# That way I can add the title in prompts
# then re-add the local files via a script? Or maybe a "repair" script would be better?

LOCAL_DOCS_FOLDER = config('LOCAL_DOCS_FOLDER')

class ZettelkastenSkill(SkillBase):
    @classmethod
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
    def get_relevant_documents(cls, doc_strings, n_results=7, where={}, include=['documents']):
        results = documents_collection.query(
            query_texts=doc_strings,
            n_results=n_results,
            where=where,
            where_document={},
            include=include
        )
        # I could put in a relevance_threshold filter?
        return results

    @classmethod
    def add_document(cls, doc_string, metadata={}):
        if doc_string == '':
            return

        keys_to_keep = ['user_id', 'source_email_id', 'title']
        metad = {k: metadata[k] for k in keys_to_keep if k in metadata}
        uuid = cls.generate_uuid()
        sha = cls.doc_sha(doc_string)
        now = cls.now_str()
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
    def check_for_existing_email_doc(cls, email):
        sha = cls.doc_sha(email.content)
        return cls.get_document(**{ '$or': [{'sha': sha}, {'source_email_id': email.id}] })

    @classmethod
    def check_for_existing_file_doc(cls, fileStr):
        sha = cls.doc_sha(fileStr)
        return documents_collection.get(
            ids=[],
            where={ 'sha': sha }
        )

    @classmethod
    def get_document(cls, **kwargs):
        '''e.g. get_document(sha="foo-bar")'''
        ids = []
        if kwargs.get('uuid') is not None:
            ids = [kwargs.get('uuid')]
        return documents_collection.get(
            ids=ids,
            where=kwargs
        )


class FileFilterService:
    def __init__(cls):
        cls.content_marker = '## ؜'

    @classmethod
    def add_documents_from_folder(cls, folderPath):
        numDocsMade = 0
        numFilesSkipped = 0
        numFolderItems = 0
        items = os.listdir(folderPath)
        for item in items:
            if not os.path.isfile(os.path.join(folderPath, item)):
                numFolderItems += 1
                continue
            item_path = os.path.join(folderPath, item)
            with open(item_path, 'r') as f:
                data = f.read()
                filtered_data = cls.filter_out_metadata(data)
                exts = Zettelkasten.check_for_existing_file_doc(filtered_data)
                if len(exts.get('ids')) > 0:
                    print('found a doc: ', exts)
                    numFilesSkipped += 1
                    continue

                Zettelkasten.add_document(filtered_data, { "title": item })
                numDocsMade += 1
        print("found ", len(items), " items in folder")
        print(numFolderItems, " were folders and skipped")
        print("Made ", numDocsMade, " docs")
        print("Skipped ", numFilesSkipped, " files because they already existed")

    def filter_out_metadata(cls, text: str) -> str:
        current_depth = cls.content_marker.count('#')
        recording = True
        lines = text.split('\n')
        filtered_lines = []

        for line in lines:
            if cls.content_marker and line == cls.content_marker:
                recording = True
                continue
            elif line.startswith('#') and '# ' in line:
                [header_tag, *_] = line.split(' ')
                depth = header_tag.count('#')
                if depth >= current_depth:
                    recording = False
                    continue
            if recording:
                filtered_lines.append(line)

        return '\n'.join(filtered_lines)
