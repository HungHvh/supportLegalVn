import sqlite3
import os
from typing import Generator

def get_db_connection(db_path: str = "legal_poc.db") -> sqlite3.Connection:
    """
    Tạo kết nối tới SQLite với các tùy chỉnh tối ưu cho tập dữ liệu lớn.
    """
    conn = sqlite3.connect(db_path)
    # Kích hoạt WAL mode để tối ưu đọc/ghi đồng thời
    conn.execute("PRAGMA journal_mode = WAL;")
    # Tăng kích thước bộ nhớ đệm (mmap) lên khoảng 3GB
    conn.execute("PRAGMA mmap_size = 3000000000;")
    conn.row_factory = sqlite3.Row
    return conn

def init_db(db_path: str = "legal_poc.db"):
    """
    Khởi tạo cấu trúc bảng với FTS5 sử dụng External Content để tiết kiệm dung lượng.
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    
    # 1. Bảng lưu Metadata gốc
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS legal_documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        doc_id TEXT UNIQUE,
        so_ky_hieu TEXT,
        headers TEXT,
        content TEXT,
        domain TEXT
    );
    """)
    
    # 2. Bảng ảo FTS5 (External Content)
    # Sử dụng content='legal_documents' để tránh nhân đôi dữ liệu 3.6GB
    # Tokenize unicode61 để hỗ trợ tiếng Việt có dấu
    # dùng để đánh inverted index cho 2 trường này (so_ky_hieu, content), key là từ khóa, value là id của document
    cursor.execute("""
    CREATE VIRTUAL TABLE IF NOT EXISTS docs_fts USING fts5(
        so_ky_hieu,
        content,
        content='legal_documents',
        content_rowid='id',
        tokenize='unicode61 remove_diacritics 0'
    );
    """)
    
    # 3. Triggers để đồng bộ hóa FTS5 khi bảng gốc thay đổi (Khuyến nghị cho External Content)
    cursor.execute("""
    CREATE TRIGGER IF NOT EXISTS legal_documents_ai AFTER INSERT ON legal_documents BEGIN
      INSERT INTO docs_fts(rowid, so_ky_hieu, content) VALUES (new.id, new.so_ky_hieu, new.content);
    END;
    """)
    
    cursor.execute("""
    CREATE TRIGGER IF NOT EXISTS legal_documents_ad AFTER DELETE ON legal_documents BEGIN
      INSERT INTO docs_fts(docs_fts, rowid, so_ky_hieu, content) VALUES('delete', old.id, old.so_ky_hieu, old.content);
    END;
    """)
    
    cursor.execute("""
    CREATE TRIGGER IF NOT EXISTS legal_documents_au AFTER UPDATE ON legal_documents BEGIN
      INSERT INTO docs_fts(docs_fts, rowid, so_ky_hieu, content) VALUES('delete', old.id, old.so_ky_hieu, old.content);
      INSERT INTO docs_fts(rowid, so_ky_hieu, content) VALUES (new.id, new.so_ky_hieu, new.content);
    END;
    """)
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("[OK] SQLite initialized with WAL mode and FTS5 (External Content + Vietnamese tokenizer)")
