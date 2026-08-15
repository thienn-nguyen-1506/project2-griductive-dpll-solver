"""
core/encoder.py
Mã hóa các manh mối (Clues) và trạng thái ô thành mệnh đề CNF (SAT)
và cung cấp Bộ đánh giá ngữ nghĩa trực tiếp (Direct Semantic Evaluator).
"""

import itertools
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


# ============================================================
# 1. KnowledgeBaseSnapshot Dataclass
# ============================================================

@dataclass
class KnowledgeBaseSnapshot:
    """Đóng gói toàn bộ trạng thái Cơ sở tri thức (KB) tại một bước suy luận."""

    clauses: List[List[int]]
    primary_vars: Dict[str, int]
    unresolved_cell_ids: List[str]
    cell_to_var: Dict[str, int]
    active_clue_ids: List[str]
    known_statuses: Dict[str, str]
    aux_var_count: int = 0

    @property
    def clause_count(self) -> int:
        """Tổng số mệnh đề CNF hiện có trong snapshot."""
        return len(self.clauses)


# ============================================================
# 2. Region Helper
# ============================================================

class RegionHelper:
    """Các hàm hỗ trợ xử lý tọa độ và vùng trên bàn cờ."""

    @staticmethod
    def get_row(grid_size: int, row: int) -> List[str]:
        """Trả về tất cả cell trong một row (row 1-indexed)."""
        return [f"{chr(ord('A') + col)}{row}" for col in range(grid_size)]

    @staticmethod
    def get_column(grid_size: int, col_letter: str) -> List[str]:
        """Trả về tất cả cell trong một column."""
        return [f"{col_letter.upper()}{row}" for row in range(1, grid_size + 1)]

    @staticmethod
    def get_neighbors(
        grid_size: int, cell_id: str, include_diagonals: bool = True
    ) -> List[str]:
        """Trả về các ô lân cận của cell."""
        col = ord(cell_id[0].upper()) - ord("A")
        row = int(cell_id[1:]) - 1

        neighbors = []
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr == 0 and dc == 0:
                    continue
                if not include_diagonals and abs(dr) + abs(dc) > 1:
                    continue
                new_row = row + dr
                new_col = col + dc
                if 0 <= new_row < grid_size and 0 <= new_col < grid_size:
                    neighbors.append(f"{chr(ord('A') + new_col)}{new_row + 1}")
        return neighbors


# ============================================================
# 3. Clue Data Model
# ============================================================

@dataclass
class Clue:
    """Đại diện cho một manh mối trong game."""

    id: str = ""
    type: str = ""
    target_cells: List[str] = field(default_factory=list)
    value: Optional[Any] = None
    target_status: str = "CRIMINAL"  # "CRIMINAL" hoặc "INNOCENT"
    text: str = ""

    # Fields used by the COUNT_COMPARE extension.
    left_cells: List[str] = field(default_factory=list)
    right_cells: List[str] = field(default_factory=list)
    operator: str = ""

    # Field tương thích với cấu trúc cũ
    clue_type: Optional[str] = None
    region: Optional[List[str]] = None
    k: Optional[int] = None
    char_a: Optional[str] = None
    char_b: Optional[str] = None
    is_criminal: Optional[bool] = None

    def __post_init__(self) -> None:
        """Chuẩn hóa dữ liệu đầu vào và tự động tạo ID nếu chưa có."""
        if not self.type and self.clue_type:
            self.type = self.clue_type
        if not self.clue_type and self.type:
            self.clue_type = self.type

        if not self.target_cells and self.region:
            self.target_cells = list(self.region)
        if not self.region and self.target_cells:
            self.region = list(self.target_cells)

        if self.value is None and self.k is not None:
            self.value = self.k
        if self.k is None and self.value is not None:
            self.k = self.value

        # Sửa lỗi: Hỗ trợ trường hợp chỉ truyền char_a
        if not self.target_cells and self.char_a:
            self.target_cells = [self.char_a]
            if self.char_b:
                self.target_cells.append(self.char_b)

        if not self.id:
            cells_str = (
                "_".join(self.target_cells) if self.target_cells else "global"
            )
            self.id = f"clue_{self.type}_{cells_str}"


# ============================================================
# 4. Direct Semantic Evaluator
# ============================================================

