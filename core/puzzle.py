"""Official puzzle JSON loader and logical validator.

The loader keeps the hidden solution and unrevealed clues in one engine-owned
object.  ``validate_puzzle`` checks the properties needed before a puzzle is
allowed into the GUI: clue truth, consistency, uniqueness, and a complete
no-guess deduction path from the initially revealed cards.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Tuple

from core.agent import DeductiveAgent
from core.encoder import CNFEncoder, Clue, ClueEvaluator


CORE_CLUE_TYPES = {
    "FACT",
    "SAME",
    "DIFFERENT",
    "EXACTLY",
    "AT_LEAST",
    "AT_MOST",
}
EXTENSION_CLUE_TYPES = {"PARITY", "COUNT_COMPARE"}
SUPPORTED_CLUE_TYPES = CORE_CLUE_TYPES | EXTENSION_CLUE_TYPES
VALID_STATUSES = {"CRIMINAL", "INNOCENT"}


@dataclass(frozen=True)
class PuzzleCell:
    cell_id: str
    name: str
    profession: str
    status: str
    clue: Clue


@dataclass(frozen=True)
class PuzzleDefinition:
    puzzle_id: str
    name: str
    size: int
    initial_revealed: Tuple[str, ...]
    cells: Tuple[PuzzleCell, ...]
    source: str = ""

    @property
    def cell_ids(self) -> Tuple[str, ...]:
        return tuple(cell.cell_id for cell in self.cells)

    @property
    def cell_map(self) -> Dict[str, PuzzleCell]:
        return {cell.cell_id: cell for cell in self.cells}

    @property
    def clues(self) -> Tuple[Clue, ...]:
        return tuple(cell.clue for cell in self.cells)

    @property
    def hidden_solution(self) -> Dict[str, str]:
        return {cell.cell_id: cell.status for cell in self.cells}


@dataclass(frozen=True)
class PuzzleValidationReport:
    puzzle_id: str
    is_valid: bool
    is_unique: bool
    deduction_order: Tuple[str, ...]
    clue_types: Tuple[str, ...]
    message: str


def _expected_cell_ids(size: int) -> list[str]:
    return [
        f"{chr(ord('A') + column)}{row}"
        for row in range(1, size + 1)
        for column in range(size)
    ]


def _require_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object.")
    return value


def _require_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string.")
    return value.strip()


def _validate_distinct_region(
    cells: Iterable[str],
    *,
    label: str,
    valid_cell_ids: set[str],
) -> list[str]:
    region = list(cells)
    if not region:
        raise ValueError(f"{label} must not be empty.")
    if len(region) != len(set(region)):
        raise ValueError(f"{label} must contain distinct cell IDs.")
    unknown = [cell for cell in region if cell not in valid_cell_ids]
    if unknown:
        raise ValueError(f"{label} references unknown cells: {unknown}.")
    return region


def _parse_clue(
    raw_clue: Any,
    *,
    owner_id: str,
    valid_cell_ids: set[str],
) -> Clue:
    data = _require_mapping(raw_clue, f"clue for {owner_id}")
    clue_id = _require_string(data.get("id"), f"clue ID for {owner_id}")
    clue_type = _require_string(
        data.get("type"), f"clue type for {owner_id}"
    ).upper()
    if clue_type not in SUPPORTED_CLUE_TYPES:
        raise ValueError(f"{clue_id} uses unsupported clue type {clue_type}.")

    target_cells = list(data.get("target_cells") or [])
    left_cells = list(data.get("left_cells") or [])
    right_cells = list(data.get("right_cells") or [])
    value = data.get("value")
    target_status = str(data.get("target_status") or "CRIMINAL").upper()
    operator = str(data.get("operator") or "").upper()
    text = str(data.get("text") or "")

    if target_status not in VALID_STATUSES:
        raise ValueError(f"{clue_id} has invalid target_status {target_status}.")

    if clue_type == "FACT":
        region = _validate_distinct_region(
            target_cells,
            label=f"{clue_id}.target_cells",
            valid_cell_ids=valid_cell_ids,
        )
        if len(region) != 1:
            raise ValueError(f"{clue_id} FACT must reference exactly one cell.")
        if str(value).upper() not in VALID_STATUSES:
            raise ValueError(f"{clue_id} FACT value must be a valid status.")
        value = str(value).upper()

    elif clue_type in {"SAME", "DIFFERENT"}:
        region = _validate_distinct_region(
            target_cells,
            label=f"{clue_id}.target_cells",
            valid_cell_ids=valid_cell_ids,
        )
        if len(region) != 2:
            raise ValueError(
                f"{clue_id} {clue_type} must reference exactly two cells."
            )

    elif clue_type in {"EXACTLY", "AT_LEAST", "AT_MOST"}:
        region = _validate_distinct_region(
            target_cells,
            label=f"{clue_id}.target_cells",
            valid_cell_ids=valid_cell_ids,
        )
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"{clue_id} value must be an integer.")
        if not 0 <= value <= len(region):
            raise ValueError(
                f"{clue_id} requires 0 <= value <= region size."
            )

    elif clue_type == "PARITY":
        _validate_distinct_region(
            target_cells,
            label=f"{clue_id}.target_cells",
            valid_cell_ids=valid_cell_ids,
        )
        value = str(value).upper()
        if value not in {"ODD", "EVEN"}:
            raise ValueError(f"{clue_id} PARITY value must be ODD or EVEN.")

    elif clue_type == "COUNT_COMPARE":
        _validate_distinct_region(
            left_cells,
            label=f"{clue_id}.left_cells",
            valid_cell_ids=valid_cell_ids,
        )
        _validate_distinct_region(
            right_cells,
            label=f"{clue_id}.right_cells",
            valid_cell_ids=valid_cell_ids,
        )
        if operator not in {"GT", "LT", "EQ", "GE", "LE"}:
            raise ValueError(
                f"{clue_id} operator must be GT, LT, EQ, GE, or LE."
            )

    return Clue(
        id=clue_id,
        type=clue_type,
        target_cells=target_cells,
        value=value,
        target_status=target_status,
        text=text,
        left_cells=left_cells,
        right_cells=right_cells,
        operator=operator,
    )

def load_puzzle(path: Path | str) -> PuzzleDefinition:
    """Load and structurally validate one official puzzle JSON file."""
    puzzle_path = Path(path)
    try:
        data = json.loads(puzzle_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Could not read {puzzle_path.name}: {error}") from error

    root = _require_mapping(data, "puzzle root")
    puzzle_id = _require_string(root.get("id"), "puzzle.id")
    name = _require_string(root.get("name"), "puzzle.name")
    size = root.get("size")
    if isinstance(size, bool) or not isinstance(size, int) or size not in {3, 4, 5}:
        raise ValueError("puzzle.size must be 3, 4, or 5.")

    expected_ids = _expected_cell_ids(size)
    expected_set = set(expected_ids)
    raw_cells = root.get("cells")
    if not isinstance(raw_cells, list) or len(raw_cells) != size * size:
        raise ValueError(f"{puzzle_id} must contain exactly {size * size} cells.")

    cells: list[PuzzleCell] = []
    clue_ids: set[str] = set()
    for index, raw_cell in enumerate(raw_cells):
        cell_data = _require_mapping(raw_cell, f"cells[{index}]")
        cell_id = _require_string(cell_data.get("id"), f"cells[{index}].id")
        if cell_id != expected_ids[index]:
            raise ValueError(
                f"{puzzle_id} cells must be in row-major order; expected "
                f"{expected_ids[index]} at index {index}, got {cell_id}."
            )
        name_value = _require_string(cell_data.get("name"), f"{cell_id}.name")
        profession = _require_string(
            cell_data.get("profession"), f"{cell_id}.profession"
        )
        status = _require_string(cell_data.get("status"), f"{cell_id}.status").upper()
        if status not in VALID_STATUSES:
            raise ValueError(f"{cell_id} has invalid status {status}.")
        clue = _parse_clue(
            cell_data.get("clue"),
            owner_id=cell_id,
            valid_cell_ids=expected_set,
        )
        if clue.id in clue_ids:
            raise ValueError(f"Duplicate clue ID: {clue.id}.")
        clue_ids.add(clue.id)
        cells.append(PuzzleCell(cell_id, name_value, profession, status, clue))

    names = [cell.name for cell in cells]
    if names != sorted(names, key=str.casefold):
        raise ValueError(f"{puzzle_id} characters must be ordered by display name.")
    if len(names) != len(set(names)):
        raise ValueError(f"{puzzle_id} contains duplicate character names.")

    initial_raw = root.get("initial_revealed")
    if not isinstance(initial_raw, list) or not initial_raw:
        raise ValueError(f"{puzzle_id} initial_revealed must be a non-empty list.")
    initial = tuple(str(cell) for cell in initial_raw)
    if len(initial) != len(set(initial)):
        raise ValueError(f"{puzzle_id} initial_revealed contains duplicates.")
    if any(cell not in expected_set for cell in initial):
        raise ValueError(f"{puzzle_id} initial_revealed references an unknown cell.")

    return PuzzleDefinition(
        puzzle_id=puzzle_id,
        name=name,
        size=size,
        initial_revealed=initial,
        cells=tuple(cells),
        source=str(root.get("source") or ""),
    )


def validate_puzzle(puzzle: PuzzleDefinition) -> PuzzleValidationReport:
    """Validate truth, uniqueness, and the public no-guess deduction loop."""
    assignment = puzzle.hidden_solution
    for cell in puzzle.cells:
        if not ClueEvaluator.evaluate(cell.clue, assignment):
            raise ValueError(
                f"{puzzle.puzzle_id}: clue {cell.clue.id} is false under "
                "the hidden solution."
            )

    all_ids = list(puzzle.cell_ids)
    all_clues = list(puzzle.clues)
    cell_map = puzzle.cell_map
    encoder = CNFEncoder(character_ids=all_ids)
    agent = DeductiveAgent()

    known_statuses = {
        cell_id: assignment[cell_id] for cell_id in puzzle.initial_revealed
    }
    active_clue_ids = [cell_map[cell_id].clue.id for cell_id in puzzle.initial_revealed]
    deduction_order: list[str] = []

    while len(known_statuses) < len(all_ids):
        snapshot = encoder.build_snapshot(
            all_cell_ids=all_ids,
            clues=all_clues,
            active_clue_ids=active_clue_ids,
            known_statuses=known_statuses,
        )
        forced, result = agent.deduce_one_step(snapshot)
        if not result.is_consistent:
            raise ValueError(
                f"{puzzle.puzzle_id}: public KB became inconsistent."
            )
        if forced is None:
            unresolved = [cell for cell in all_ids if cell not in known_statuses]
            raise ValueError(
                f"{puzzle.puzzle_id}: deduction is stuck with UNKNOWN cells "
                f"{unresolved}."
            )

        cell_id, status = forced
        if status != assignment[cell_id]:
            raise ValueError(
                f"{puzzle.puzzle_id}: solver verdict {cell_id}={status} "
                "disagrees with the hidden solution."
            )
        known_statuses[cell_id] = status
        active_clue_ids.append(cell_map[cell_id].clue.id)
        deduction_order.append(cell_id)

    complete_snapshot = encoder.build_snapshot(
        all_cell_ids=all_ids,
        clues=all_clues,
        active_clue_ids=[clue.id for clue in all_clues],
        known_statuses={
            cell_id: assignment[cell_id] for cell_id in puzzle.initial_revealed
        },
    )
    is_unique, _metrics = agent.check_uniqueness(complete_snapshot)
    if not is_unique:
        raise ValueError(
            f"{puzzle.puzzle_id}: complete clue set does not have exactly one solution."
        )

    clue_types = tuple(sorted({clue.type for clue in all_clues}))
    return PuzzleValidationReport(
        puzzle_id=puzzle.puzzle_id,
        is_valid=True,
        is_unique=True,
        deduction_order=tuple(deduction_order),
        clue_types=clue_types,
        message=(
            f"Valid: {len(puzzle.initial_revealed)} initial cards, "
            f"{len(deduction_order)} forced deductions."
        ),
    )
