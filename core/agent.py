"""Deductive Logic Agent for Griductive puzzle solving.

The agent receives a KnowledgeBaseSnapshot (the public knowledge base
at time t) and uses the DPLLSolver to decide which characters are forced 
CRIMINAL, forced INNOCENT, or still UNKNOWN.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from core.dpll import DPLLMetrics, DPLLSolver


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class KnowledgeBaseSnapshot:
    """Public knowledge base snapshot at time t."""

    clauses: List[List[int]]
    primary_vars: Dict[str, int]
    unresolved_cell_ids: List[str]
    cell_to_var: Dict[str, int]
    active_clue_ids: List[str]
    known_statuses: Dict[str, str]
    clause_count: int = 0
    aux_var_count: int = 0

    def __post_init__(self) -> None:
        if self.clause_count == 0:
            self.clause_count = len(self.clauses)


@dataclass
class SATQuery:
    """One structured SAT query record inside a trace entry."""

    cell_id: str
    assumed_status: str  # "CRIMINAL" or "INNOCENT"
    result: str          # "SAT" or "UNSAT"


@dataclass
class TraceStep:
    """One step in the structured deduction trace."""

    step: int
    active_clue_ids: Tuple[str, ...]
    sat_queries: Tuple[SATQuery, ...]
    verdict: Optional[str]        # "CRIMINAL", "INNOCENT", or None
    cell_id: Optional[str]        # cell whose verdict was decided
    revealed_clue_id: Optional[str] = None
    message: str = ""


@dataclass
class AgentMetrics:
    """Aggregate metrics across all SAT calls made by the agent."""

    sat_calls: int = 0
    total_decisions: int = 0
    total_propagations: int = 0
    total_backtracks: int = 0
    total_runtime_ms: float = 0.0

    def _accumulate(self, dpll_metrics: DPLLMetrics) -> None:
        """Fold one DPLL run's metrics into the aggregate."""
        self.sat_calls += 1
        self.total_decisions += dpll_metrics.decisions
        self.total_propagations += dpll_metrics.propagations
        self.total_backtracks += dpll_metrics.backtracks
        self.total_runtime_ms += dpll_metrics.runtime_ms

    def __repr__(self) -> str:
        return (
            f"AgentMetrics(sat_calls={self.sat_calls}, "
            f"decisions={self.total_decisions}, "
            f"propagations={self.total_propagations}, "
            f"backtracks={self.total_backtracks}, "
            f"runtime_ms={self.total_runtime_ms:.3f})"
        )


@dataclass
class ClassificationResult:
    """Outcome of DeductiveAgent.classify_all."""

    classifications: Dict[str, str]
    is_consistent: bool
    metrics: AgentMetrics
    trace: List[TraceStep] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Row-major ordering helper
# ---------------------------------------------------------------------------

_CELL_RE = re.compile(r"^([A-Z]+)(\d+)$")


