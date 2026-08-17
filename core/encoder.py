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

    VALID_KINDS = {"ROW", "COLUMN", "NEIGHBORS", "EXPLICIT"}

    @staticmethod
    def _validate_grid_size(grid_size: int) -> None:
        if isinstance(grid_size, bool) or not isinstance(grid_size, int):
            raise ValueError("grid_size must be a positive integer.")
        if grid_size <= 0:
            raise ValueError("grid_size must be a positive integer.")

    @staticmethod
    def get_row(grid_size: int, row: int) -> List[str]:
        """Trả về tất cả cell trong một row (row 1-indexed)."""
        RegionHelper._validate_grid_size(grid_size)
        if isinstance(row, bool) or not isinstance(row, int) or not 1 <= row <= grid_size:
            raise ValueError(f"row must be between 1 and {grid_size}.")
        return [f"{chr(ord('A') + col)}{row}" for col in range(grid_size)]

    @staticmethod
    def get_column(grid_size: int, col_letter: str) -> List[str]:
        """Trả về tất cả cell trong một column."""
        RegionHelper._validate_grid_size(grid_size)
        if not isinstance(col_letter, str) or len(col_letter.strip()) != 1:
            raise ValueError("column must be one letter.")
        column = col_letter.strip().upper()
        column_index = ord(column) - ord("A")
        if not 0 <= column_index < grid_size:
            raise ValueError(
                f"column must be between A and {chr(ord('A') + grid_size - 1)}."
            )
        return [f"{column}{row}" for row in range(1, grid_size + 1)]

    @staticmethod
    def get_neighbors(
        grid_size: int, cell_id: str, include_diagonals: bool = True
    ) -> List[str]:
        """Trả về các ô lân cận của cell."""
        RegionHelper._validate_grid_size(grid_size)
        if not isinstance(cell_id, str) or len(cell_id) < 2:
            raise ValueError("neighbor center must be a valid cell ID.")
        try:
            col = ord(cell_id[0].upper()) - ord("A")
            row = int(cell_id[1:]) - 1
        except (TypeError, ValueError):
            raise ValueError("neighbor center must be a valid cell ID.") from None
        if not (0 <= row < grid_size and 0 <= col < grid_size):
            raise ValueError(f"neighbor center {cell_id} is outside the grid.")

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

    @staticmethod
    def resolve(grid_size: int, kind: str, value: Any) -> List[str]:
        """Resolve a structured region expression into explicit cell IDs."""
        normalised_kind = str(kind or "").upper()
        if normalised_kind not in RegionHelper.VALID_KINDS:
            raise ValueError(
                "region kind must be ROW, COLUMN, NEIGHBORS, or EXPLICIT."
            )
        if normalised_kind == "ROW":
            return RegionHelper.get_row(grid_size, value)
        if normalised_kind == "COLUMN":
            return RegionHelper.get_column(grid_size, value)
        if normalised_kind == "NEIGHBORS":
            return RegionHelper.get_neighbors(grid_size, value)
        if not isinstance(value, (list, tuple)):
            raise ValueError("EXPLICIT region value must be a list of cell IDs.")
        return list(value)


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

    # Optional structured region metadata. target_cells contains the resolved
    # cells so the semantic evaluator and GUI do not need to resolve it again.
    region_kind: Optional[str] = None
    region_value: Optional[Any] = None

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
        if self.region_kind:
            self.region_kind = str(self.region_kind).upper()
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

    SUPPORTED_CLUE_TYPES = {
        "FACT",
        "SAME",
        "DIFFERENT",
        "EXACTLY",
        "EXACT_COUNT",  # Legacy alias for EXACTLY.
        "AT_LEAST",
        "AT_MOST",
        "PARITY",
        "COUNT_COMPARE",
        "IMPLIES",  # Retained for backwards compatibility.
    }
    VALID_STATUSES = {"CRIMINAL", "INNOCENT"}
    VALID_COMPARE_OPERATORS = {"GT", "LT", "EQ", "GE", "LE"}

    def __init__(
        self,
        character_ids: Optional[List[str]] = None,
        *,
        grid_size: Optional[int] = None,
    ) -> None:
        self.cell_to_var: Dict[str, int] = {}
        self.var_to_cell: Dict[int, str] = {}
        self._next_var = 1
        self.aux_var_count = 0
        self._declared_cells: Optional[set[str]] = None
        if grid_size is not None:
            RegionHelper._validate_grid_size(grid_size)
        self.grid_size = grid_size

        if character_ids is not None:
            validated_ids = self._validate_cell_catalog(character_ids)
            self._declared_cells = set(validated_ids)
            if self.grid_size is None:
                self.grid_size = self._infer_grid_size(validated_ids)
            for cell_id in sorted(validated_ids):
                self._get_or_create_cell_var(cell_id)

        self.var_map = self.cell_to_var
        self.rev_map = self.var_to_cell

    @staticmethod
    def _validate_cell_id(cell_id: Any, label: str = "cell ID") -> str:
        if not isinstance(cell_id, str) or not cell_id.strip():
            raise ValueError(f"{label} must be a non-empty string.")
        if cell_id != cell_id.strip():
            raise ValueError(f"{label} must not contain surrounding whitespace.")
        return cell_id

    @classmethod
    def _validate_cell_catalog(cls, cell_ids: Any) -> List[str]:
        if not isinstance(cell_ids, (list, tuple)):
            raise ValueError("character_ids must be a list or tuple of cell IDs.")
        validated = [
            cls._validate_cell_id(cell_id, "character_ids entry")
            for cell_id in cell_ids
        ]
        if len(validated) != len(set(validated)):
            raise ValueError("character_ids must contain distinct cell IDs.")
        return validated

    @staticmethod
    def _infer_grid_size(cell_ids: List[str]) -> Optional[int]:
        size = int(len(cell_ids) ** 0.5)
        if size * size != len(cell_ids):
            return None
        expected = {
            f"{chr(ord('A') + column)}{row}"
            for row in range(1, size + 1)
            for column in range(size)
        }
        return size if set(cell_ids) == expected else None

    def _get_or_create_cell_var(self, cell_id: str) -> int:
        cell_id = self._validate_cell_id(cell_id)
        if (
            self._declared_cells is not None
            and cell_id not in self._declared_cells
        ):
            raise ValueError(f"Unknown cell referenced by encoder: {cell_id}.")
        if cell_id not in self.cell_to_var:
            variable = self._next_var
            self.cell_to_var[cell_id] = variable
            self.var_to_cell[variable] = cell_id
            self._next_var += 1
        return self.cell_to_var[cell_id]

    @classmethod
    def _normalise_status(cls, status: Any, label: str) -> str:
        # Bool/int support is retained only for the legacy public API.
        if status is True or (
            isinstance(status, int)
            and not isinstance(status, bool)
            and status == 1
        ):
            return "CRIMINAL"
        if status is False or (
            isinstance(status, int)
            and not isinstance(status, bool)
            and status == 0
        ):
            return "INNOCENT"
        if isinstance(status, str):
            normalised = status.upper()
            if normalised in cls.VALID_STATUSES:
                return normalised
        raise ValueError(
            f"{label} must be CRIMINAL or INNOCENT, got {status!r}."
        )

    def _validate_region(
        self,
        raw_cells: Any,
        *,
        label: str,
        allowed_cells: Optional[set[str]] = None,
    ) -> List[str]:
        if not isinstance(raw_cells, (list, tuple)):
            raise ValueError(f"{label} must be a list or tuple of cell IDs.")
        cells = [
            self._validate_cell_id(cell_id, f"{label} entry")
            for cell_id in raw_cells
        ]
        if not cells:
            raise ValueError(f"{label} must not be empty.")
        if len(cells) != len(set(cells)):
            raise ValueError(f"{label} must contain distinct cell IDs.")

        valid_cells = allowed_cells
        if valid_cells is None:
            valid_cells = self._declared_cells
        if valid_cells is not None:
            unknown = [cell for cell in cells if cell not in valid_cells]
            if unknown:
                raise ValueError(f"{label} references unknown cells: {unknown}.")
        return cells

    def _resolve_target_region(self, clue: Clue) -> Any:
        raw_cells = clue.target_cells or clue.region or []
        if not clue.region_kind:
            return raw_cells
        if self.grid_size is None:
            raise ValueError(
                f"{clue.id}.region requires a square grid size."
            )
        resolved = RegionHelper.resolve(
            self.grid_size,
            clue.region_kind,
            clue.region_value,
        )
        if clue.target_cells and list(clue.target_cells) != resolved:
            raise ValueError(
                f"{clue.id}.target_cells does not match its structured region."
            )
        return resolved

    def _validate_clue(
        self,
        clue: Clue,
        *,
        allowed_cells: Optional[set[str]] = None,
    ) -> tuple[str, List[str], str]:
        if not isinstance(clue, Clue):
            raise ValueError("encode_clue expects a Clue instance.")

        clue_type = str(clue.type or clue.clue_type or "").upper()
        clue_label = clue.id or "<unnamed clue>"
        if clue_type not in self.SUPPORTED_CLUE_TYPES:
            raise ValueError(
                f"{clue_label} uses unsupported clue type "
                f"{clue_type or '<empty>'}."
            )

        target_status = self._normalise_status(
            getattr(clue, "target_status", "CRIMINAL"),
            f"{clue_label}.target_status",
        )

        if clue_type == "COUNT_COMPARE":
            left_cells = self._validate_region(
                clue.left_cells,
                label=f"{clue_label}.left_cells",
                allowed_cells=allowed_cells,
            )
            right_cells = self._validate_region(
                clue.right_cells,
                label=f"{clue_label}.right_cells",
                allowed_cells=allowed_cells,
            )
            operator = str(clue.operator or "").upper()
            if operator not in self.VALID_COMPARE_OPERATORS:
                raise ValueError(
                    f"{clue_label}.operator must be GT, LT, EQ, GE, or LE."
                )
            involved = list(dict.fromkeys(left_cells + right_cells))
            return clue_type, involved, target_status

        raw_cells = self._resolve_target_region(clue)
        cells = self._validate_region(
            raw_cells,
            label=f"{clue_label}.target_cells",
            allowed_cells=allowed_cells,
        )

        exact_arity = {
            "FACT": 1,
            "SAME": 2,
            "DIFFERENT": 2,
            "IMPLIES": 2,
        }.get(clue_type)
        if exact_arity is not None and len(cells) != exact_arity:
            raise ValueError(
                f"{clue_label} {clue_type} must reference exactly "
                f"{exact_arity} cell(s)."
            )

        if clue_type == "FACT":
            fact_status = clue.value
            if fact_status is None:
                fact_status = (
                    "INNOCENT" if clue.is_criminal is False else "CRIMINAL"
                )
            self._normalise_status(fact_status, f"{clue_label}.value")

        if clue_type in {"EXACTLY", "EXACT_COUNT", "AT_LEAST", "AT_MOST"}:
            value = clue.value if clue.value is not None else clue.k
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"{clue_label}.value must be an integer.")
            if not 0 <= value <= len(cells):
                raise ValueError(
                    f"{clue_label}.value must satisfy "
                    "0 <= value <= region size."
                )

        if clue_type == "PARITY":
            parity = str(clue.value or "").upper()
            if parity not in {"ODD", "EVEN"}:
                raise ValueError(
                    f"{clue_label}.value must be ODD or EVEN for PARITY."
                )

        return clue_type, cells, target_status

    def encode_known_statuses(
        self, known_statuses: Dict[str, str]
    ) -> List[List[int]]:
        if not isinstance(known_statuses, dict):
            raise ValueError("known_statuses must be a dictionary.")
        clauses: List[List[int]] = []
        for cell_id, status in known_statuses.items():
            var = self._get_or_create_cell_var(cell_id)
            normalised = self._normalise_status(
                status, f"known status for {cell_id}"
            )
            if normalised == "CRIMINAL":
                clauses.append([var])
            else:
                clauses.append([-var])
        return clauses

    def encode_clue(self, clue: Clue) -> List[List[int]]:
        clue_type, cells, target_st = self._validate_clue(clue)

        if clue_type == "FACT":
            target_status = clue.value
            if target_status is None:
                target_status = (
                    "INNOCENT" if clue.is_criminal is False else "CRIMINAL"
                )
            target_status = self._normalise_status(
                target_status, f"{clue.id}.value"
            )
            var = self._get_or_create_cell_var(cells[0])
            return [[var if target_status == "CRIMINAL" else -var]]

        # Chuyển đổi danh sách ô thành danh sách literal (dương nếu CRIMINAL, âm nếu INNOCENT)
        vars_ = [self._get_or_create_cell_var(cell) for cell in cells]
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
            else clue.k
        )

        if clue_type in ("EXACTLY", "EXACT_COUNT"):
            return self._encode_at_least(lits, k) + self._encode_at_most(
                lits, k
            )

        if clue_type == "AT_LEAST":
            return self._encode_at_least(lits, k)

        if clue_type == "AT_MOST":
            return self._encode_at_most(lits, k)

        raise AssertionError(f"Validated clue type was not encoded: {clue_type}")

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
        validated_cell_ids = self._validate_cell_catalog(all_cell_ids)
        valid_cell_set = set(validated_cell_ids)
        if (
            self._declared_cells is not None
            and valid_cell_set != self._declared_cells
        ):
            raise ValueError(
                "all_cell_ids must match the cells declared when the encoder "
                "was created."
            )
        for cell_id in validated_cell_ids:
            self._get_or_create_cell_var(cell_id)

        if not isinstance(clues, (list, tuple)):
            raise ValueError("clues must be a list or tuple of Clue objects.")
        clue_map: Dict[str, Clue] = {}
        for clue in clues:
            if not isinstance(clue, Clue):
                raise ValueError("clues must contain only Clue objects.")
            if not clue.id:
                raise ValueError("Every clue must have a non-empty ID.")
            if clue.id in clue_map:
                raise ValueError(f"Duplicate clue ID: {clue.id}.")
            self._validate_clue(clue, allowed_cells=valid_cell_set)
            clue_map[clue.id] = clue

        if not isinstance(active_clue_ids, (list, tuple)):
            raise ValueError("active_clue_ids must be a list or tuple.")
        if len(active_clue_ids) != len(set(active_clue_ids)):
            raise ValueError("active_clue_ids must contain distinct clue IDs.")
        unknown_clues = [
            clue_id for clue_id in active_clue_ids if clue_id not in clue_map
        ]
        if unknown_clues:
            raise ValueError(
                f"active_clue_ids references unknown clues: {unknown_clues}."
            )

        if not isinstance(known_statuses, dict):
            raise ValueError("known_statuses must be a dictionary.")
        unknown_known_cells = [
            cell_id for cell_id in known_statuses if cell_id not in valid_cell_set
        ]
        if unknown_known_cells:
            raise ValueError(
                "known_statuses references unknown cells: "
                f"{unknown_known_cells}."
            )

        clauses: List[List[int]] = []
        clauses.extend(self.encode_known_statuses(known_statuses))

        for clue_id in active_clue_ids:
            clauses.extend(self.encode_clue(clue_map[clue_id]))

        primary_vars = {
            f"C_{cell_id}": self._get_or_create_cell_var(cell_id)
            for cell_id in validated_cell_ids
        }
        unresolved = [c for c in validated_cell_ids if c not in known_statuses]

        return KnowledgeBaseSnapshot(
            clauses=clauses,
            primary_vars=primary_vars,
            unresolved_cell_ids=unresolved,
            cell_to_var=self.cell_to_var.copy(),
            active_clue_ids=list(active_clue_ids),
            known_statuses=known_statuses.copy(),
            aux_var_count=self.aux_var_count,
        )
