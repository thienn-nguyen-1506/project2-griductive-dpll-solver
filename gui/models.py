"""Public data contract shared by the GUI and the future game engine.

The GUI must only receive public information through these view models. Hidden
statuses and unrevealed clues stay inside the engine/agent implementation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Protocol, runtime_checkable


class Status(str, Enum):
    """Logical status of a character.

    UNKNOWN is an agent result: the current KB entails neither status. In the
    interface an unrevealed card is labelled UNSOLVED so these two ideas are
    not confused.
    """

    CRIMINAL = "CRIMINAL"
    INNOCENT = "INNOCENT"
    UNKNOWN = "UNKNOWN"


class GamePhase(str, Enum):
    READY = "READY"
    ACTIVE = "ACTIVE"
    SOLVED = "SOLVED"
    STUCK = "STUCK"
    INCONSISTENT = "INCONSISTENT"


class ActionCode(str, Enum):
    ACCEPTED = "ACCEPTED"
    NOT_PROVABLE = "NOT_PROVABLE"
    CONTRADICTED = "CONTRADICTED"
    UNKNOWN = "UNKNOWN"
    SOLVED = "SOLVED"
    INCONSISTENT = "INCONSISTENT"
    ERROR = "ERROR"
    INFO = "INFO"


@dataclass(frozen=True)
class CellView:
    """Public information that the GUI may render for one character."""

    cell_id: str
    name: str
    profession: str
    revealed: bool = False
    status: Status = Status.UNKNOWN
    clue_id: str | None = None
    clue_text: str | None = None
    clue_references: tuple[str, ...] = ()


@dataclass(frozen=True)
class SolverMetrics:
    """Optional statistics supplied by a real SAT/DPLL implementation."""

    sat_calls: int = 0
    decisions: int = 0
    propagations: int = 0
    backtracks: int = 0
    runtime_ms: float = 0.0


@dataclass(frozen=True)
class TraceEntry:
    """One structured row in the deduction trace."""

    step: int
    message: str
    active_clue_ids: tuple[str, ...] = ()
    sat_queries: tuple[str, ...] = ()
    verdict: str | None = None
    revealed_clue_id: str | None = None


@dataclass(frozen=True)
class GameView:
    """Public game state. Hidden labels and unrevealed clues do not belong here."""

    size: int
    puzzle_name: str
    step: int
    cells: tuple[CellView, ...]
    phase: GamePhase = GamePhase.READY
    trace: tuple[TraceEntry, ...] = ()
    metrics: SolverMetrics = field(default_factory=SolverMetrics)

    @property
    def solved_count(self) -> int:
        return sum(cell.revealed for cell in self.cells)

    @property
    def total_count(self) -> int:
        return len(self.cells)

    @property
    def unsolved_count(self) -> int:
        return self.total_count - self.solved_count


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


@runtime_checkable
class GameGateway(Protocol):
    """The only interface the GUI uses to communicate with game logic.

    Teammates can implement this protocol in an adapter around GameEngine and
    DeductiveAgent. The GUI then only needs that adapter passed to GriductiveApp.
    """

    def get_public_state(self) -> GameView: ...

    def submit_verdict(self, cell_id: str, status: Status) -> ActionResult: ...

    def get_hint(self) -> HintResult: ...

    def auto_solve_step(self) -> ActionResult: ...

    def restart(self) -> ActionResult: ...

    def load_puzzle(self, path: Path) -> ActionResult: ...
