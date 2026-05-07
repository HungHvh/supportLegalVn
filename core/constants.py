import os

SAFE_EMBEDDING_MODEL_NAME = "bkai-foundation-models/vietnamese-bi-encoder"
SQLITE_PATH=os.getenv("SQLITE_DB_PATH", "sqlite_data/legal_poc.db")