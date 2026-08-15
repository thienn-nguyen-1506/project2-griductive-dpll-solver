# Tích hợp thuật toán vào GUI

## Ranh giới giữa các phần

GUI chỉ gọi interface `GameGateway` trong `gui/models.py`:

```text
GUI -> Gateway adapter -> Game Engine -> CNF encoder / DPLL / Deductive Agent
GUI <- public view   <- public state <- kết quả suy luận
```

`gui/app.py` không được đọc trực tiếp biến CNF, model SAT hay đáp án bí mật.
Adapter là nơi chuyển object của Game Engine sang các dataclass công khai mà GUI
hiểu được.

## Các hàm adapter phải cài

| Hàm | GUI cần gì từ hàm này |
| --- | --- |
| `get_public_state()` | Snapshot công khai để vẽ toàn bộ màn hình. |
| `submit_verdict(cell_id, status)` | Kiểm tra verdict bằng KB; chỉ reveal khi entailed. |
| `get_hint()` | Clue/ô nên highlight, không tiết lộ status bí mật. |
| `auto_solve_step()` | Thực hiện đúng một vòng deduction. |
| `restart()` | Trở về tập clue công khai ban đầu. |
| `load_puzzle(path)` | Đọc định dạng puzzle chính thức của nhóm. |

## Quy tắc dữ liệu quan trọng

Với card chưa giải, adapter phải trả:

```python
CellView(
    cell_id="B2",
    name="Bea",
    profession="Cook",
    revealed=False,
    status=Status.UNKNOWN,
    clue_id=None,
    clue_text=None,
    clue_references=(),
)
```

GUI sẽ hiển thị card này là `UNSOLVED`. `Status.UNKNOWN` chỉ nói rằng dữ liệu
công khai chưa có status; nó không phải một verdict mà người chơi được submit.

Sau khi verdict được chứng minh, adapter mới trả `revealed=True`, status thật,
clue mới và region của clue. `clue_references` phải là danh sách cell ID đã được
chuẩn hóa như `("A1", "B1", "B2")`.

## Adapter đang sử dụng

`RealGameGateway` đã được cài trong `gui/real_gateway.py`. `main.py` khởi động
luồng thật bằng:

```python
from gui.app import run_app
from gui.real_gateway import RealGameGateway

run_app(gateway=RealGameGateway())
```

Gateway kiểm tra puzzle trước khi thay engine. Nếu file không hợp lệ, nó trả
`ERROR` và giữ nguyên ván đang chơi.

## Ánh xạ kết quả suy luận

| Kết quả logic | `ActionCode` | GUI làm gì |
| --- | --- | --- |
| Verdict được KB entail | `ACCEPTED` | Mở card, thêm clue, cập nhật trace. |
| Cả bảng vừa được giải xong | `SOLVED` | Như ACCEPTED và khóa điều khiển. |
| Cả hai status đều chưa forced | `NOT_PROVABLE` | Giữ nguyên game state. |
| Status đối diện được forced | `CONTRADICTED` | Giữ nguyên game state. |
| Deduction loop không tìm được bước tiếp | `UNKNOWN` | Dừng Auto Solve, phase `STUCK`. |
| KB không nhất quán | `INCONSISTENT` | Dừng Auto Solve, phase `INCONSISTENT`. |
| Lỗi file hoặc adapter | `ERROR` | Hiển thị lỗi, không làm GUI crash. |

`TraceEntry` và `SolverMetrics` là dữ liệu tùy chọn nhưng nên được Agent/DPLL
cập nhật để demo và báo cáo có thể cho thấy hệ thống đã suy luận thế nào.
