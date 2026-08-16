# Griductive Solver

Phiên bản có thể chơi của Project 2 môn Introduction to AI. GUI hiện được nối
với Game Engine, CNF encoder, DPLL và Deductive Agent thật qua
`RealGameGateway`; hidden solution và clue chưa mở không đi vào public state.

## Cài đặt và chạy trên MacOS

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
python3 main.py
```

Python được chọn phải có Tkinter. Kiểm tra bằng:

```bash
python3 -c "import tkinter; print(tkinter.TkVersion)"
```  

## Cài đặt trên Windows  

```bash
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```  

## Chạy trên Windows  

```bash
.\venv\Scripts\Activate.ps1
python main.py
```  

## Thư viện cần thiết

Các thư viện của project được khai báo trong `requirements.txt`:

- `customtkinter`: xây dựng giao diện desktop.
- `Pillow`: cung cấp module `PIL` để tải và xử lý ảnh trong GUI.

Không cài package có tên `PIL`. Trong Python ta import bằng `from PIL import ...`,
nhưng tên package cần cài là `Pillow`.

Nếu gặp lỗi `ModuleNotFoundError: No module named 'PIL'`, hãy chắc chắn virtual
environment đã được kích hoạt, sau đó chạy lại:

```bash
python3 -m pip install -r requirements.txt
```

Trên Windows, dùng lệnh tương đương:

```bash
python -m pip install -r requirements.txt
```

## Thử các chức năng

- Chọn một card chưa giải rồi submit Criminal hoặc Innocent.
- Dùng Hint để highlight clue và target liên quan.
- Dùng Next Step để xem một vòng deduction.
- Dùng Auto Solve để chạy liên tục; nút này đổi thành Stop trong lúc chạy.
- Chọn clue đã mở để highlight toàn bộ region.
- Dùng **Choose Level** để chọn màn tích hợp sẵn, hoặc **Import Puzzle** để nạp
  một file `level_*.json` bên ngoài.
- Chạy `python validate_puzzles.py` để kiểm tra clue truth, uniqueness và toàn
  bộ deduction loop của các màn.

## Cấu trúc

- `gui/app.py`: layout, widget và tương tác.
- `gui/theme.py`: toàn bộ màu sắc dùng cho Light/Dark mode.
- `gui/models.py`: hợp đồng dữ liệu công khai giữa GUI và thuật toán.
- `gui/real_gateway.py`: adapter nối GUI với Game Engine và Logic Agent thật.
- `gui/mock_engine.py`: dữ liệu mô phỏng chỉ còn dùng cho unit test GUI.
- `core/puzzle.py`: loader và validator của puzzle chính thức.
- `puzzles/level_*.json`: tám puzzle logic đã được kiểm chứng.
- `tests/`: kiểm tra encoder, DPLL, agent, puzzle và tích hợp gateway.
- `GUI_STATUS.md`: những phần GUI đã/chưa có.
- `GUI_INTEGRATION.md`: hướng dẫn cho các thành viên nối Engine/Agent vào GUI.

## Kiểm thử

```bash
python3 -m unittest discover -s tests -v
```

Điểm quan trọng nhất: GUI chỉ nói chuyện với `GameGateway`. `main.py` truyền
`RealGameGateway`, còn Mock Gateway không được dùng trong luồng chạy bài nộp.
