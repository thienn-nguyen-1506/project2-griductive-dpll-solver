# Griductive GUI

GUI hoàn chỉnh và sẵn sàng tích hợp cho Project 2 môn Introduction to AI. Phần
hiện tại dùng Mock Engine để nhóm có thể thiết kế, demo và kiểm thử giao diện
trước khi Game Engine, CNF encoder, DPLL và Deductive Agent hoàn thành.

## Cài đặt và chạy trên MacOS

```bash
python3 -m venv .venv
source .venv/bin/activate
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
pip install -r requirements.txt
```  

## Chạy trên Windows  

```bash
.\venv\Scripts\Activate.ps1
python main.py
```  

## Thử các chức năng

- Chọn một card chưa giải rồi submit Criminal hoặc Innocent.
- Dùng Hint để highlight clue và target liên quan.
- Dùng Next Step để xem một vòng deduction.
- Dùng Auto Solve để chạy liên tục; nút này đổi thành Stop trong lúc chạy.
- Chọn clue đã mở để highlight toàn bộ region.
- Load các file `puzzles/gui_demo_3x3.json`, `gui_demo_4x4.json` và
  `gui_demo_5x5.json` để kiểm tra layout động.

Mock Engine cố ý trả đủ các trạng thái giao diện, nhưng không phải thuật toán
suy luận của bài nộp.

## Cấu trúc

- `gui/app.py`: layout, widget và tương tác.
- `gui/theme.py`: toàn bộ màu sắc dùng cho Light/Dark mode.
- `gui/models.py`: hợp đồng dữ liệu công khai giữa GUI và thuật toán.
- `gui/mock_engine.py`: dữ liệu mô phỏng chỉ dùng để phát triển GUI.
- `puzzles/`: JSON tối giản để kiểm tra nhiều kích thước bảng.
- `tests/`: kiểm tra hợp đồng public-state và hành vi Mock Gateway.
- `GUI_STATUS.md`: những phần GUI đã/chưa có.
- `GUI_INTEGRATION.md`: hướng dẫn cho các thành viên nối Engine/Agent vào GUI.

## Kiểm thử

```bash
python3 -m unittest discover -s tests -v
```

Điểm quan trọng nhất: GUI chỉ nói chuyện với `GameGateway`. Khi thuật toán thật
sẵn sàng, thay `MockGameGateway` bằng adapter thật; không cần viết lại GUI.
