import sqlite3

def print_schema():
    conn = sqlite3.connect('sqlite_data/legal_poc.db')
    cursor = conn.cursor()
    cursor.execute("SELECT count(*) FROM legal_articles")
    for row in cursor.fetchall():
        print(f"Total articles: {row[0]}")
        # print(f"Table: {row[0]}")
        # print(f"SQL: {row[1]}")
        # print("-" * 50)
    conn.close()

if __name__ == '__main__':
    print_schema()
