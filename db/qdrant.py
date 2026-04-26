from qdrant_client import QdrantClient
from qdrant_client.http import models

class QdrantManager:
    def __init__(self, host: str = "localhost", port: int = 6333):
        self.client = QdrantClient(host=host, port=port)

    def init_collection(self, collection_name: str, vector_size: int = 768):
        """
        Khởi tạo collection với cấu trúc Hybrid (Dense + Sparse).
        """
        if not self.client.collection_exists(collection_name):
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config={
                    "dense": models.VectorParams(
                        size=vector_size,
                        distance=models.Distance.COSINE
                    )
                },
                sparse_vectors_config={
                    "sparse": models.SparseVectorParams(
                        index=models.SparseIndexParams(on_disk=False)
                    )
                }
            )
            print(f"[OK] Hybrid Collection '{collection_name}' created in Qdrant.")
            
            # Tạo index cho payload để lọc nhanh
            self.client.create_payload_index(collection_name, "doc_id", models.PayloadSchemaType.KEYWORD)
            self.client.create_payload_index(collection_name, "law_name", models.PayloadSchemaType.KEYWORD)
        else:
            print(f"[INFO] Collection '{collection_name}' already exists.")

if __name__ == "__main__":
    # Test connection nếu Qdrant đang chạy
    try:
        mgr = QdrantManager()
        mgr.init_collection("legal_chunks")
    except Exception as e:
        print(f"x Could not connect to Qdrant: {e}")