def _row_major_key(cell_id: str) -> Tuple[int, str]:
    """Sort key that orders cell IDs in row-major order (A1, B1, C1, A2, B2...)."""
    m = _CELL_RE.match(cell_id)
    if m:
        col_letters, row_digits = m.groups()
        return (int(row_digits), col_letters)
    return (0, cell_id)


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class DeductiveAgent:
    """No-guess deductive agent for Griductive puzzles."""

    def __init__(self, solver: Optional[DPLLSolver] = None) -> None:
        self._solver = solver or DPLLSolver()

    def check_consistency(
        self,
        snapshot: KnowledgeBaseSnapshot,
        metrics: AgentMetrics,
    ) -> bool:
        """Return True if KB_t is satisfiable (consistent)."""
        result = self._solver.solve(snapshot.clauses)
        metrics._accumulate(result.metrics)
        return result.is_sat

    def _entails(
        self,
        clauses: List[List[int]],
        literal: int,
        metrics: AgentMetrics,
    ) -> bool:
        """Check if clauses ⊨ literal via refutation (KB ∧ ¬literal is UNSAT)."""
        augmented = clauses + [[-literal]]
        result = self._solver.solve(augmented)
        metrics._accumulate(result.metrics)
        return not result.is_sat

    def classify_cell(
        self,
        snapshot: KnowledgeBaseSnapshot,
        cell_id: str,
        metrics: AgentMetrics,
    ) -> Tuple[str, Tuple[SATQuery, ...]]:
        """Classify a single cell using 1 or 2 SAT queries."""
        var = snapshot.cell_to_var[cell_id]
        queries: List[SATQuery] = []

        # Query 1: Test KB_t ∧ ¬C_i -> UNSAT implies C_i is forced CRIMINAL
        is_criminal = self._entails(snapshot.clauses, var, metrics)
        queries.append(SATQuery(
            cell_id=cell_id,
            assumed_status="INNOCENT",
            result="UNSAT" if is_criminal else "SAT",
        ))

        if is_criminal:
            return "CRIMINAL", tuple(queries)

        # Query 2: Test KB_t ∧ C_i -> UNSAT implies ¬C_i is forced INNOCENT
        is_innocent = self._entails(snapshot.clauses, -var, metrics)
        queries.append(SATQuery(
            cell_id=cell_id,
            assumed_status="CRIMINAL",
            result="UNSAT" if is_innocent else "SAT",
        ))

        if is_innocent:
            return "INNOCENT", tuple(queries)

        return "UNKNOWN", tuple(queries)

    def classify_all(
        self,
        snapshot: KnowledgeBaseSnapshot,
    ) -> ClassificationResult:
        """Classify every unresolved cell in row-major order."""
        metrics = AgentMetrics()
        trace: List[TraceStep] = []
        classifications: Dict[str, str] = {}

        if not self.check_consistency(snapshot, metrics):
            return ClassificationResult(
                classifications={},
                is_consistent=False,
                metrics=metrics,
                trace=[TraceStep(
                    step=0,
                    active_clue_ids=tuple(snapshot.active_clue_ids),
                    sat_queries=(),
                    verdict=None,
                    cell_id=None,
                    message="KB_t is UNSAT – knowledge base is INCONSISTENT.",
                )],
            )

        ordered_cells = sorted(
            snapshot.unresolved_cell_ids, key=_row_major_key,
        )

        for step_counter, cell_id in enumerate(ordered_cells, start=1):
            status, queries = self.classify_cell(snapshot, cell_id, metrics)
            classifications[cell_id] = status

            trace.append(TraceStep(
                step=step_counter,
                active_clue_ids=tuple(snapshot.active_clue_ids),
                sat_queries=queries,
                verdict=status if status != "UNKNOWN" else None,
                cell_id=cell_id,
                message=(
                    f"Cell {cell_id}: {status}"
                    if status != "UNKNOWN"
                    else f"Cell {cell_id}: neither status is forced."
                ),
            ))

        return ClassificationResult(
            classifications=classifications,
            is_consistent=True,
            metrics=metrics,
            trace=trace,
        )

    @staticmethod
    def choose_next_forced(
        classifications: Dict[str, str],
    ) -> Optional[Tuple[str, str]]:
        """Pick the first forced cell in row-major order."""
        forced = {
            cid: st for cid, st in classifications.items()
            if st in ("CRIMINAL", "INNOCENT")
        }
        if not forced:
            return None

        ordered = sorted(forced.keys(), key=_row_major_key)
        first = ordered[0]
        return first, forced[first]

    def check_uniqueness(
        self,
        snapshot: KnowledgeBaseSnapshot,
    ) -> Tuple[bool, AgentMetrics]:
        """Verify that the puzzle has at most one valid assignment to primary variables."""
        metrics = AgentMetrics()

        result1 = self._solver.solve(snapshot.clauses)
        metrics._accumulate(result1.metrics)

        if not result1.is_sat:
            return True, metrics

        primary_var_ids = set(snapshot.cell_to_var.values())
        blocking_clause: List[int] = []

        if result1.assignment is None:
            return False, metrics

        for var in sorted(primary_var_ids):
            val = result1.assignment.get(var, False)
            blocking_clause.append(-var if val else var)

        augmented = snapshot.clauses + [blocking_clause]
        result2 = self._solver.solve(augmented)
        metrics._accumulate(result2.metrics)

        return not result2.is_sat, metrics

    def deduce_one_step(
        self,
        snapshot: KnowledgeBaseSnapshot,
    ) -> Tuple[Optional[Tuple[str, str]], ClassificationResult]:
        """Convenience wrapper to run classification and return the next forced cell."""
        result = self.classify_all(snapshot)
        if not result.is_consistent:
            return None, result
        forced = self.choose_next_forced(result.classifications)
        return forced, result