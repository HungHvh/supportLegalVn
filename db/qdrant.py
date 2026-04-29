import os

from qdrant_client import QdrantClient
from qdrant_client.http import models

class QdrantManager:
    def __init__(self, host: str = None, port: int = None):
        host = host or os.getenv("QDRANT_HOST", "localhost")
        port = int(port or os.getenv("QDRANT_PORT", 6333))
        self.client = QdrantClient(host=host, port=port)

    def init_collection(self, collection_name: str, vector_size: int = 768):
        """
        Khởi tạo collection với cấu trúc Hybrid (Dense + Sparse).
        """
        if self.client.collection_exists(collection_name):
            try:
                info = self.client.get_collection(collection_name)
                vectors = info.config.params.vectors
                current_dense = vectors.get("dense") if isinstance(vectors, dict) else vectors
                current_size = getattr(current_dense, "size", None)

                if current_size != vector_size:
                    self.client.delete_collection(collection_name)
                    print(
                        f"[WARN] Recreated collection '{collection_name}' to match vector size "
                        f"{vector_size} (was {current_size})."
                    )
                else:
                    print(f"[INFO] Collection '{collection_name}' already exists.")
                    return
            except Exception:
                self.client.delete_collection(collection_name)

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
            self.client.create_payload_index(collection_name, "so_ky_hieu", models.PayloadSchemaType.KEYWORD)
        else:
            print(f"[INFO] Collection '{collection_name}' already exists.")

if __name__ == "__main__":
    # Test connection nếu Qdrant đang chạy
    try:
        mgr = QdrantManager()
        mgr.init_collection("legal_chunks")
    except Exception as e:
        print(f"x Could not connect to Qdrant: {e}")
