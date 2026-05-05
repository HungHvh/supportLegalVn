import os

from qdrant_client import QdrantClient
from qdrant_client.http import models

class QdrantManager:
    def __init__(self, host: str = None, port: int = None):
        self.host = host or os.getenv("QDRANT_HOST", "localhost")
        # Chuyển mặc định sang 6334 cho gRPC
        self.port = int(port or os.getenv("QDRANT_PORT", 6334))
        # Sử dụng prefer_grpc=True để tối ưu hiệu năng
        self.client = QdrantClient(host=self.host, port=self.port, prefer_grpc=True)
        
        # Khởi tạo sẵn Async client để dùng chung, tránh đóng mở liên tục
        from qdrant_client import AsyncQdrantClient
        self.async_client = AsyncQdrantClient(host=self.host, port=self.port, prefer_grpc=True)




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
            self.client.create_payload_index(collection_name, "nam_ban_hanh", models.PayloadSchemaType.INTEGER)
            self.client.create_payload_index(collection_name, "linh_vuc", models.PayloadSchemaType.KEYWORD)

        else:
            print(f"[INFO] Collection '{collection_name}' already exists.")

    def init_semantic_cache(self, vector_size: int = 768):
        """
        Khởi tạo collection cho Semantic Cache.
        """
        collection_name = "semantic_cache"
        if not self.client.collection_exists(collection_name):
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(
                    size=vector_size,
                    distance=models.Distance.COSINE
                )
            )
            # Index cho timestamp dọn dẹp
            self.client.create_payload_index(collection_name, "created_at", models.PayloadSchemaType.INTEGER)
            print(f"[OK] Semantic Cache Collection '{collection_name}' created.")
        else:
            print(f"[INFO] Collection '{collection_name}' already exists.")

    async def check_semantic_cache(self, query_vector: list, threshold: float = 0.95):
        """
        Tìm kiếm câu trả lời tương tự trong collection semantic_cache.
        """
        try:
            from qdrant_client.http import models as qmodels
            results = await self.async_client.query_points(
                collection_name="semantic_cache",
                query=query_vector,
                limit=1,
                score_threshold=threshold
            )

            
            if results and results.points:
                payload = results.points[0].payload
                import json
                citations = []
                try:
                    if "citations" in payload:
                        citations = json.loads(payload["citations"])
                except:
                    pass
                return {
                    "answer": payload.get("llm_response"),
                    "citations": citations
                }


        except Exception as e:
            print(f"[Warning] Semantic cache check failed: {e}")
        return None

    async def save_to_cache(self, query_text: str, query_vector: list, answer: str, citations: list = None):
        """
        Lưu câu trả lời và trích dẫn vào semantic_cache kèm theo timestamp.
        """
        try:
            import time
            import uuid
            import json
            
            point_id = str(uuid.uuid4())
            await self.async_client.upsert(
                collection_name="semantic_cache",
                points=[
                    models.PointStruct(
                        id=point_id,
                        vector=query_vector,
                        payload={
                            "query_text": query_text,
                            "llm_response": answer,
                            "citations": json.dumps(citations or []),
                            "created_at": int(time.time())
                        }
                    )
                ]
            )
            print(f"[OK] Saved query to semantic cache: {point_id}")

        except Exception as e:
            print(f"[Warning] Failed to save to semantic cache: {e}")

if __name__ == "__main__":
    # Test connection nếu Qdrant đang chạy
    try:
        mgr = QdrantManager()
        mgr.init_semantic_cache()
    except Exception as e:
        print(f"x Could not connect to Qdrant: {e}")
