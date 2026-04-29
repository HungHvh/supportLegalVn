import asyncio
import sqlite3
import os
import sys

# Thêm root dự án vào path để import được các module
sys.path.append(os.getcwd())

async def test_embedding_provider():
    print("\n--- Testing Embedding Provider ---")
    try:
        from core.embeddings import VietnameseSBERTProvider
        provider = VietnameseSBERTProvider()
        text = "Cộng hòa Xã hội Chủ nghĩa Việt Nam"
        vector = await provider.get_embedding(text)
        print(f"[OK] Generated vector size: {len(vector)}")
        if len(vector) == provider.dimension:
            print(f"[PASS] Vector size matches provider dimension ({provider.dimension}).")
        else:
            print(f"[FAIL] Unexpected vector size: {len(vector)}")
    except Exception as e:
        print(f"[FAIL] Embedding Test Error: {e}")

def test_sqlite_tokenizer():
    print("\n--- Testing SQLite FTS5 Vietnamese Tokenizer ---")
    db_path = "legal_poc.db"
    try:
        conn = sqlite3.connect(db_path)
        # Chèn thử dữ liệu có dấu
        conn.execute("INSERT OR IGNORE INTO legal_documents (doc_id, so_ky_hieu, content) VALUES (?, ?, ?)", 
                     ("test1", "123/2024/QH15", "Luật đất đai và quy định mới"))
        conn.commit()
        
        # Thử tìm kiếm với từ khóa có dấu (đất đai)
        res = conn.execute("SELECT * FROM docs_fts WHERE content MATCH 'đất đai'").fetchone()
        if res:
            print("[PASS] Found document with diacritics search 'dat dai (Vietnamese)'")
        else:
            # Thử tìm kiếm không dấu
            res_no_diacritics = conn.execute("SELECT * FROM docs_fts WHERE content MATCH 'dat dai'").fetchone()
            if res_no_diacritics:
                 print("[INFO] Found via unmarked search 'dat dai'. check tokenizer settings.")
            print("[FAIL] Could not find Vietnamese text in FTS5 index.")
            
        conn.close()
    except Exception as e:
        print(f"[FAIL] SQLite Test Error: {e}")

async def main():
    # 1. Kiểm tra File existence
    print("--- File Stability Check ---")
    files = ["docker-compose.yml", ".env.example", "db/sqlite.py", "core/embeddings.py"]
    for f in files:
        if os.path.exists(f):
            print(f"[OK] {f} exists.")
        else:
            print(f"[MISSING] {f} not found.")

    # 2. Chạy tests
    test_sqlite_tokenizer()
    await test_embedding_provider()

if __name__ == "__main__":
    asyncio.run(main())
