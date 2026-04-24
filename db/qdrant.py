from qdrant_client import QdrantClient
from qdrant_client.http import models

class QdrantManager:
    def __init__(self, host: str = "localhost", port: int = 6333):
        self.client = QdrantClient(host=host, port=port)

    def init_collection(self, collection_name: str, vector_size: int = 768):
        """
        Khởi tạo collection nếu chưa tồn tại.
        Mặc định dùng Cosine similarity cho Vietnamese-SBERT.
        """
        if not self.client.collection_exists(collection_name):
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(
                    size=vector_size,
                    distance=models.Distance.COSINE
                )
            )
            print(f"[OK] Collection '{collection_name}' created in Qdrant.")
        else:
            print(f"[INFO] Collection '{collection_name}' already exists.")

if __name__ == "__main__":
    # Test connection nếu Qdrant đang chạy
    try:
        mgr = QdrantManager()
        mgr.init_collection("legal_chunks")
    except Exception as e:
        print(f"x Could not connect to Qdrant: {e}")
