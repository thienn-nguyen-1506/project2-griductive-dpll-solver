# Trạng thái phần GUI

Tài liệu này mô tả đúng phạm vi phần việc GUI. Dữ liệu hiện tại là dữ liệu mô
phỏng để có thể phát triển giao diện trước khi Game Engine, CNF encoder, DPLL và
Deductive Agent hoàn thành.

## GUI đã có

- Bảng động 3x3, 4x4 và 5x5, đúng quy ước cột A, B, C... và hàng 1, 2, 3...
- Card có tên, nghề nghiệp và ba cách trình bày: `UNSOLVED`, `CRIMINAL`,
  `INNOCENT`.
- Card chưa mở không nhận lời giải ẩn hoặc nội dung clue ẩn.
- Chọn card, submit Criminal/Innocent và hiển thị rõ `ACCEPTED`,
  `NOT_PROVABLE`, `CONTRADICTED`, `UNKNOWN`, `INCONSISTENT`, `SOLVED`.
- Khi mở card, clue mới xuất hiện và các ô thuộc region được highlight.
- Trình duyệt các clue đã mở.
- Hint, chạy một deduction step, Auto Solve từng bước và nút Stop.
- Progress, trạng thái ván chơi, solver metrics và deduction trace có cấu trúc.
- Load JSON, Restart, Light/Dark/System theme và phím tắt.
- Mock Engine có thể chạy hết một ván để kiểm tra GUI mà không giả vờ là thuật
  toán suy luận thật.

## Chưa có vì thuộc phần việc của thành viên khác

- Đọc định dạng puzzle chính thức của nhóm.
- Chuyển sáu clue template và extension thành CNF.
- SAT solver/DPLL thật.
- Kiểm tra entailment bằng hai SAT query.
- Thuật toán chọn character forced theo row-major order.
- Sinh metrics thật từ solver.

Khi các phần trên hoàn thành, chỉ cần viết một adapter theo `GameGateway`. Không
cần sửa layout hoặc các widget trong `gui/app.py`.

## Chạy thử

```bash
source .venv/bin/activate
python main.py
```

Trong GUI, chọn **Load JSON** rồi mở một trong ba file ở thư mục `puzzles/` để
kiểm tra các kích thước bảng. Đây chỉ là schema tối giản dành cho Mock Engine.
