"""Adapter connecting the GUI contract to the real logical game engine."""

from __future__ import annotations

from pathlib import Path

from core.engine import EngineAction, GameEngine
from core.puzzle import load_puzzle as read_puzzle
from core.puzzle import validate_puzzle
from gui.models import (
    ActionCode,
    ActionResult,
    CellView,
    GamePhase,
    GameView,
    HintResult,
    PuzzleOption,
    SolverMetrics,
    Status,
    TraceEntry,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PUZZLE = PROJECT_ROOT / "puzzles" / "level_01_3x3.json"


class RealGameGateway:
    """Expose public engine state in the immutable models expected by the GUI."""

    def __init__(self, puzzle_path: Path | str = DEFAULT_PUZZLE) -> None:
        puzzle = read_puzzle(puzzle_path)
        validate_puzzle(puzzle)
        self._engine = GameEngine(puzzle)

    @property
    def engine(self) -> GameEngine:
        """Engine access for integration tests; GUI code does not use it."""
        return self._engine

    @staticmethod
    def _action_result(action: EngineAction) -> ActionResult:
        try:
            code = ActionCode(action.code)
        except ValueError:
            code = ActionCode.ERROR
        return ActionResult(
            code=code,
            message=action.message,
            cell_id=action.cell_id,
            revealed_clue=(
                action.revealed_clue.text if action.revealed_clue else None
            ),
            highlighted_cells=action.highlighted_cells,
        )

    def get_public_state(self) -> GameView:
        cells = []
        for cell in self._engine.public_cells():
            clue = cell.clue
            cells.append(
                CellView(
                    cell_id=cell.cell_id,
                    name=cell.name,
                    profession=cell.profession,
                    revealed=cell.revealed,
                    status=(Status(cell.status) if cell.status else Status.UNKNOWN),
                    clue_id=clue.id if clue else None,
                    clue_text=clue.text if clue else None,
                    clue_references=(
                        self._engine.clue_references(clue) if clue else ()
                    ),
                )
            )

        metrics = self._engine.metrics
        trace = tuple(
            TraceEntry(
                step=entry.step,
                message=entry.message,
                active_clue_ids=entry.active_clue_ids,
                sat_queries=entry.sat_queries,
                verdict=entry.verdict,
                revealed_clue_id=entry.revealed_clue_id,
                revealed_clue_type=entry.revealed_clue_type,
                revealed_clue_text=entry.revealed_clue_text,
                revealed_clue_references=entry.revealed_clue_references,
            )
            for entry in self._engine.trace
        )
        return GameView(
            size=self._engine.size,
            puzzle_name=self._engine.puzzle_name,
            step=self._engine.step,
            cells=tuple(cells),
            phase=GamePhase(self._engine.phase),
            trace=trace,
            metrics=SolverMetrics(
                sat_calls=metrics.sat_calls,
                decisions=metrics.total_decisions,
                propagations=metrics.total_propagations,
                backtracks=metrics.total_backtracks,
                runtime_ms=metrics.total_runtime_ms,
            ),
        )

    def list_puzzles(self) -> tuple[PuzzleOption, ...]:
        """Return validated built-in levels without exposing hidden content."""
        options = []
        for path in sorted((PROJECT_ROOT / "puzzles").glob("level_*.json")):
            try:
                puzzle = read_puzzle(path)
            except ValueError:
                continue
            options.append(
                PuzzleOption(
                    puzzle_id=puzzle.puzzle_id,
                    name=puzzle.name,
                    size=puzzle.size,
                    path=path,
                )
            )
        return tuple(options)

    def submit_verdict(self, cell_id: str, status: Status) -> ActionResult:
        return self._action_result(
            self._engine.submit_verdict(cell_id, status.value)
        )

    def get_hint(self) -> HintResult:
        hint = self._engine.get_hint()
        return HintResult(
            message=hint.message,
            clue_source=hint.clue_source,
            target_cells=hint.target_cells,
        )

    def auto_solve_step(self) -> ActionResult:
        return self._action_result(self._engine.auto_solve_step())

    def restart(self) -> ActionResult:
        return self._action_result(self._engine.restart())

    def load_puzzle(self, path: Path) -> ActionResult:
        """Validate before swapping engines so a bad file changes no state."""
        try:
            puzzle = read_puzzle(path)
            validate_puzzle(puzzle)
            next_engine = GameEngine(puzzle)
        except (OSError, TypeError, ValueError) as error:
            return ActionResult(
                ActionCode.ERROR,
                f"Could not load {path.name}: {error}",
            )

        self._engine = next_engine
        return ActionResult(
            ActionCode.INFO,
            f"Loaded {path.name} as a validated logical puzzle.",
        )
