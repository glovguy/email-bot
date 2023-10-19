import src.models
import src.documents

if __name__ == "__main__":
    src.models.init_db()
    # src.documents.chroma_client.create_collection(name="documents_collection")
