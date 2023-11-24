import chromadb
from decouple import config
from datetime import datetime
from hashlib import sha256
from InstructorEmbedding import INSTRUCTOR
import uuid6
import os

os.environ["TOKENIZERS_PARALLELISM"] = "false"

chroma_client = chromadb.PersistentClient(path="./documents_collection")
embeddings_model = INSTRUCTOR('hkunlp/instructor-base')

def zettel_note_embed(doc_string):
    instruction = "Represent the personal Zettelkasten note for storing and retrieving personal insights: "
    vec = embeddings_model.encode([[instruction, doc_string[0]]]).tolist()
    return vec

def botbrain_note_embed(doc_string):
    instruction = "Represent this note written about the user's preferences and personality: "
    vec = embeddings_model.encode([[instruction, doc_string[0]]]).tolist()
    return vec

documents_collection = chroma_client.get_or_create_collection(name="documents_collection", embedding_function=zettel_note_embed)
botbrain_collection = chroma_client.get_or_create_collection(name="botbrain_collection", embedding_function=botbrain_note_embed)

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

LOCAL_DOCS_FOLDER = config('LOCAL_DOCS_FOLDER')

class Zettelkasten:
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
        # return [results['documents'][0][i] for i in range(0, len(results['ids'][0]))]

    @classmethod
    def add_document(cls, doc_string, metadata={}):
        if doc_string == '':
            return

        keys_to_keep = ['user_id', 'source_email_id', 'title']
        metad = {k: metadata[k] for k in keys_to_keep if k in metadata}
        uuid = str(uuid6.uuid7())
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
                filtered_data = FileFilter().filter_out_metadata(data)
                exts = cls.check_for_existing_file_doc(filtered_data)
                if len(exts.get('ids')) > 0:
                    print('found a doc: ', exts)
                    numFilesSkipped += 1
                    continue

                cls.add_document(filtered_data, { "title": item })
                numDocsMade += 1
        print("found ", len(items), " items in folder")
        print(numFolderItems, " were folders and skipped")
        print("Made ", numDocsMade, " docs")
        print("Skipped ", numFilesSkipped, " files because they already existed")

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

    @classmethod
    def doc_sha(cls, doc_string):
        return sha256(doc_string.encode('utf-8')).hexdigest()

class FileFilter:
    def __init__(self):
        self.content_marker = '## ؜'

    def filter_out_metadata(self, text: str) -> str:
        current_depth = self.content_marker.count('#')
        recording = True
        lines = text.split('\n')
        filtered_lines = []

        for line in lines:
            if self.content_marker and line == self.content_marker:
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
