import os
from .zettel import Zettel
from src.models import db_session


class FileManagementService:
    CONTENT_MARKER = '## ؜'
    SUPPORTED_FILE_EXTENSIONS = ['.md']

    def __init__(self) -> None:
        self.numDocsMade = 0
        self.numExistingFilesSkipped = 0
        self.numSkippedInvalidItems = 0
        self.numFilesMetadataUpdated = 0
        self.numFilesDeleted = 0
        self.itemCount = 0
        self.zettelsWithoutFileDeleted = 0
        self.allShasInFiles = set()

    def sync_documents_from_folder(self, folderPath, user):
        self.add_documents_from_folder(folderPath, user)
        self.delete_documents_missing_from_folder()
        self.print_sync_info()

    def add_documents_from_folder(self, folderPath, user):
        allDocs = db_session.query(Zettel).filter_by(user_id=user.id).all()
        print(f"{len(allDocs)} synced docs in db")
        items = os.listdir(folderPath)
        self.itemCount = len(items)
        for item in items:
            if item.startswith('.'):
                self.numSkippedInvalidItems += 1
                continue
            if not os.path.isfile(os.path.join(folderPath, item)):
                self.numSkippedInvalidItems += 1
                continue
            if not any(item.endswith(fileExtension) for fileExtension in self.SUPPORTED_FILE_EXTENSIONS):
                self.numSkippedInvalidItems += 1
                continue
            item_path = os.path.join(folderPath, item)
            with open(item_path, 'r') as f:
                data = f.read()
                filtered_data = self.filter_out_metadata(data)
                fileContentSha = Zettel.doc_sha(filtered_data)
                self.allShasInFiles.add(fileContentSha)
                title = item.removesuffix('.md')
                existingZettels = db_session.query(Zettel).filter_by(sha=fileContentSha).all()
                if len(existingZettels) == 0:
                    # create
                    newZettel = Zettel(
                        content=filtered_data,
                        user_id=user.id,
                        title=title,
                        filepath=item_path
                    )
                    self.numDocsMade += 1
                    db_session.add(newZettel)
                    continue
                if len(existingZettels) > 1:
                    print('found multiple docs, deleting duplicates: ', [z.id for z in existingZettels[1:]])
                    duplicates = existingZettels[1:]
                    for dup in duplicates:
                        db_session.delete(dup)
                    self.numFilesDeleted += len(duplicates)
                if len(existingZettels) > 0:
                    # repair
                    upsert_needed = False
                    ztl = existingZettels[0]
                    if ztl.content != filtered_data:
                        ztl.content = filtered_data
                        db_session.add(ztl)
                        upsert_needed = True
                    if ztl.title != title:
                        ztl.title = title
                        db_session.add(ztl)
                        upsert_needed = True
                    if ztl.filepath != item_path:
                        upsert_needed = True
                        ztl.filepath = item_path
                        db_session.add(ztl)
                    if upsert_needed:
                        print("Repairing: ", [ztl.id for ztl in existingZettels])
                        self.numFilesMetadataUpdated += 1
                    else:
                        self.numExistingFilesSkipped += 1
                    continue

    def delete_documents_missing_from_folder(self):
        zettelsToDelete = db_session.query(Zettel).filter(~Zettel.sha.in_(self.allShasInFiles)).all()
        self.zettelsWithoutFileDeleted = len(zettelsToDelete)
        for ztl in zettelsToDelete:
            print("deleting Zettel: ", ztl)
            db_session.delete(ztl)
    
    def print_sync_info(self):
        print("\n")
        print(f"found {self.itemCount} items in folder")
        print(f"Skipped {self.numSkippedInvalidItems} because they were folders or did not have a supported file extension")
        print(f"Created {self.numDocsMade} docs")
        print(f"Skipped {self.numExistingFilesSkipped} files because they already existed")
        print(f"Updated metadata to {self.numFilesMetadataUpdated} files")
        print(f"Deleted {self.numFilesDeleted} files with duplicate shas")
        print(f"Deleted {self.zettelsWithoutFileDeleted} docs without a corresponding file")
        numDocs = db_session.query(Zettel).count()
        print(f"Now {numDocs} synced docs in db")

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
