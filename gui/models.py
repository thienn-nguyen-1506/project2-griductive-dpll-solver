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
class VerdictFeedback:
    """Presentation-neutral content for one rejected manual verdict."""

    title: str
    icon: str
    tone: str
    main: str
    advice: str
    button: str


def build_verdict_feedback(
    action_code: ActionCode,
    cell: CellView,
    attempted_status: Status,
    message: str | None = None,
) -> VerdictFeedback:
    """Return distinct content for NOT_PROVABLE and CONTRADICTED."""
    attempted = attempted_status.value.title()
    opposite = (
        Status.INNOCENT.value.title()
        if attempted_status is Status.CRIMINAL
        else Status.CRIMINAL.value.title()
    )
    name = cell.name or cell.cell_id

    if action_code is ActionCode.NOT_PROVABLE:
        return VerdictFeedback(
            title="Not Provable Yet",
            icon="?",
            tone="warning",
            main=(
                f"The current KB still allows both possibilities for {name}. "
                f"The verdict {attempted} is not provable yet."
            ),
            advice="Reveal more clues or use Hint before trying this card again.",
            button="Review clues",
        )
    if action_code is ActionCode.CONTRADICTED:
        return VerdictFeedback(
            title="Verdict Contradicted",
            icon="✕",
            tone="error",
            main=(
                f"The current KB proves {name} is {opposite}. "
                f"The verdict {attempted} is contradicted."
            ),
            advice=(
                "The card stays hidden, but the opposite verdict is "
                "logically forced."
            ),
            button="Try the opposite",
        )
    return VerdictFeedback(
        title="Verdict Rejected",
        icon="!",
        tone="warning",
        main=message or "The verdict could not be accepted.",
        advice="Review the current knowledge base and try again.",
        button="Keep looking",
    )


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
    revealed_clue_type: str | None = None
    revealed_clue_text: str | None = None
    revealed_clue_references: tuple[str, ...] = ()


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


@dataclass(frozen=True)
class PuzzleOption:
    """One built-in puzzle shown by the GUI level selector."""

    puzzle_id: str
    name: str
    size: int
    path: Path


@runtime_checkable
class GameGateway(Protocol):
    """The only interface the GUI uses to communicate with game logic.

    Teammates can implement this protocol in an adapter around GameEngine and
    DeductiveAgent. The GUI then only needs that adapter passed to GriductiveApp.
    """

    def get_public_state(self) -> GameView: ...

    def list_puzzles(self) -> tuple[PuzzleOption, ...]: ...

    def submit_verdict(self, cell_id: str, status: Status) -> ActionResult: ...

    def get_hint(self) -> HintResult: ...

    def auto_solve_step(self) -> ActionResult: ...

    def restart(self) -> ActionResult: ...

    def load_puzzle(self, path: Path) -> ActionResult: ...
