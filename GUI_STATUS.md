# Trạng thái phần GUI

GUI hiện đã được nối với Game Engine, CNF encoder, DPLL và Deductive Agent thật
qua `gui/real_gateway.py`.

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
- Choose Level, Import Puzzle, Restart, Light/Dark theme và phím tắt.
- Real Gateway có thể tải và giải các puzzle chính thức bằng KB công khai.

## Tích hợp đã hoàn thành

- Đọc và kiểm tra schema puzzle chính thức.
- Mã hóa sáu core clue cùng `PARITY` và `COUNT_COMPARE`.
- Kiểm tra entailment bằng SAT, chọn forced character theo row-major.
- Manual verdict, Hint, Auto Solve, Restart và Load đều dùng logic thật.
- Metrics và deduction trace được lấy từ DPLL/Agent.
- Card úp không đưa hidden status hoặc clue vào `GameView`.

## Chạy thử

```bash
source .venv/bin/activate
python main.py
```

Trong GUI, chọn **Choose Level** để mở một trong bảy màn tích hợp sẵn. Chọn
**Import Puzzle** khi cần nạp một file `level_*.json` bên ngoài. Các file
`gui_demo_*.json` là dữ liệu Mock cũ và không được Real Gateway chấp nhận.
