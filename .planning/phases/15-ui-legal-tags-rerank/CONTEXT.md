# Phase 15: Cải thiện UI chuẩn ngành luật với Tag phân loại và Rerank

## Goal
Để UI hiển thị hợp lý và "chuẩn ngành luật" hơn, cần cải thiện giao diện và trải nghiệm người dùng với các điểm nhấn sau:

1. Phân loại bằng Tag/Badge màu sắc (Visual Hierarchy)
- Màu Đỏ/Cam (Cấp cao nhất): [QH] Luật, Bộ luật, Nghị quyết Quốc hội.
- Màu Xanh dương (Cấp trung ương hướng dẫn): [NĐ-CP], [TT] Nghị định, Thông tư.
- Màu Xám/Xanh lá (Cấp địa phương): [QĐ-UBND] Quyết định của Tỉnh/Thành phố.
- Giao diện tham khảo: Ngay dưới tên văn bản (ví dụ: 19/2003/QH11 - Điều 328), thêm một badge nhỏ ghi rõ "Luật" hoặc "Văn bản hướng dẫn".

2. Sắp xếp lại thứ tự (Sorting/Reranking)
- Thực hiện ở backend hoặc frontend.
- Ưu tiên tuyệt đối: Các mã có đuôi QH phải luôn được đẩy lên top đầu của danh sách tham khảo để làm kim chỉ nam.
- Tiếp theo: Các văn bản hướng dẫn (CP, TT).
- Cuối cùng: Các văn bản địa phương (UBND). Trừ khi câu hỏi của người dùng có chứa đích danh tên tỉnh thành (ví dụ: "Ở Hà Nội thì khiếu nại thế nào?").

## Depends on
- Phase 13
- Phase 14

## Plans
- Chưa lên kế hoạch
