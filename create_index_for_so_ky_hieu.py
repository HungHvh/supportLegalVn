import os
import sqlite3
import unicodedata


def normalize_so_ky_hieu(value: str | None) -> str:
    if not value:
        return ""
    text = unicodedata.normalize("NFD", value.strip().lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.replace("đ", "d")
    text = text.replace("/", " ").replace("-", " ").replace("_", " ")
    return " ".join(text.split())


def build_so_ky_hieu_index(db_path: str = "legal_poc.db") -> None:
    db_path = os.getenv("SQLITE_DB_PATH", db_path)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS so_ky_hieu_index (
            raw_so_ky_hieu TEXT PRIMARY KEY,
            norm_so_ky_hieu TEXT NOT NULL
        )
        """
    )
    cur.execute("DELETE FROM so_ky_hieu_index")

    cur.execute(
        "SELECT DISTINCT so_ky_hieu FROM legal_articles WHERE so_ky_hieu IS NOT NULL AND so_ky_hieu != ''"
    )
    rows = cur.fetchall()
    cur.executemany(
        "INSERT OR REPLACE INTO so_ky_hieu_index (raw_so_ky_hieu, norm_so_ky_hieu) VALUES (?, ?)",
        [(row[0], normalize_so_ky_hieu(row[0])) for row in rows],
    )

    cur.execute("CREATE INDEX IF NOT EXISTS idx_so_ky_hieu_index_norm ON so_ky_hieu_index(norm_so_ky_hieu)")
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_la_so_ky_hieu_norm ON legal_articles(so_ky_hieu_norm)"
    )

    conn.commit()
    conn.close()
    print("✔ so_ky_hieu lookup index ensured")


if __name__ == "__main__":
    build_so_ky_hieu_index()

