import pytest
from core.parser import VietnameseLegalParser, LegalLevel

def test_vietnamese_legal_parser_basic():
    parser = VietnameseLegalParser()
    sample = """
Điều 1. Phạm vi điều chỉnh
1. Luật này quy định về...
2. Các trường hợp khác:
a) Cá nhân.
b) Tổ chức.
Điều 2. Đối tượng áp dụng
Công dân Việt Nam.
"""
    doc = parser.parse_document(sample, "Luật Kiểm thử")
    
    # Check roots
    assert doc.title == "Luật Kiểm thử"
    assert len(doc.children) >= 2 # Điều 1, Điều 2
    
    # Check Điều 1
    dieu_1 = next(n for n in doc.children if "Điều 1" in n.title)
    assert len(dieu_1.children) >= 2 # Khoản 1, Khoản 2
    
    # Check Khoản 2 children
    khoan_2 = next(n for n in dieu_1.children if "2." in n.title)
    # Filter out PREAMBLE nodes for specific content checks if needed
    points = [c for c in khoan_2.children if c.title != "PREAMBLE"]
    assert len(points) >= 2 # Điểm a, Điểm b
    assert "a)" in points[0].title
    
    # Check Full Path
    assert "Luật Kiểm thử > Điều 1. > 2. > a)" in points[0].full_path

def test_preamble_handling():
    parser = VietnameseLegalParser()
    sample = """
Lời nói đầu: Luật này rất quan trọng.
Điều 1. ABC
"""
    doc = parser.parse_document(sample, "Luật A")
    # PREAMBLE should be the first child of the first split level that matches
    # Since it's before any "Phần", "Chương", "Mục", "Điều"
    # It will be caught by the first level that tries to split.
    
    # Find the node that contains "Lời nói đầu"
    found = False
    for child in doc.children:
        if "Lời nói đầu" in child.content:
            found = True
            break
    assert found

if __name__ == "__main__":
    pytest.main([__file__])
