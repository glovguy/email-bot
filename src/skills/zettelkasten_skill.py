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

    @classmethod
    def upsert_documents(cls, ids, metadatas, documents):
        return documents_collection.update(
            ids=ids,
            metadatas=metadatas,
            documents=documents,
        )

    @classmethod
    def delete_documents(cls, ids):
        return documents_collection.delete(
            ids=ids,
        )


class FileManagementService:
    CONTENT_MARKER = '## ؜'
    SUPPORTED_FILE_EXTENSIONS = ['.md']

    @classmethod
    def remove_empty_documents(cls):
        empty_string_sha = Zettelkasten.doc_sha('')
        docs = Zettelkasten.get_document(sha=empty_string_sha)
        if len(docs.get('ids')) > 0:
            print("Deleting ", len(docs.get('ids')), " empty docs")
            print(docs)
            Zettelkasten.delete_documents(docs.get('ids'))

    @classmethod
    def sync_documents_from_folder(cls, folderPath):
        cls.add_documents_from_folder(folderPath)
        cls.delete_documents_missing_from_folder(folderPath)

    @classmethod
    def add_documents_from_folder(cls, folderPath):
        numDocsMade = 0
        numExistingFilesSkipped = 0
        numSkippedInvalidItems = 0
        numFilesMetadataUpdated = 0
        numFilesDeleted = 0
        allShasInFiles = set()
        allDocs = Zettelkasten.get_document()
        print(len(allDocs.get('ids')), " synced docs in db")
        items = os.listdir(folderPath)
        for item in items:
            if item.startswith('.'):
                continue
            if not os.path.isfile(os.path.join(folderPath, item)):
                numSkippedInvalidItems += 1
                continue
            if not any(item.endswith(fileExtension) for fileExtension in cls.SUPPORTED_FILE_EXTENSIONS):
                numSkippedInvalidItems += 1
                continue
            item_path = os.path.join(folderPath, item)
            with open(item_path, 'r') as f:
                data = f.read()
                filtered_data = cls.filter_out_metadata(data)
                allShasInFiles.add(Zettelkasten.doc_sha(filtered_data))
                title = item.removesuffix('.md')
                exts = Zettelkasten.check_for_existing_file_doc(filtered_data)
                if len(exts.get('ids')) == 0:
                    # create
                    Zettelkasten.add_document(filtered_data, { "title": title, "filepath": item_path })
                    numDocsMade += 1
                    continue
                if len(exts.get('ids')) > 1:
                    print('found multiple docs, deleting duplicates: ', exts.get('ids')[1:])
                    Zettelkasten.delete_documents(exts.get('ids')[1:])
                    numFilesDeleted += len(exts.get('ids')[1:])
                if len(exts.get('ids')) > 0:
                    # repair
                    upsert_needed = False
                    metad = exts.get('metadatas')[0]
                    new_metad = metad
                    doc = exts.get('documents')[0]
                    new_doc = doc
                    if doc != filtered_data:
                        new_doc = filtered_data
                        upsert_needed = True
                    if metad.get('title') != title:
                        new_metad = { **metad, "title": title }
                        upsert_needed = True
                    if metad.get('filepath') != item_path:
                        new_metad = { **metad, "filepath": item_path }
                        upsert_needed = True
                    if upsert_needed:
                        print("Repairing: ", exts.get('ids'))
                        Zettelkasten.upsert_documents(
                            [exts.get('ids')[0]],
                            new_metad,
                            [new_doc]
                        )
                        numFilesMetadataUpdated += 1
                    else:
                        numExistingFilesSkipped += 1
                    continue
        # Remove docs in db without file
        allDocs = Zettelkasten.get_document()
        docIdsToDelete = [allDocs.get('ids')[i] for i in range(0, len(allDocs.get('ids'))) if allDocs.get('metadatas')[i].get('sha') not in allShasInFiles]
        if len(docIdsToDelete) > 0:
            Zettelkasten.delete_documents(ids=docIdsToDelete)
        print("\n\n")
        print("found ", len(items), " items in folder")
        print("Skipped ", numSkippedInvalidItems, " because they were folders or did not have a supported file extension")
        print("Created ", numDocsMade, " docs")
        print("Skipped ", numExistingFilesSkipped, " files because they already existed")
        print("Updated metadata to ", numFilesMetadataUpdated, " files")
        print("Deleted ", numFilesDeleted, " files with duplicate shas")
        print("Deleted ", len(docIdsToDelete), " docs without a corresponding file")
        allDocsIds = Zettelkasten.get_document().get('ids')
        print("Now ", len(allDocsIds), " synced docs in db")

    @classmethod
    def delete_documents_missing_from_folder(cls, folderPath):
        numFilesDeleted = 0
        docs = Zettelkasten.get_document()
        items = [os.path.join(folderPath, item) for item in os.listdir(folderPath)]
        for i in range(0, len(docs.get('metadatas'))):
            metad = docs.get('metadatas')[i]
            doc = docs.get('documents')[i]
            id = docs.get('ids')[i]
            if metad.get('filepath') is None:
                print(" Deleting doc ", metad, doc)
                Zettelkasten.delete_documents([id])
                numFilesDeleted += 1
                continue
            doc_filepath = metad.get('filepath')
            if doc_filepath not in items:
                print("Deleting doc  ", metad, doc)
                numFilesDeleted += 1
                Zettelkasten.delete_documents([id])
        print("Deleted ", numFilesDeleted, " files")

    @classmethod
    def filter_out_metadata(cls, text: str) -> str:
        if cls.CONTENT_MARKER not in text:
            current_depth = 0
        else:
            current_depth = cls.CONTENT_MARKER.count('#')
        recording = True
        lines = text.split('\n')
        filtered_lines = []
        for line in lines:
            if cls.CONTENT_MARKER and line == cls.CONTENT_MARKER:
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
