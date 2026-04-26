import re

def test_legal_regex(text):
    patterns = {
        "Phần": r'^Phần\s+.*?\.',
        "Chương": r'^Chương\s+.*?\.',
        "Mục": r'^Mục\s+.*?\.',
        "Điều": r'^Điều\s+\d+.*?\.',
        "Khoản": r'^\d+\.',
        "Điểm": r'^[a-z]\)'
    }
    
    results = {}
    for name, pattern in patterns.items():
        matches = re.findall(pattern, text, re.MULTILINE | re.IGNORECASE)
        results[name] = matches
        
    return results

sample_text = """
PHẦN THỨ NHẤT. QUY ĐỊNH CHUNG
Chương I. ĐIỀU KHOẢN THI HÀNH
Mục 1. Phạm vi điều chỉnh
Điều 1. Đối tượng áp dụng
1. Các cơ quan nhà nước, tổ chức chính trị.
2. Công dân Việt Nam ở nước ngoài.
a) Trường hợp có hộ chiếu.
b) Trường hợp không có hộ chiếu.
Điều 2. Giải thích từ ngữ
Trong Luật này, các từ ngữ dưới đây được hiểu như sau:
1. "Luật" là văn bản quy phạm pháp luật.
2. "Nghị định" là văn bản do Chính phủ ban hành.
"""

results = test_legal_regex(sample_text)
with open("c:/Users/hvcng/PycharmProjects/supportLegalVn/scratch/regex_results.txt", "w", encoding="utf-8") as f:
    for category, matches in results.items():
        f.write(f"{category}: {matches}\n")