class ClueEvaluator:
    """Bộ đánh giá trực tiếp giá trị chân lý của Clue không qua mã hóa CNF."""

    @staticmethod
    def evaluate(clue: Clue, assignment: Dict[str, str]) -> bool:
        targets = clue.target_cells
        ctype = (clue.type or clue.clue_type or "").upper()
        target_st = getattr(clue, "target_status", "CRIMINAL")

        if ctype == "FACT":
            expected = clue.value
            if expected is None:
                expected = (
                    "CRIMINAL" if clue.is_criminal is not False else "INNOCENT"
                )
            return all(assignment.get(cid) == expected for cid in targets)

        # Lọc trạng thái đã gán (bỏ qua các ô chưa gán / None)
        assigned_statuses = [
            assignment[cid]
            for cid in targets
            if cid in assignment and assignment[cid] is not None
        ]

        if ctype == "SAME":
            return len(set(assigned_statuses)) <= 1

        elif ctype == "DIFFERENT":
            return len(assigned_statuses) == len(set(assigned_statuses))

        elif ctype == "IMPLIES":
            if len(targets) < 2:
                return True
            cond = assignment.get(targets[0]) == "CRIMINAL"
            then = assignment.get(targets[1]) == "CRIMINAL"
            return (not cond) or then

        elif ctype in ("EXACTLY", "EXACT_COUNT"):
            k = int(clue.value) if clue.value is not None else 1
            count = sum(
                1 for cid in targets if assignment.get(cid) == target_st
            )
            return count == k

        elif ctype == "AT_LEAST":
            k = int(clue.value) if clue.value is not None else 1
            count = sum(
                1 for cid in targets if assignment.get(cid) == target_st
            )
            return count >= k

        elif ctype == "AT_MOST":
            k = int(clue.value) if clue.value is not None else 1
            count = sum(
                1 for cid in targets if assignment.get(cid) == target_st
            )
            return count <= k

        elif ctype == "PARITY":
            parity = str(clue.value or "").upper()
            count = sum(
                1 for cid in targets if assignment.get(cid) == target_st
            )
            if parity == "ODD":
                return count % 2 == 1
            if parity == "EVEN":
                return count % 2 == 0
            raise ValueError("PARITY clue value must be ODD or EVEN.")

        elif ctype == "COUNT_COMPARE":
            left_count = sum(
                1 for cid in clue.left_cells if assignment.get(cid) == target_st
            )
            right_count = sum(
                1 for cid in clue.right_cells if assignment.get(cid) == target_st
            )
            operator = clue.operator.upper()
            comparisons = {
                "GT": left_count > right_count,
                "LT": left_count < right_count,
                "EQ": left_count == right_count,
                "GE": left_count >= right_count,
                "LE": left_count <= right_count,
            }
            if operator not in comparisons:
                raise ValueError(
                    "COUNT_COMPARE operator must be GT, LT, EQ, GE, or LE."
                )
            return comparisons[operator]

        raise ValueError(f"Unsupported clue type: {ctype or '<empty>'}")


# ============================================================
# 5. CNF Encoder
# ============================================================

