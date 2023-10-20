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

def embed(doc_string):
    # print("embed doc_string: ", type(doc_string), doc_string)
    instruction = "Represent the personal Zettelkasten note for storing and retrieving personal insights: "
    vec = embeddings_model.encode([[instruction, doc_string[0]]]).tolist()
    # print("vec type: ", type(vec))
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
    def get_relevant_documents(cls, doc_string, relevance_threshold=0.8):
        docs = documents_collection.query(
            query_texts=[doc_string],
            n_results=10,
            where={},
            where_document={}
        )
        # print(docs)
        # print(docs['distances'][0][0])
        return [docs['documents'][0][i] for i in range(0, len(docs['ids'][0])) if docs['distances'][0][i] <= relevance_threshold]

    @classmethod
    def add_document(cls, doc_string, metadata={}):
        if doc_string == '':
            return
        keys_to_keep = ['user_id', 'source_email_id']
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
            with open(os.path.join(folderPath, item), 'r') as f:
                data = f.read()
                filtered_data = FileFilter().filter_out_metadata(data)
                exts = cls.check_for_existing_file_doc(filtered_data)
                if len(exts.get('ids')) > 0:
                    print('found a doc: ', exts)
                    numFilesSkipped += 1
                    continue
                
                cls.add_document(filtered_data)
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
        if [kwargs.get('uuid')] is not None:
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
