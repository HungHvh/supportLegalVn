import sqlite3

from core.constants import SQLITE_PATH


def build_article_fts(db_path=SQLITE_PATH):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # 1. create FTS
    cur.execute("""
    CREATE VIRTUAL TABLE IF NOT EXISTS article_titles_fts USING fts5(
        article_uuid UNINDEXED,
        article_title
    )
    """)

    # 2. insert missing
    cur.execute("""
    INSERT INTO article_titles_fts (article_uuid, article_title)
    SELECT la.article_uuid, la.article_title
    FROM legal_articles la
    LEFT JOIN article_titles_fts fts
    ON la.article_uuid = fts.article_uuid
    WHERE fts.article_uuid IS NULL
    """)

    conn.commit()
    conn.close()
    print("✔ FTS build/update done")

if __name__ == "__main__":
    build_article_fts()