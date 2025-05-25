from src.user import User
from .zettel import Zettel, LOCAL_DOCS_FOLDER
from .zettelkasten_topic import ZettelkastenTopic
from src.app_setting import AppSetting
from src.skills.zettel.file_management_service import FileManagementService

def sync_local_docs():
    desktop_user_id = AppSetting.get('desktop_user_id')
    if desktop_user_id:
        user = User.query.filter_by(id=desktop_user_id).first()
        FileManagementService().sync_documents_from_folder(LOCAL_DOCS_FOLDER, user)

__all__ = ['Zettel','ZettelkastenTopic', 'LOCAL_DOCS_FOLDER']
