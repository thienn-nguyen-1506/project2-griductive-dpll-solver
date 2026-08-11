"""DPLL SAT Solver with unit propagation, conflict detection, and backtracking.

This module implements the Davis–Putnam–Logemann–Loveland (DPLL) algorithm for
solving the Boolean Satisfiability Problem (SAT).  It operates on CNF formulas
represented as lists of integer-literal clauses and guarantees a **complete
assignment** for all variables when the formula is satisfiable.

Usage
-----
>>> from core.dpll import DPLLSolver
>>> solver = DPLLSolver()
>>> sat, model, metrics = solver.solve([[1, 2], [-1, 3], [-2, -3]])
>>> sat
True
>>> model[1]   # True or False
...
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class DPLLMetrics:
    """Statistics collected during a single DPLL solve call."""

    decisions: int = 0
    propagations: int = 0
    backtracks: int = 0
    runtime_ms: float = 0.0

    def __repr__(self) -> str:
        return (
            f"DPLLMetrics(decisions={self.decisions}, "
            f"propagations={self.propagations}, "
            f"backtracks={self.backtracks}, "
            f"runtime_ms={self.runtime_ms:.3f})"
        )


@dataclass
class DPLLResult:
    """Result returned by :meth:`DPLLSolver.solve`.

    Attributes
    ----------
    is_sat : bool
        ``True`` if the formula is satisfiable.
    assignment : dict[int, bool] | None
        A **complete** variable assignment if SAT, else ``None``.
        Keys are positive variable IDs; values are ``True``/``False``.
    metrics : DPLLMetrics
        Solver statistics for this run.
    """

    is_sat: bool
    assignment: Optional[Dict[int, bool]]
    metrics: DPLLMetrics


# ---------------------------------------------------------------------------
# Solver
# ---------------------------------------------------------------------------

class DPLLSolver:
    """DPLL SAT solver producing complete assignments.

    The solver uses:
    * **Unit propagation** – iteratively assigns forced literals.
    * **Conflict detection** – detects empty clauses early.
    * **Deterministic variable selection** – picks the smallest unassigned
      variable ID to ensure reproducible results.
    * **Recursive backtracking** – tries both polarities.

    Parameters
    ----------
    None – the solver is stateless between calls.

    Examples
    --------
    >>> solver = DPLLSolver()
    >>> r = solver.solve([[1, -2], [2, 3], [-1, -3]])
    >>> r.is_sat
    True
    >>> all(v in r.assignment for v in [1, 2, 3])
    True
    """

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def solve(self, clauses: List[List[int]]) -> DPLLResult:
        """Solve a CNF formula.

        Parameters
        ----------
        clauses : list[list[int]]
            CNF formula.  Each inner list is a disjunctive clause of integer
            literals.  A positive integer ``k`` represents variable *k*; a
            negative integer ``-k`` represents ¬k.  Variable IDs must be ≥ 1.

        Returns
        -------
        DPLLResult
            Contains satisfiability flag, complete assignment (if SAT), and
            solver metrics.
        """
        metrics = DPLLMetrics()
        start = time.perf_counter()

        # Collect all variable IDs that appear in the formula.
        all_vars: Set[int] = set()
        for clause in clauses:
            for lit in clause:
                all_vars.add(abs(lit))

        # Internal representation: list of frozensets for immutable clauses.
        frozen: List[frozenset] = [frozenset(c) for c in clauses]

        assignment: Dict[int, bool] = {}
        sat = self._dpll(frozen, assignment, all_vars, metrics)

        # Ensure complete assignment: any variable not yet assigned gets a
        # default value (False).  This satisfies the project requirement of
        # returning a *complete* assignment.
        if sat:
            for var in all_vars:
                if var not in assignment:
                    assignment[var] = False

        metrics.runtime_ms = (time.perf_counter() - start) * 1000.0

        return DPLLResult(
            is_sat=sat,
            assignment=assignment if sat else None,
            metrics=metrics,
        )

    # ------------------------------------------------------------------ #
    # Internal recursive algorithm
    # ------------------------------------------------------------------ #

    def _dpll(
        self,
        clauses: List[frozenset],
        assignment: Dict[int, bool],
        all_vars: Set[int],
        metrics: DPLLMetrics,
    ) -> bool:
        """Core recursive DPLL procedure.

        Operates on a list of frozenset clauses.  Modifies *assignment* in
        place and backtracks on failure.
        """
        # 1. Unit propagation – loop until fixpoint.
        clauses, conflict = self._unit_propagate(clauses, assignment, metrics)
        if conflict:
            return False

        # 2. Check for satisfiability: no clauses left ⇒ SAT.
        if not clauses:
            return True

        # 3. Choose the next unassigned variable (deterministic: smallest ID).
        var = self._choose_variable(clauses, assignment, all_vars)
        if var is None:
            # All variables assigned but clauses remain ⇒ need to evaluate.
            # This shouldn't happen after proper unit propagation, but guard.
            return not clauses

        # 4. Branch on var = True, then var = False.
        for value in (True, False):
            metrics.decisions += 1
            saved_assignment = dict(assignment)

            assignment[var] = value
            new_clauses = self._assign(clauses, var, value)

            if self._dpll(new_clauses, assignment, all_vars, metrics):
                return True

            # Backtrack: restore assignment.
            metrics.backtracks += 1
            assignment.clear()
            assignment.update(saved_assignment)

        return False

    # ------------------------------------------------------------------ #
    # Unit propagation
    # ------------------------------------------------------------------ #

    def _unit_propagate(
        self,
        clauses: List[frozenset],
        assignment: Dict[int, bool],
        metrics: DPLLMetrics,
    ) -> Tuple[List[frozenset], bool]:
        """Repeatedly find and propagate unit clauses.

        Returns
        -------
        (clauses, conflict) : tuple
            Updated clause list and a flag indicating whether a conflict
            (empty clause) was found.
        """
        changed = True
        while changed:
            changed = False
            for clause in clauses:
                if len(clause) == 1:
                    lit = next(iter(clause))
                    var = abs(lit)
                    val = lit > 0
                    metrics.propagations += 1
                    assignment[var] = val
                    clauses = self._assign(clauses, var, val)
                    changed = True
                    # Check for conflict after propagation.
                    if any(len(c) == 0 for c in clauses):
                        return clauses, True
                    break  # Restart scan after modification.

            # Check for empty clause (conflict).
            if any(len(c) == 0 for c in clauses):
                return clauses, True

        return clauses, False

    # ------------------------------------------------------------------ #
    # Variable selection
    # ------------------------------------------------------------------ #

    @staticmethod
    def _choose_variable(
        clauses: List[frozenset],
        assignment: Dict[int, bool],
        all_vars: Set[int],
    ) -> Optional[int]:
        """Deterministic variable selection: pick the smallest unassigned ID.

        This ensures reproducible solving behaviour across runs, which is
        required by the project specification.
        """
        unassigned = sorted(v for v in all_vars if v not in assignment)
        return unassigned[0] if unassigned else None

    # ------------------------------------------------------------------ #
    # Clause simplification
    # ------------------------------------------------------------------ #

    @staticmethod
    def _assign(
        clauses: List[frozenset],
        var: int,
        value: bool,
    ) -> List[frozenset]:
        """Return a simplified clause list after assigning *var* = *value*.

        * Clauses containing the satisfied literal are removed (satisfied).
        * The negated literal is removed from remaining clauses.
        """
        true_lit = var if value else -var
        false_lit = -true_lit

        new_clauses: List[frozenset] = []
        for clause in clauses:
            if true_lit in clause:
                # Clause is satisfied – drop it.
                continue
            if false_lit in clause:
                # Remove the falsified literal.
                new_clauses.append(clause - {false_lit})
            else:
                new_clauses.append(clause)
        return new_clauses
