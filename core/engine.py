"""Game Engine for the real Griductive reveal protocol.

The engine owns the complete puzzle, hidden solution, and unrevealed clues.  It
only asks the Deductive Agent questions about the public knowledge base and
reveals a card after the claimed verdict is logically forced.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from core.agent import AgentMetrics, ClassificationResult, DeductiveAgent, TraceStep
from core.encoder import CNFEncoder, Clue, KnowledgeBaseSnapshot
from core.puzzle import PuzzleDefinition


@dataclass(frozen=True)
class EnginePublicCell:
    cell_id: str
    name: str
    profession: str
    revealed: bool
    status: Optional[str] = None
    clue: Optional[Clue] = None


@dataclass(frozen=True)
class EngineTraceEntry:
    step: int
    message: str
    active_clue_ids: Tuple[str, ...] = ()
    sat_queries: Tuple[str, ...] = ()
    verdict: Optional[str] = None
    revealed_clue_id: Optional[str] = None
    revealed_clue_type: Optional[str] = None
    revealed_clue_text: Optional[str] = None
    revealed_clue_references: Tuple[str, ...] = ()


@dataclass(frozen=True)
class EngineAction:
    code: str
    message: str
    cell_id: Optional[str] = None
    revealed_clue: Optional[Clue] = None
    highlighted_cells: Tuple[str, ...] = ()


@dataclass(frozen=True)
class EngineHint:
    message: str
    clue_source: Optional[str] = None
    target_cells: Tuple[str, ...] = ()


class GameEngine:
    """Own hidden state and execute manual or automatic deduction steps."""

    VALID_STATUSES = {"CRIMINAL", "INNOCENT"}

    def __init__(
        self,
        puzzle: PuzzleDefinition,
        *,
        agent: Optional[DeductiveAgent] = None,
    ) -> None:
        self._puzzle = puzzle
        self._cell_map = puzzle.cell_map
        self._solution = puzzle.hidden_solution
        self._all_clues = list(puzzle.clues)
        self._clue_owner = {
            cell.clue.id: cell.cell_id for cell in puzzle.cells
        }
        self._encoder = CNFEncoder(
            character_ids=list(puzzle.cell_ids),
            grid_size=puzzle.size,
        )
        self._agent = agent or DeductiveAgent()
        self.restart()

    @property
    def size(self) -> int:
        return self._puzzle.size

    @property
    def puzzle_name(self) -> str:
        return self._puzzle.name

    @property
    def step(self) -> int:
        return self._step

    @property
    def phase(self) -> str:
        return self._phase

    @property
    def trace(self) -> Tuple[EngineTraceEntry, ...]:
        return tuple(self._trace)

    @property
    def metrics(self) -> AgentMetrics:
        return self._metrics

    @property
    def known_statuses(self) -> dict[str, str]:
        return dict(self._known_statuses)

    def public_cells(self) -> Tuple[EnginePublicCell, ...]:
        """Return a public-only cell snapshot with hidden fields removed."""
        cells: list[EnginePublicCell] = []
        for cell in self._puzzle.cells:
            revealed = cell.cell_id in self._revealed_cards
            cells.append(
                EnginePublicCell(
                    cell_id=cell.cell_id,
                    name=cell.name,
                    profession=cell.profession,
                    revealed=revealed,
                    status=self._known_statuses.get(cell.cell_id) if revealed else None,
                    clue=cell.clue if revealed else None,
                )
            )
        return tuple(cells)

    def get_kb_snapshot(self) -> KnowledgeBaseSnapshot:
        """Build KB_t from revealed clues and previously proved statuses only."""
        return self._encoder.build_snapshot(
            all_cell_ids=list(self._puzzle.cell_ids),
            clues=self._all_clues,
            active_clue_ids=list(self._active_clue_ids),
            known_statuses=dict(self._known_statuses),
        )

    @staticmethod
    def clue_references(clue: Clue) -> Tuple[str, ...]:
        if clue.type == "COUNT_COMPARE":
            return tuple(dict.fromkeys(clue.left_cells + clue.right_cells))
        return tuple(clue.target_cells)

    def _merge_metrics(self, metrics: AgentMetrics) -> None:
        self._metrics.sat_calls += metrics.sat_calls
        self._metrics.total_decisions += metrics.total_decisions
        self._metrics.total_propagations += metrics.total_propagations
        self._metrics.total_backtracks += metrics.total_backtracks
        self._metrics.total_runtime_ms += metrics.total_runtime_ms

    @staticmethod
    def _trace_for_cell(
        result: ClassificationResult,
        cell_id: str,
    ) -> Optional[TraceStep]:
        return next((step for step in result.trace if step.cell_id == cell_id), None)

    @staticmethod
    def _format_sat_queries(trace_step: Optional[TraceStep]) -> Tuple[str, ...]:
        if trace_step is None:
            return ()
        return tuple(
            f"KB and {query.cell_id}={query.assumed_status} -> {query.result}"
            for query in trace_step.sat_queries
        )

    def _classify(self) -> ClassificationResult:
        result = self._agent.classify_all(self.get_kb_snapshot())
        self._merge_metrics(result.metrics)
        return result

    def _accept_forced(
        self,
        cell_id: str,
        status: str,
        result: ClassificationResult,
    ) -> EngineAction:
        # Hidden truth is used only as an internal integrity assertion; the
        # verdict above was selected solely from the public KB.
        if self._solution[cell_id] != status:
            self._phase = "INCONSISTENT"
            return EngineAction(
                "INCONSISTENT",
                f"The public KB conflicts with the hidden solution at {cell_id}.",
                cell_id,
            )

        trace_step = self._trace_for_cell(result, cell_id)
        clue = self._cell_map[cell_id].clue
        self._known_statuses[cell_id] = status
        self._revealed_cards.add(cell_id)
        self._active_clue_ids.append(clue.id)
        self._step += 1
        self._phase = (
            "SOLVED"
            if len(self._revealed_cards) == len(self._puzzle.cells)
            else "ACTIVE"
        )
        self._trace.append(
            EngineTraceEntry(
                step=self._step,
                message=f"{cell_id} was proved {status}; its clue joined the KB.",
                active_clue_ids=tuple(self._active_clue_ids),
                sat_queries=self._format_sat_queries(trace_step),
                verdict=f"{cell_id} = {status}",
                revealed_clue_id=clue.id,
                revealed_clue_type=clue.type,
                revealed_clue_text=clue.text,
                revealed_clue_references=self.clue_references(clue),
            )
        )

        code = "SOLVED" if self._phase == "SOLVED" else "ACCEPTED"
        message = (
            "All characters have been solved."
            if code == "SOLVED"
            else f"{cell_id}: verdict accepted. A new clue was revealed."
        )
        return EngineAction(
            code=code,
            message=message,
            cell_id=cell_id,
            revealed_clue=clue,
            highlighted_cells=self.clue_references(clue),
        )

    def submit_verdict(self, cell_id: str, claimed_status: str) -> EngineAction:
        """Accept only verdicts entailed by the current public KB."""
        claimed_status = str(claimed_status).upper()
        if cell_id not in self._cell_map:
            return EngineAction("ERROR", f"Cell {cell_id} does not exist.")
        if claimed_status not in self.VALID_STATUSES:
            return EngineAction("ERROR", f"Invalid verdict: {claimed_status}.", cell_id)
        if cell_id in self._revealed_cards:
            return EngineAction(
                "INFO",
                f"{cell_id} is already revealed as {self._known_statuses[cell_id]}.",
                cell_id,
            )
        if self._phase == "SOLVED":
            return EngineAction("SOLVED", "All characters are already solved.")
        if self._phase == "INCONSISTENT":
            return EngineAction("INCONSISTENT", "The public KB is inconsistent.")

        result = self._classify()
        if not result.is_consistent:
            self._phase = "INCONSISTENT"
            return EngineAction("INCONSISTENT", "The public KB is inconsistent.")

        forced_status = result.classifications.get(cell_id, "UNKNOWN")
        if forced_status == "UNKNOWN":
            return EngineAction(
                "NOT_PROVABLE",
                f"{cell_id}: the current KB entails neither CRIMINAL nor INNOCENT.",
                cell_id,
            )
        if forced_status != claimed_status:
            return EngineAction(
                "CONTRADICTED",
                f"{cell_id}: the KB entails {forced_status}, so "
                f"{claimed_status} is contradicted.",
                cell_id,
            )
        return self._accept_forced(cell_id, forced_status, result)

    def auto_solve_step(self) -> EngineAction:
        """Perform exactly one deterministic no-guess reveal step."""
        if self._phase == "SOLVED":
            return EngineAction("SOLVED", "All characters are already solved.")
        if self._phase == "INCONSISTENT":
            return EngineAction("INCONSISTENT", "The public KB is inconsistent.")

        result = self._classify()
        if not result.is_consistent:
            self._phase = "INCONSISTENT"
            return EngineAction("INCONSISTENT", "The public KB is inconsistent.")

        forced = self._agent.choose_next_forced(result.classifications)
        if forced is None:
            self._phase = "STUCK"
            return EngineAction(
                "UNKNOWN",
                "No unsolved character is logically forced by the current KB.",
            )
        cell_id, status = forced
        return self._accept_forced(cell_id, status, result)

    def get_hint(self) -> EngineHint:
        """Identify a forced target without reading or returning its hidden label."""
        if self._phase == "SOLVED":
            return EngineHint("The puzzle is already solved.")
        if self._phase == "INCONSISTENT":
            return EngineHint("The public KB is inconsistent.")

        result = self._classify()
        if not result.is_consistent:
            self._phase = "INCONSISTENT"
            return EngineHint("The public KB is inconsistent.")
        forced = self._agent.choose_next_forced(result.classifications)
        if forced is None:
            return EngineHint("No character is currently forced by the public KB.")

        target, _status = forced
        clue_source = next(
            (
                self._clue_owner[clue_id]
                for clue_id in self._active_clue_ids
                if target
                in self.clue_references(
                    self._cell_map[self._clue_owner[clue_id]].clue
                )
            ),
            None,
        )
        target_cells = (
            tuple(dict.fromkeys((clue_source, target)))
            if clue_source
            else (target,)
        )
        message = (
            f"Review {clue_source}'s clue; {target} can be proved next."
            if clue_source
            else f"A forced verdict is available for {target}."
        )
        return EngineHint(message, clue_source, target_cells)

    def restart(self) -> EngineAction:
        """Restore the initial public cards and clear all solver history."""
        self._known_statuses = {
            cell_id: self._solution[cell_id]
            for cell_id in self._puzzle.initial_revealed
        }
        self._revealed_cards = set(self._puzzle.initial_revealed)
        self._active_clue_ids = [
            self._cell_map[cell_id].clue.id
            for cell_id in self._puzzle.initial_revealed
        ]
        self._step = 0
        self._phase = (
            "SOLVED"
            if len(self._revealed_cards) == len(self._puzzle.cells)
            else "ACTIVE"
        )
        self._metrics = AgentMetrics()
        self._trace = [
            EngineTraceEntry(
                step=0,
                message=(
                    f"Loaded {len(self._revealed_cards)} initial public clues."
                ),
                active_clue_ids=tuple(self._active_clue_ids),
            )
        ]
        return EngineAction("INFO", "Puzzle restarted from its initial clues.")
