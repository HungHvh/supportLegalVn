import sqlite3

def print_schema():
    conn = sqlite3.connect('sqlite_data/legal_poc.db')
    cursor = conn.cursor()
    cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='table' AND name LIKE '%fts%' OR name='legal_articles'")
    for row in cursor.fetchall():
        print(f"Table: {row[0]}")
        print(f"SQL: {row[1]}")
        print("-" * 50)
    conn.close()

if __name__ == '__main__':
    print_schema()
