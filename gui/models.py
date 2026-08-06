from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Protocol


class Status(str, Enum):
    CRIMINAL = "CRIMINAL"
    INNOCENT = "INNOCENT"
    UNKNOWN = "UNKNOWN"


class ActionCode(str, Enum):
    ACCEPTED = "ACCEPTED"
    NOT_PROVABLE = "NOT_PROVABLE"
    CONTRADICTED = "CONTRADICTED"
    INCONSISTENT = "INCONSISTENT"
    INFO = "INFO"


@dataclass(frozen=True)
class CellView:
    """Public information that the GUI may render for one character."""

    cell_id: str
    name: str
    profession: str
    revealed: bool = False
    status: Status = Status.UNKNOWN
    clue_text: str | None = None
    clue_references: tuple[str, ...] = ()


@dataclass(frozen=True)
class GameView:
    """Public game state. Hidden labels and unrevealed clues do not belong here."""

    size: int
    puzzle_name: str
    step: int
    cells: tuple[CellView, ...]
    trace: tuple[str, ...] = ()

    @property
    def solved_count(self) -> int:
        return sum(cell.revealed for cell in self.cells)


@dataclass(frozen=True)
class ActionResult:
    code: ActionCode
    message: str
    cell_id: str | None = None
    revealed_clue: str | None = None
    highlighted_cells: tuple[str, ...] = ()


@dataclass(frozen=True)
class HintResult:
    message: str
    clue_source: str | None = None
    target_cells: tuple[str, ...] = ()


class GameGateway(Protocol):
    """The only interface the GUI should use to communicate with the game."""

    def get_public_state(self) -> GameView: ...

    def submit_verdict(self, cell_id: str, status: Status) -> ActionResult: ...

    def get_hint(self) -> HintResult: ...

    def auto_solve_step(self) -> ActionResult: ...

    def restart(self) -> ActionResult: ...

    def load_puzzle(self, path: Path) -> ActionResult: ...
