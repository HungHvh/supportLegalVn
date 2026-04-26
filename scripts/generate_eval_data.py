import os
import sqlite3
import json
import logging
import time
from typing import List, Dict
from dotenv import load_dotenv
import google.generativeai as genai

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment
load_dotenv()

# Config
DB_PATH = os.getenv("SQLITE_DB_PATH", "legal_poc.db")
OUTPUT_PATH = ".planning/phases/06-retrieval-evaluation/golden_set_synthetic.json"
MODEL_NAME = "gemini-2.0-flash"
TARGET_DOCS_COUNT = 10 

# Configure Gemini
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel(MODEL_NAME)

PROMPT_TEMPLATE = """
Bạn là một chuyên gia pháp luật Việt Nam. Dựa trên nội dung văn bản pháp luật dưới đây, hãy tạo ra {num_questions} bộ câu hỏi đánh giá (Evaluation Triplets).
Mỗi bộ câu hỏi bao gồm:
1. Query: Một câu hỏi thực tế mà người dùng có thể hỏi (ví dụ: "Thủ tục thành lập công ty TNHH 1 thành viên là gì?").
2. Reference Context: Đoạn trích chính xác từ văn bản dùng để trả lời câu hỏi.
3. Reference Answer: Câu trả lời ngắn gọn, chính xác dựa trên đoạn trích đó.

Yêu cầu:
- Câu hỏi phải mang tính thực tế và chuyên sâu.
- Câu trả lời phải khách quan, dựa trên văn bản.
- Trả về kết quả dưới dạng JSON list: [{{"query": "...", "reference_context": "...", "reference_answer": "..."}}]

Văn bản:
{content}
"""

def fetch_legal_documents(limit: int = 10) -> List[Dict]:
    """Fetches documents from the database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    query = "SELECT DISTINCT so_ky_hieu, full_path, content FROM legal_documents LIMIT ?"
    cursor.execute(query, (limit,))
    rows = cursor.fetchall()
    conn.close()
    
    return [{"so_ky_hieu": r[0], "full_path": r[1], "content": r[2]} for r in rows]

def generate_triplets(content: str, num_questions: int = 3) -> List[Dict]:
    """Generates triplets for a single document content with retry logic."""
    prompt = PROMPT_TEMPLATE.format(num_questions=num_questions, content=content[:8000])
    
    max_retries = 3
    retry_delay = 10
    
    for attempt in range(max_retries):
        try:
            response = model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    response_mime_type="application/json",
                )
            )
            data = json.loads(response.text)
            return data if isinstance(data, list) else []
        except Exception as e:
            if "429" in str(e):
                logger.warning(f"Rate limit hit. Retrying in {retry_delay}s (Attempt {attempt+1}/{max_retries})")
                time.sleep(retry_delay)
                retry_delay *= 2
            else:
                logger.error(f"Error generating content: {e}")
                break
    return []

def main():
    docs = fetch_legal_documents(limit=TARGET_DOCS_COUNT)
    if not docs:
        logger.error("No documents found in database.")
        return

    all_triplets = []
    logger.info(f"Generating synthetic data for {len(docs)} documents...")
    
    for i, doc in enumerate(docs):
        logger.info(f"Processing doc {i+1}/{len(docs)}: {doc['so_ky_hieu']}")
        triplets = generate_triplets(doc['content'])
        for t in triplets:
            t['metadata'] = {
                "so_ky_hieu": doc['so_ky_hieu'],
                "full_path": doc['full_path']
            }
        all_triplets.extend(triplets)
        time.sleep(3) # Increased sleep between documents

    # Save to file
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(all_triplets, f, ensure_ascii=False, indent=2)
    
    logger.info(f"Successfully generated {len(all_triplets)} triplets and saved to {OUTPUT_PATH}")

if __name__ == "__main__":
    main()
