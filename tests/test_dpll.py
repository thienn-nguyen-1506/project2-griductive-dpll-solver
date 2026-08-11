"""Unit tests for the DPLL SAT Solver (core/dpll.py).

Covers:
* Satisfiable and unsatisfiable formulas.
* Unit propagation correctness.
* Complete assignment guarantee.
* Empty formula / single-clause edge cases.
* Metrics tracking (decisions, propagations, backtracks).
"""

import unittest

from core.dpll import DPLLSolver, DPLLResult


class TestDPLLBasicSAT(unittest.TestCase):
    """Basic satisfiability checks."""

    def setUp(self) -> None:
        self.solver = DPLLSolver()

    # ------------------------------------------------------------------ #
    # Satisfiable formulas
    # ------------------------------------------------------------------ #

    def test_single_positive_literal(self) -> None:
        """[[1]] → SAT with 1 = True."""
        r = self.solver.solve([[1]])
        self.assertTrue(r.is_sat)
        self.assertIsNotNone(r.assignment)
        self.assertTrue(r.assignment[1])

    def test_single_negative_literal(self) -> None:
        """[[-1]] → SAT with 1 = False."""
        r = self.solver.solve([[-1]])
        self.assertTrue(r.is_sat)
        self.assertIsNotNone(r.assignment)
        self.assertFalse(r.assignment[1])

    def test_two_unit_clauses_consistent(self) -> None:
        """[[1], [2]] → SAT with both True."""
        r = self.solver.solve([[1], [2]])
        self.assertTrue(r.is_sat)
        self.assertTrue(r.assignment[1])
        self.assertTrue(r.assignment[2])

    def test_simple_satisfiable(self) -> None:
        """(1 ∨ 2) ∧ (¬1 ∨ 3) ∧ (¬2 ∨ ¬3) is SAT."""
        r = self.solver.solve([[1, 2], [-1, 3], [-2, -3]])
        self.assertTrue(r.is_sat)
        self._verify_model(r, [[1, 2], [-1, 3], [-2, -3]])

    def test_three_variable_sat(self) -> None:
        """(1 ∨ 2 ∨ 3) ∧ (¬1 ∨ ¬2) ∧ (¬2 ∨ ¬3) ∧ (¬1 ∨ ¬3)."""
        clauses = [[1, 2, 3], [-1, -2], [-2, -3], [-1, -3]]
        r = self.solver.solve(clauses)
        self.assertTrue(r.is_sat)
        self._verify_model(r, clauses)

    # ------------------------------------------------------------------ #
    # Unsatisfiable formulas
    # ------------------------------------------------------------------ #

    def test_contradicting_units(self) -> None:
        """[[1], [-1]] → UNSAT."""
        r = self.solver.solve([[1], [-1]])
        self.assertFalse(r.is_sat)
        self.assertIsNone(r.assignment)

    def test_unsatisfiable_three_vars(self) -> None:
        """Classic pigeonhole-like 3-variable UNSAT."""
        clauses = [
            [1, 2], [1, -2], [-1, 2], [-1, -2],
        ]
        r = self.solver.solve(clauses)
        self.assertFalse(r.is_sat)

    def test_unsatisfiable_small(self) -> None:
        """(1) ∧ (2) ∧ (¬1 ∨ ¬2) ∧ (¬1 ∨ 2) ∧ (1 ∨ ¬2)."""
        # This forces 1=T, 2=T but clause [-1,-2] blocks it.
        # Then 1=T, 2=F blocked by [2].  All paths fail.
        clauses = [[1], [2], [-1, -2]]
        r = self.solver.solve(clauses)
        self.assertFalse(r.is_sat)

    # ------------------------------------------------------------------ #
    # Edge cases
    # ------------------------------------------------------------------ #

    def test_empty_formula(self) -> None:
        """No clauses → trivially SAT."""
        r = self.solver.solve([])
        self.assertTrue(r.is_sat)

    def test_empty_clause_in_formula(self) -> None:
        """A formula containing the empty clause → UNSAT."""
        r = self.solver.solve([[]])
        self.assertFalse(r.is_sat)

    def test_single_variable_two_clauses(self) -> None:
        """[[1], [1]] → SAT with 1 = True."""
        r = self.solver.solve([[1], [1]])
        self.assertTrue(r.is_sat)
        self.assertTrue(r.assignment[1])

    # ------------------------------------------------------------------ #
    # Complete assignment guarantee
    # ------------------------------------------------------------------ #

    def test_complete_assignment_all_vars_present(self) -> None:
        """All variables in the formula must appear in the assignment."""
        clauses = [[1, 2, 3], [-1, 4], [-3, -4]]
        r = self.solver.solve(clauses)
        self.assertTrue(r.is_sat)
        for var in [1, 2, 3, 4]:
            self.assertIn(var, r.assignment,
                          f"Variable {var} missing from assignment")

    def test_complete_assignment_pure_literal(self) -> None:
        """Var 3 only appears positively – should still be in assignment."""
        clauses = [[1, 2], [-1, 3]]
        r = self.solver.solve(clauses)
        self.assertTrue(r.is_sat)
        for var in [1, 2, 3]:
            self.assertIn(var, r.assignment)

    # ------------------------------------------------------------------ #
    # Metrics sanity
    # ------------------------------------------------------------------ #

    def test_metrics_populated(self) -> None:
        """Metrics object should have non-negative values."""
        r = self.solver.solve([[1, 2], [-1, 3], [-2, -3]])
        m = r.metrics
        self.assertGreaterEqual(m.decisions, 0)
        self.assertGreaterEqual(m.propagations, 0)
        self.assertGreaterEqual(m.backtracks, 0)
        self.assertGreater(m.runtime_ms, 0)

    def test_unit_propagation_metrics(self) -> None:
        """Pure unit-clause formulas should have propagations, no decisions."""
        r = self.solver.solve([[1], [2], [3]])
        self.assertGreaterEqual(r.metrics.propagations, 3)
        # No branching needed, so zero decisions.
        self.assertEqual(r.metrics.decisions, 0)
        self.assertEqual(r.metrics.backtracks, 0)

    def test_backtrack_counted(self) -> None:
        """Contradicting formula must register at least one backtrack."""
        r = self.solver.solve([[1], [-1]])
        # The solver first propagates 1=T, then finds conflict with [-1].
        self.assertFalse(r.is_sat)

    # ------------------------------------------------------------------ #
    # Larger formulas
    # ------------------------------------------------------------------ #

    def test_five_variable_sat(self) -> None:
        """Moderate formula with 5 variables."""
        clauses = [
            [1, 2], [-1, 3], [-2, 4], [-3, 5],
            [-4, -5], [1, -3, 5], [-2, 3, -4],
        ]
        r = self.solver.solve(clauses)
        self.assertTrue(r.is_sat)
        self._verify_model(r, clauses)
        for var in range(1, 6):
            self.assertIn(var, r.assignment)

    def test_ten_variable_chain(self) -> None:
        """Implication chain: 1→2→…→10 with unit [1]."""
        clauses = [[1]]  # force 1 = True
        for i in range(1, 10):
            clauses.append([-i, i + 1])  # i → i+1
        r = self.solver.solve(clauses)
        self.assertTrue(r.is_sat)
        # All variables should be True via unit propagation.
        for var in range(1, 11):
            self.assertIn(var, r.assignment)
            self.assertTrue(r.assignment[var],
                            f"Variable {var} should be True in chain")

    # ------------------------------------------------------------------ #
    # Helper
    # ------------------------------------------------------------------ #

    def _verify_model(self, r: DPLLResult, clauses) -> None:
        """Assert that r.assignment satisfies every clause."""
        self.assertIsNotNone(r.assignment)
        for clause in clauses:
            satisfied = any(
                (r.assignment.get(abs(lit), False) if lit > 0
                 else not r.assignment.get(abs(lit), False))
                for lit in clause
            )
            self.assertTrue(satisfied,
                            f"Clause {clause} not satisfied by {r.assignment}")


if __name__ == "__main__":
    unittest.main()
