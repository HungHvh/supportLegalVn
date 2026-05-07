import sqlite3
import os
import unicodedata

from core.constants import SQLITE_PATH


def normalize_so_ky_hieu_key(value: str | None) -> str:
    if not value:
        return ""
    text = unicodedata.normalize("NFD", value.strip().lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.replace("đ", "d")
    text = text.replace("/", " ").replace("-", " ").replace("_", " ")
    text = " ".join(text.split())
    return text


def normalize_so_ky_hieu(value: str | None) -> str:
    return normalize_so_ky_hieu_key(value)

def get_db_connection(db_path: str = SQLITE_PATH) -> sqlite3.Connection:
    """
    Tạo kết nối tới SQLite với các tùy chỉnh tối ưu cho tập dữ liệu lớn.
    """
    db_path = os.getenv("SQLITE_DB_PATH", db_path)
    # Convert relative paths to absolute paths based on project root
    if not os.path.isabs(db_path):
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        db_path = os.path.join(project_root, db_path)
    # Ensure directory exists
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    # Kích hoạt WAL mode để tối ưu đọc/ghi đồng thời
    try:
        # lỗi mount giữa window và linux có thể
        # conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA journal_mode = DELETE;")
    except sqlite3.OperationalError:
        # Một số filesystem (bind mounts trên Windows, vboxfs, vfs) không hỗ trợ WAL.
        # Trong trường hợp đó, fallback về DELETE để tránh disk I/O error.
        try:
            conn.execute("PRAGMA journal_mode = DELETE;")
        except Exception:
            # Nếu vẫn lỗi, tiếp tục mà không đặt journal mode (SQLite sẽ dùng mặc định)
            pass

    # Tăng kích thước bộ nhớ đệm (mmap) lên khoảng 3GB nếu có hỗ trợ
    try:
        conn.execute("PRAGMA mmap_size = 3000000000;")
    except sqlite3.OperationalError:
        # mmap có thể không được hỗ trợ; bỏ qua nếu lỗi
        pass
    conn.row_factory = sqlite3.Row
    return conn

def init_db(db_path: str = SQLITE_PATH, drop_existing: bool = False):
    """
    Khởi tạo cấu trúc bảng cho Phase 10: Parent-Document Retrieval.
    Bao gồm bảng legal_articles (Điều) và legal_chunks (Khoản/Điểm).
    """
    db_path = os.getenv("SQLITE_DB_PATH", db_path)
    # Convert relative paths to absolute paths based on project root
    if not os.path.isabs(db_path):
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        db_path = os.path.join(project_root, db_path)
    # Ensure directory exists
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    if drop_existing:
        print(f"Dropping existing tables in {db_path}...")
        cursor.execute("DROP TABLE IF EXISTS legal_documents")
        cursor.execute("DROP TABLE IF EXISTS docs_fts")
        cursor.execute("DROP TABLE IF EXISTS indexing_status")
        cursor.execute("DROP TABLE IF EXISTS legal_articles")
        cursor.execute("DROP TABLE IF EXISTS legal_chunks")
        cursor.execute("DROP TABLE IF EXISTS chunks_fts")
        cursor.execute("DROP INDEX IF EXISTS idx_la_doc_id")
        cursor.execute("DROP INDEX IF EXISTS idx_la_so_ky_hieu")
        cursor.execute("DROP INDEX IF EXISTS idx_la_so_ky_hieu_norm")
        cursor.execute("DROP INDEX IF EXISTS idx_lc_article_uuid")
        cursor.execute("DROP INDEX IF EXISTS idx_lc_doc_id")
        cursor.execute("DROP TRIGGER IF EXISTS legal_documents_ai")
        cursor.execute("DROP TRIGGER IF EXISTS legal_documents_ad")
        cursor.execute("DROP TRIGGER IF EXISTS legal_documents_au")
        cursor.execute("DROP TRIGGER IF EXISTS chunks_fts_insert")

    # 1. Bảng legal_articles (Parent document store - full Điều)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS legal_articles (
        article_uuid  TEXT PRIMARY KEY,
        doc_id        TEXT NOT NULL,
        so_ky_hieu    TEXT,
        so_ky_hieu_norm TEXT,
        article_title TEXT,
        article_path  TEXT,
        full_content  TEXT NOT NULL
    );
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_la_doc_id ON legal_articles(doc_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_la_so_ky_hieu ON legal_articles(so_ky_hieu);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_la_so_ky_hieu_norm ON legal_articles(so_ky_hieu_norm);")

    # 2. Bảng legal_chunks (Chunk store - Khoản-level, links to article)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS legal_chunks (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        chunk_id     TEXT UNIQUE NOT NULL,
        article_uuid TEXT NOT NULL REFERENCES legal_articles(article_uuid),
        doc_id       TEXT NOT NULL,
        so_ky_hieu   TEXT,
        level        TEXT,        -- "KHOẢN" | "ĐIỂM" | "ARTICLE"
        chunk_path   TEXT,
        content      TEXT NOT NULL
    );
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_lc_article_uuid ON legal_chunks(article_uuid);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_lc_doc_id ON legal_chunks(doc_id);")

    # 3. Bảng ảo chunks_fts (FTS5 trên chunks)
    # Tokenize unicode61 để hỗ trợ tiếng Việt có dấu
    cursor.execute("""
    CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
        chunk_id     UNINDEXED,
        content,
        article_title,
        article_uuid UNINDEXED,
        so_ky_hieu   UNINDEXED,
        tokenize='unicode61 remove_diacritics 0'
    );
    """)

    # 4. Trigger auto-populate FTS5
    cursor.execute("""
    CREATE TRIGGER IF NOT EXISTS chunks_fts_insert AFTER INSERT ON legal_chunks BEGIN
        INSERT INTO chunks_fts(chunk_id, content, article_title, article_uuid, so_ky_hieu)
        VALUES (
            new.chunk_id,
            new.content,
            (SELECT article_title FROM legal_articles WHERE article_uuid = new.article_uuid),
            new.article_uuid,
            new.so_ky_hieu
        );
    END;
    """)

    # 5. Bảng theo dõi tiến độ (Idempotency)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS indexing_status (
        doc_id       TEXT PRIMARY KEY,
        processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    conn.commit()
    conn.close()

def is_processed(conn: sqlite3.Connection, doc_id: str) -> bool:
    """Kiểm tra xem document đã được xử lý chưa."""
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM indexing_status WHERE doc_id = ?", (doc_id,))
    return cursor.fetchone() is not None

def mark_as_processed(conn: sqlite3.Connection, doc_id: str):
    """Đánh dấu document là đã xử lý xong."""
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO indexing_status (doc_id) VALUES (?)", (doc_id,))
    conn.commit()

if __name__ == "__main__":
    init_db()
    print("[OK] SQLite initialized with Phase 10 schema (Parent-Document Retrieval)")
