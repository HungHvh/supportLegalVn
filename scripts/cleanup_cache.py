import time
import os
from qdrant_client import QdrantClient
from qdrant_client.http import models

from core.qdrant_config import resolve_qdrant_connection

def cleanup_cache(days=30):
    """
    Xóa các points trong semantic_cache có created_at cũ hơn số ngày quy định.
    """
    settings = resolve_qdrant_connection()
    host = settings.host
    # Sử dụng port gRPC 6334 theo kế hoạch Phase 18
    port = settings.port
    
    try:
        client = QdrantClient(host=host, port=port, prefer_grpc=True)
        
        # Tính toán mốc thời gian xóa
        cutoff = int(time.time()) - (days * 24 * 60 * 60)
        
        print(f"[Cleanup] Cleaning up semantic_cache...")
        print(f"[Cleanup] Cutoff: {cutoff} ({days} days ago)")
        
        # Thực hiện xóa dựa trên range filter
        result = client.delete(
            collection_name="semantic_cache",
            points_selector=models.Filter(
                must=[
                    models.FieldCondition(
                        key="created_at",
                        range=models.Range(
                            lt=cutoff
                        )
                    )
                ]
            )
        )
        print(f"[OK] Cleanup result: {result}")
    except Exception as e:
        print(f"[Error] Cache cleanup failed: {e}")


if __name__ == "__main__":
    # Mặc định dọn dẹp các entry cũ hơn 30 ngày
    cleanup_cache(days=10)