class CNFEncoder:
    """Chuyển đổi các manh mối puzzle thành công thức CNF."""

    def __init__(self, character_ids: Optional[List[str]] = None) -> None:
        self.cell_to_var: Dict[str, int] = {}
        self.var_to_cell: Dict[int, str] = {}
        self._next_var = 1
        self.aux_var_count = 0

        if character_ids:
            for cell_id in sorted(character_ids):
                self._get_or_create_cell_var(cell_id)

        self.var_map = self.cell_to_var
        self.rev_map = self.var_to_cell

    def _get_or_create_cell_var(self, cell_id: str) -> int:
        if cell_id not in self.cell_to_var:
            variable = self._next_var
            self.cell_to_var[cell_id] = variable
            self.var_to_cell[variable] = cell_id
            self._next_var += 1
        return self.cell_to_var[cell_id]

    def encode_known_statuses(
        self, known_statuses: Dict[str, str]
    ) -> List[List[int]]:
        clauses: List[List[int]] = []
        for cell_id, status in known_statuses.items():
            var = self._get_or_create_cell_var(cell_id)
            if status in ("CRIMINAL", True, 1):
                clauses.append([var])
            elif status in ("INNOCENT", False, 0):
                clauses.append([-var])
        return clauses

    def encode_clue(self, clue: Clue) -> List[List[int]]:
        clue_type = (clue.type or clue.clue_type or "").upper()
        cells = clue.target_cells or clue.region or []

        if clue_type == "FACT":
            clauses: List[List[int]] = []
            target_status = clue.value
            if target_status is None:
                target_status = (
                    "INNOCENT" if clue.is_criminal is False else "CRIMINAL"
                )

            targets = cells if cells else ([clue.char_a] if clue.char_a else [])
            for target in targets:
                var = self._get_or_create_cell_var(target)
                if target_status in ("CRIMINAL", True, 1):
                    clauses.append([var])
                else:
                    clauses.append([-var])
            return clauses

        # Chuyển đổi danh sách ô thành danh sách literal (dương nếu CRIMINAL, âm nếu INNOCENT)
        vars_ = [self._get_or_create_cell_var(cell) for cell in cells]
        target_st = getattr(clue, "target_status", "CRIMINAL")
        lits = [-v for v in vars_] if target_st == "INNOCENT" else vars_

        if clue_type == "SAME":
            clauses = []
            for i in range(len(vars_) - 1):
                a, b = vars_[i], vars_[i + 1]
                clauses.append([-a, b])
                clauses.append([a, -b])
            return clauses

        if clue_type == "DIFFERENT":
            clauses = []
            for i in range(len(vars_)):
                for j in range(i + 1, len(vars_)):
                    a, b = vars_[i], vars_[j]
                    clauses.append([a, b])
                    clauses.append([-a, -b])
            return clauses

        if clue_type == "IMPLIES":
            if len(vars_) < 2:
                return []
            a, b = vars_[0], vars_[1]
            return [[-a, b]]

        if clue_type == "PARITY":
            parity = str(clue.value or "").upper()
            if parity not in ("ODD", "EVEN"):
                raise ValueError("PARITY clue value must be ODD or EVEN.")

            def parity_holds(values: Dict[str, bool]) -> bool:
                count = sum(
                    values[cell] if target_st == "CRIMINAL" else not values[cell]
                    for cell in cells
                )
                return count % 2 == (1 if parity == "ODD" else 0)

            return self._encode_truth_table(cells, parity_holds)

        if clue_type == "COUNT_COMPARE":
            operator = clue.operator.upper()
            if operator not in ("GT", "LT", "EQ", "GE", "LE"):
                raise ValueError(
                    "COUNT_COMPARE operator must be GT, LT, EQ, GE, or LE."
                )
            involved_cells = list(
                dict.fromkeys(clue.left_cells + clue.right_cells)
            )

            def comparison_holds(values: Dict[str, bool]) -> bool:
                def is_target(cell: str) -> bool:
                    value = values[cell]
                    return value if target_st == "CRIMINAL" else not value

                left_count = sum(is_target(cell) for cell in clue.left_cells)
                right_count = sum(is_target(cell) for cell in clue.right_cells)
                return {
                    "GT": left_count > right_count,
                    "LT": left_count < right_count,
                    "EQ": left_count == right_count,
                    "GE": left_count >= right_count,
                    "LE": left_count <= right_count,
                }[operator]

            return self._encode_truth_table(involved_cells, comparison_holds)

        k = (
            clue.value
            if clue.value is not None
            else (clue.k if clue.k is not None else 0)
        )
        k = int(k)

        if clue_type in ("EXACTLY", "EXACT_COUNT"):
            return self._encode_at_least(lits, k) + self._encode_at_most(
                lits, k
            )

        if clue_type == "AT_LEAST":
            return self._encode_at_least(lits, k)

        if clue_type == "AT_MOST":
            return self._encode_at_most(lits, k)

        return []

    def _encode_truth_table(
        self,
        cell_ids: List[str],
        predicate: Callable[[Dict[str, bool]], bool],
    ) -> List[List[int]]:
        """Encode a small Boolean constraint by blocking every false row.

        Project regions are intentionally small, so this direct combinatorial
        encoding is suitable for the two extensions and keeps the generated
        clauses easy to explain in the report.
        """
        unique_cells = list(dict.fromkeys(cell_ids))
        if not unique_cells:
            raise ValueError("Extension clue regions must not be empty.")

        variables = {
            cell: self._get_or_create_cell_var(cell) for cell in unique_cells
        }
        clauses: List[List[int]] = []
        for bits in itertools.product((False, True), repeat=len(unique_cells)):
            values = dict(zip(unique_cells, bits))
            if predicate(values):
                continue
            clauses.append([
                -variables[cell] if values[cell] else variables[cell]
                for cell in unique_cells
            ])
        return clauses

    def _encode_at_most(self, lits: List[int], k: int) -> List[List[int]]:
        n = len(lits)
        if k >= n:
            return []
        if k < 0:
            return [[]]  # UNSAT
        clauses: List[List[int]] = []
        for combination in itertools.combinations(lits, k + 1):
            clauses.append([-var for var in combination])
        return clauses

    def _encode_at_least(self, lits: List[int], k: int) -> List[List[int]]:
        n = len(lits)
        if k <= 0:
            return []
        if k > n:
            return [[]]  # UNSAT
        clauses: List[List[int]] = []
        for combination in itertools.combinations(lits, n - k + 1):
            clauses.append(list(combination))
        return clauses

    def build_snapshot(
        self,
        all_cell_ids: List[str],
        clues: List[Clue],
        active_clue_ids: List[str],
        known_statuses: Dict[str, str],
    ) -> KnowledgeBaseSnapshot:
        clauses: List[List[int]] = []
        clauses.extend(self.encode_known_statuses(known_statuses))

        clue_map = {clue.id: clue for clue in clues if clue.id}
        for clue_id in active_clue_ids:
            clue = clue_map.get(clue_id)
            if clue is not None:
                clauses.extend(self.encode_clue(clue))
            else:
                for candidate in clues:
                    if candidate.id == clue_id or candidate.type == clue_id:
                        clauses.extend(self.encode_clue(candidate))

        primary_vars = {
            f"C_{cell_id}": self._get_or_create_cell_var(cell_id)
            for cell_id in all_cell_ids
        }
        unresolved = [c for c in all_cell_ids if c not in known_statuses]

        return KnowledgeBaseSnapshot(
            clauses=clauses,
            primary_vars=primary_vars,
            unresolved_cell_ids=unresolved,
            cell_to_var=self.cell_to_var.copy(),
            active_clue_ids=list(active_clue_ids),
            known_statuses=known_statuses.copy(),
            aux_var_count=self.aux_var_count,
        )
