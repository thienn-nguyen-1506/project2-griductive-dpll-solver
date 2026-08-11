"""Deductive Logic Agent for Griductive puzzle solving.

The agent receives a :class:`KnowledgeBaseSnapshot` (the public knowledge base
at time *t*) and uses the :class:`~core.dpll.DPLLSolver` to decide which
characters are forced **Criminal**, forced **Innocent**, or still **Unknown**.

Key capabilities
----------------
* **Inconsistency detection** – checks KB_t satisfiability before deduction.
* **Entailment via 2 SAT queries** – per unresolved cell.
* **classify_all** – classifies every unresolved character.
* **choose_next_forced** – deterministic row-major selection.
* **Uniqueness check** – confirms exactly one valid solution exists.
* **Structured deduction trace** – machine-readable step log.

Usage
-----
>>> from core.agent import DeductiveAgent, KnowledgeBaseSnapshot
>>> snapshot = KnowledgeBaseSnapshot(...)
>>> agent = DeductiveAgent()
>>> result = agent.classify_all(snapshot)
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from core.dpll import DPLLSolver, DPLLMetrics


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class KnowledgeBaseSnapshot:
    """Public knowledge base at time *t* exchanged between CNF encoder and agent.

    This is the **only** interface between the CNF/Engine modules (built by
    other team members) and this agent.  All fields use plain Python types so
    there is zero coupling to implementation details of the encoder.

    Attributes
    ----------
    clauses : list[list[int]]
        CNF formula – each inner list is a disjunctive clause of integer
        literals.
    primary_vars : dict[str, int]
        Mapping from human-readable primary variable names to integer IDs
        (e.g. ``{"C_A1": 1, "C_B1": 2}``).
    unresolved_cell_ids : list[str]
        Cell IDs whose status has not yet been determined.
    cell_to_var : dict[str, int]
        Mapping from cell ID (e.g. ``"A1"``) to the primary integer variable
        that represents *"cell is Criminal"*.
    active_clue_ids : list[str]
        Identifiers of currently revealed clues contributing to KB_t.
    known_statuses : dict[str, str]
        Already-proven statuses: ``{cell_id: "CRIMINAL" | "INNOCENT"}``.
    clause_count : int
        Convenience: ``len(clauses)``.  May be set by the encoder.
    aux_var_count : int
        Number of auxiliary variables introduced by the encoder.
    """

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
    assumed_status: str          # "CRIMINAL" or "INNOCENT"
    result: str                  # "SAT" or "UNSAT"


@dataclass
class TraceStep:
    """One step in the structured deduction trace.

    Designed to be serialisable to JSON / rendered in the GUI trace panel.
    """

    step: int
    active_clue_ids: Tuple[str, ...]
    sat_queries: Tuple[SATQuery, ...]
    verdict: Optional[str]       # "CRIMINAL", "INNOCENT", or None
    cell_id: Optional[str]       # cell whose verdict was decided
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
    """Outcome of :meth:`DeductiveAgent.classify_all`.

    Attributes
    ----------
    classifications : dict[str, str]
        ``{cell_id: "CRIMINAL" | "INNOCENT" | "UNKNOWN"}`` for every
        unresolved cell.
    is_consistent : bool
        ``False`` if KB_t itself is UNSAT (inconsistent knowledge base).
    metrics : AgentMetrics
        Aggregate SAT call statistics.
    trace : list[TraceStep]
        Structured deduction trace produced during classification.
    """

    classifications: Dict[str, str]
    is_consistent: bool
    metrics: AgentMetrics
    trace: List[TraceStep] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Row-major ordering helper
# ---------------------------------------------------------------------------

_CELL_RE = re.compile(r"^([A-Z]+)(\d+)$")


def _row_major_key(cell_id: str) -> Tuple[int, str]:
    """Sort key that orders cell IDs in row-major order.

    Grid convention: column letter first, row number second (e.g. A1, B1, C1,
    A2, B2, C2 …).  Row-major means we iterate by *row number* first, then
    by *column letter* within each row.

    Returns ``(row_number, column_letters)`` so that ``sorted(ids,
    key=_row_major_key)`` yields row-major order.
    """
    m = _CELL_RE.match(cell_id)
    if m:
        col_letters, row_digits = m.groups()
        return (int(row_digits), col_letters)
    # Fallback: lexicographic.
    return (0, cell_id)


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class DeductiveAgent:
    """No-guess deductive agent for Griductive puzzles.

    The agent never guesses.  It only reveals a cell's status when the
    current knowledge base *entails* it.

    Parameters
    ----------
    solver : DPLLSolver | None
        Solver instance to reuse.  A fresh one is created if ``None``.
    """

    def __init__(self, solver: Optional[DPLLSolver] = None) -> None:
        self._solver = solver or DPLLSolver()

    # ------------------------------------------------------------------ #
    # Consistency check
    # ------------------------------------------------------------------ #

    def check_consistency(
        self,
        snapshot: KnowledgeBaseSnapshot,
        metrics: AgentMetrics,
    ) -> bool:
        """Return ``True`` if KB_t is satisfiable (consistent).

        This **must** be called before any entailment queries.  If the KB is
        inconsistent, every formula is trivially entailed and results would
        be meaningless.
        """
        result = self._solver.solve(snapshot.clauses)
        metrics._accumulate(result.metrics)
        return result.is_sat

    # ------------------------------------------------------------------ #
    # Entailment (2 SAT queries)
    # ------------------------------------------------------------------ #

    def _entails(
        self,
        clauses: List[List[int]],
        literal: int,
        metrics: AgentMetrics,
    ) -> bool:
        """Check if *clauses* ⊨ literal  (via refutation).

        Adds ¬literal to the clause set.  If the result is UNSAT then the
        original clauses entail *literal*.
        """
        augmented = clauses + [[-literal]]
        result = self._solver.solve(augmented)
        metrics._accumulate(result.metrics)
        return not result.is_sat  # UNSAT ⟹ entailed

    def classify_cell(
        self,
        snapshot: KnowledgeBaseSnapshot,
        cell_id: str,
        metrics: AgentMetrics,
    ) -> Tuple[str, Tuple[SATQuery, ...]]:
        """Classify a single cell using 2 SAT queries.

        Returns
        -------
        (status, queries) : tuple
            *status* is ``"CRIMINAL"``, ``"INNOCENT"``, or ``"UNKNOWN"``.
            *queries* records the two SAT calls for the trace.
        """
        var = snapshot.cell_to_var[cell_id]
        queries: List[SATQuery] = []

        # Query 1: KB_t ∧ ¬C_i  →  if UNSAT then C_i is forced CRIMINAL
        is_criminal = self._entails(snapshot.clauses, var, metrics)
        queries.append(SATQuery(
            cell_id=cell_id,
            assumed_status="INNOCENT",   # we assumed ¬C_i (innocent)
            result="UNSAT" if is_criminal else "SAT",
        ))

        if is_criminal:
            return "CRIMINAL", tuple(queries)

        # Query 2: KB_t ∧ C_i  →  if UNSAT then ¬C_i is forced INNOCENT
        is_innocent = self._entails(snapshot.clauses, -var, metrics)
        queries.append(SATQuery(
            cell_id=cell_id,
            assumed_status="CRIMINAL",   # we assumed C_i (criminal)
            result="UNSAT" if is_innocent else "SAT",
        ))

        if is_innocent:
            return "INNOCENT", tuple(queries)

        return "UNKNOWN", tuple(queries)

    # ------------------------------------------------------------------ #
    # Classify all unresolved cells
    # ------------------------------------------------------------------ #

    def classify_all(
        self,
        snapshot: KnowledgeBaseSnapshot,
    ) -> ClassificationResult:
        """Classify every unresolved cell in the snapshot.

        Steps:
        1. Check KB_t consistency.  If UNSAT → return INCONSISTENT.
        2. For each unresolved cell (row-major order), run 2 SAT queries.
        3. Return a :class:`ClassificationResult` with all verdicts, metrics,
           and a structured trace.
        """
        metrics = AgentMetrics()
        trace: List[TraceStep] = []
        classifications: Dict[str, str] = {}

        # Step 0: Consistency check.
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

        # Step 1+: classify each unresolved cell in row-major order.
        ordered_cells = sorted(
            snapshot.unresolved_cell_ids, key=_row_major_key,
        )

        step_counter = 1
        for cell_id in ordered_cells:
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
            step_counter += 1

        return ClassificationResult(
            classifications=classifications,
            is_consistent=True,
            metrics=metrics,
            trace=trace,
        )

    # ------------------------------------------------------------------ #
    # Choose next forced cell (row-major deterministic)
    # ------------------------------------------------------------------ #

    @staticmethod
    def choose_next_forced(
        classifications: Dict[str, str],
    ) -> Optional[Tuple[str, str]]:
        """Pick the first forced cell in row-major order.

        Parameters
        ----------
        classifications : dict[str, str]
            Output of :meth:`classify_all` → ``classifications``.

        Returns
        -------
        (cell_id, status) | None
            The first forced cell and its status, or ``None`` if no cell is
            forced.
        """
        forced = {
            cid: st for cid, st in classifications.items()
            if st in ("CRIMINAL", "INNOCENT")
        }
        if not forced:
            return None

        ordered = sorted(forced.keys(), key=_row_major_key)
        first = ordered[0]
        return first, forced[first]

    # ------------------------------------------------------------------ #
    # Uniqueness check
    # ------------------------------------------------------------------ #

    def check_uniqueness(
        self,
        snapshot: KnowledgeBaseSnapshot,
    ) -> Tuple[bool, AgentMetrics]:
        """Verify that the puzzle has exactly one valid solution.

        Algorithm:
        1. Solve KB_t with DPLL → get model *M*.
        2. Build a blocking clause that negates *M* restricted to **primary
           variables only**.
        3. Solve KB_t ∧ blocking clause.  If UNSAT the solution is unique.

        Returns
        -------
        (is_unique, metrics) : tuple
        """
        metrics = AgentMetrics()

        # Find first model.
        result1 = self._solver.solve(snapshot.clauses)
        metrics._accumulate(result1.metrics)

        if not result1.is_sat:
            # No solution at all → trivially "unique" (zero solutions).
            return True, metrics

        # Build blocking clause over primary variables.
        primary_var_ids = set(snapshot.cell_to_var.values())
        blocking_clause: List[int] = []
        for var in sorted(primary_var_ids):
            if result1.assignment is not None:
                val = result1.assignment.get(var, False)
                # Negate: if var was True in model, add -var to blocking clause.
                blocking_clause.append(-var if val else var)

        # Solve with the blocking clause added.
        augmented = snapshot.clauses + [blocking_clause]
        result2 = self._solver.solve(augmented)
        metrics._accumulate(result2.metrics)

        is_unique = not result2.is_sat
        return is_unique, metrics

    # ------------------------------------------------------------------ #
    # Single deduction step (for GUI integration)
    # ------------------------------------------------------------------ #

    def deduce_one_step(
        self,
        snapshot: KnowledgeBaseSnapshot,
    ) -> Tuple[Optional[Tuple[str, str]], ClassificationResult]:
        """Run one full classification round and return the next forced cell.

        Convenience wrapper combining :meth:`classify_all` and
        :meth:`choose_next_forced` for the GUI adapter.

        Returns
        -------
        (forced, result) : tuple
            *forced* is ``(cell_id, status)`` or ``None``.
            *result* is the full :class:`ClassificationResult`.
        """
        result = self.classify_all(snapshot)
        if not result.is_consistent:
            return None, result
        forced = self.choose_next_forced(result.classifications)
        return forced, result
