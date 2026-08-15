"""Unit tests for the Deductive Agent (core/agent.py).

Covers:
* KnowledgeBaseSnapshot construction.
* Consistency (INCONSISTENT detection).
* Entailment – forced CRIMINAL / INNOCENT / UNKNOWN.
* classify_all correctness.
* choose_next_forced row-major order.
* Uniqueness check.
* Structured trace correctness.
* AgentMetrics accumulation.
"""

import unittest

from core.agent import (
    ClassificationResult,
    DeductiveAgent,
    KnowledgeBaseSnapshot,
    SATQuery,
    TraceStep,
    _row_major_key,
)


# ---------------------------------------------------------------------------
# Helpers – tiny puzzle snapshots
# ---------------------------------------------------------------------------

def _make_snapshot(
    clauses,
    cell_ids=None,
    cell_to_var=None,
    known=None,
    clue_ids=None,
) -> KnowledgeBaseSnapshot:
    """Build a minimal KnowledgeBaseSnapshot for testing."""
    if cell_ids is None:
        cell_ids = ["A1"]
    if cell_to_var is None:
        cell_to_var = {cid: i + 1 for i, cid in enumerate(cell_ids)}
    primary = {f"C_{cid}": var for cid, var in cell_to_var.items()}
    return KnowledgeBaseSnapshot(
        clauses=clauses,
        primary_vars=primary,
        unresolved_cell_ids=cell_ids,
        cell_to_var=cell_to_var,
        active_clue_ids=clue_ids or ["clue0"],
        known_statuses=known or {},
    )


class TestRowMajorOrder(unittest.TestCase):
    """Verify the row-major sorting helper."""

    def test_basic_order(self) -> None:
        ids = ["B2", "A1", "C1", "A2", "B1", "C2"]
        ordered = sorted(ids, key=_row_major_key)
        # Row 1: A1 B1 C1, Row 2: A2 B2 C2
        self.assertEqual(ordered, ["A1", "B1", "C1", "A2", "B2", "C2"])

    def test_single_cell(self) -> None:
        self.assertEqual(sorted(["A1"], key=_row_major_key), ["A1"])


class TestConsistency(unittest.TestCase):
    """Test INCONSISTENT detection (KB_t is UNSAT)."""

    def setUp(self) -> None:
        self.agent = DeductiveAgent()

    def test_consistent_kb(self) -> None:
        snap = _make_snapshot([[1], [2]], cell_ids=["A1", "B1"])
        result = self.agent.classify_all(snap)
        self.assertTrue(result.is_consistent)

    def test_inconsistent_kb(self) -> None:
        # 1 ∧ ¬1 is UNSAT.
        snap = _make_snapshot([[1], [-1]], cell_ids=["A1"])
        result = self.agent.classify_all(snap)
        self.assertFalse(result.is_consistent)
        self.assertEqual(result.classifications, {})
        # Trace should contain the inconsistency message.
        self.assertEqual(len(result.trace), 1)
        self.assertIn("INCONSISTENT", result.trace[0].message)


class TestEntailment(unittest.TestCase):
    """Test individual cell entailment via 2 SAT queries."""

    def setUp(self) -> None:
        self.agent = DeductiveAgent()

    def test_forced_criminal(self) -> None:
        """Unit clause [1] forces variable 1 = True ⇒ A1 = CRIMINAL."""
        snap = _make_snapshot(
            clauses=[[1]],
            cell_ids=["A1"],
            cell_to_var={"A1": 1},
        )
        result = self.agent.classify_all(snap)
        self.assertTrue(result.is_consistent)
        self.assertEqual(result.classifications["A1"], "CRIMINAL")

    def test_forced_innocent(self) -> None:
        """Unit clause [-1] forces variable 1 = False ⇒ A1 = INNOCENT."""
        snap = _make_snapshot(
            clauses=[[-1]],
            cell_ids=["A1"],
            cell_to_var={"A1": 1},
        )
        result = self.agent.classify_all(snap)
        self.assertTrue(result.is_consistent)
        self.assertEqual(result.classifications["A1"], "INNOCENT")

    def test_unknown_status(self) -> None:
        """No forcing clause ⇒ status is UNKNOWN."""
        # (1 ∨ 2): both 1=T/2=F and 1=F/2=T are models.
        snap = _make_snapshot(
            clauses=[[1, 2]],
            cell_ids=["A1", "B1"],
            cell_to_var={"A1": 1, "B1": 2},
        )
        result = self.agent.classify_all(snap)
        self.assertTrue(result.is_consistent)
        # At least one should be UNKNOWN (both can be either).
        self.assertIn("UNKNOWN", result.classifications.values())

    def test_two_cells_one_forced(self) -> None:
        """A1 is forced CRIMINAL by [1]; B1 is free in [1, 2]."""
        snap = _make_snapshot(
            clauses=[[1], [1, 2]],
            cell_ids=["A1", "B1"],
            cell_to_var={"A1": 1, "B1": 2},
        )
        result = self.agent.classify_all(snap)
        self.assertEqual(result.classifications["A1"], "CRIMINAL")
        # B1 is not forced: [1] satisfies clause [1,2] regardless of 2.
        self.assertEqual(result.classifications["B1"], "UNKNOWN")


class TestClassifyAll(unittest.TestCase):
    """Test classify_all with multi-cell scenarios."""

    def setUp(self) -> None:
        self.agent = DeductiveAgent()

    def test_all_forced(self) -> None:
        """All cells forced by unit clauses."""
        snap = _make_snapshot(
            clauses=[[1], [-2], [3]],
            cell_ids=["A1", "B1", "C1"],
            cell_to_var={"A1": 1, "B1": 2, "C1": 3},
        )
        result = self.agent.classify_all(snap)
        self.assertEqual(result.classifications, {
            "A1": "CRIMINAL",
            "B1": "INNOCENT",
            "C1": "CRIMINAL",
        })

    def test_mixed_forced_unknown(self) -> None:
        """Some forced, some unknown."""
        # [1] forces A1=CRIMINAL.
        # (2 ∨ 3) leaves B1, C1 undetermined.
        snap = _make_snapshot(
            clauses=[[1], [2, 3]],
            cell_ids=["A1", "B1", "C1"],
            cell_to_var={"A1": 1, "B1": 2, "C1": 3},
        )
        result = self.agent.classify_all(snap)
        self.assertEqual(result.classifications["A1"], "CRIMINAL")
        self.assertEqual(result.classifications["B1"], "UNKNOWN")
        self.assertEqual(result.classifications["C1"], "UNKNOWN")


class TestChooseNextForced(unittest.TestCase):
    """Test choose_next_forced returns row-major first forced cell."""

    def test_first_forced_row_major(self) -> None:
        classifications = {
            "B2": "CRIMINAL",
            "A1": "UNKNOWN",
            "C1": "INNOCENT",
            "A2": "CRIMINAL",
        }
        result = DeductiveAgent.choose_next_forced(classifications)
        # Row-major: A1(UNKNOWN skip), C1(row1 INNOCENT), A2(row2 CRIMINAL),
        # B2(row2 CRIMINAL). First forced = C1.
        self.assertIsNotNone(result)
        self.assertEqual(result[0], "C1")
        self.assertEqual(result[1], "INNOCENT")

    def test_no_forced(self) -> None:
        classifications = {"A1": "UNKNOWN", "B1": "UNKNOWN"}
        result = DeductiveAgent.choose_next_forced(classifications)
        self.assertIsNone(result)

    def test_single_forced(self) -> None:
        classifications = {"A1": "CRIMINAL"}
        result = DeductiveAgent.choose_next_forced(classifications)
        self.assertEqual(result, ("A1", "CRIMINAL"))


class TestUniqueness(unittest.TestCase):
    """Test uniqueness check."""

    def setUp(self) -> None:
        self.agent = DeductiveAgent()

    def test_unique_solution(self) -> None:
        """Unit clauses force a single model ⇒ unique."""
        snap = _make_snapshot(
            clauses=[[1], [-2]],
            cell_ids=["A1", "B1"],
            cell_to_var={"A1": 1, "B1": 2},
        )
        is_unique, metrics = self.agent.check_uniqueness(snap)
        self.assertTrue(is_unique)
        self.assertEqual(metrics.sat_calls, 2)  # find model + check blocking

    def test_non_unique_solution(self) -> None:
        """(1 ∨ 2) has multiple models ⇒ not unique."""
        snap = _make_snapshot(
            clauses=[[1, 2]],
            cell_ids=["A1", "B1"],
            cell_to_var={"A1": 1, "B1": 2},
        )
        is_unique, metrics = self.agent.check_uniqueness(snap)
        self.assertFalse(is_unique)

    def test_unsat_is_not_unique(self) -> None:
        """UNSAT formula has zero solutions, so it is not a unique puzzle."""
        snap = _make_snapshot(
            clauses=[[1], [-1]],
            cell_ids=["A1"],
            cell_to_var={"A1": 1},
        )
        is_unique, metrics = self.agent.check_uniqueness(snap)
        self.assertFalse(is_unique)


class TestTrace(unittest.TestCase):
    """Test structured deduction trace."""

    def setUp(self) -> None:
        self.agent = DeductiveAgent()

    def test_trace_entries_match_cells(self) -> None:
        """Each unresolved cell should have a trace entry."""
        snap = _make_snapshot(
            clauses=[[1], [-2]],
            cell_ids=["A1", "B1"],
            cell_to_var={"A1": 1, "B1": 2},
        )
        result = self.agent.classify_all(snap)
        # 2 cells → 2 trace steps.
        self.assertEqual(len(result.trace), 2)
        trace_cell_ids = [t.cell_id for t in result.trace]
        # Row-major: A1 then B1.
        self.assertEqual(trace_cell_ids, ["A1", "B1"])

    def test_trace_has_sat_queries(self) -> None:
        """Each trace step should contain structured SAT queries."""
        snap = _make_snapshot(
            clauses=[[1]],
            cell_ids=["A1"],
            cell_to_var={"A1": 1},
        )
        result = self.agent.classify_all(snap)
        step = result.trace[0]
        self.assertGreater(len(step.sat_queries), 0)
        q = step.sat_queries[0]
        self.assertIsInstance(q, SATQuery)
        self.assertEqual(q.cell_id, "A1")
        self.assertIn(q.result, ("SAT", "UNSAT"))

    def test_trace_step_numbering(self) -> None:
        snap = _make_snapshot(
            clauses=[[1], [-2], [3]],
            cell_ids=["A1", "B1", "C1"],
            cell_to_var={"A1": 1, "B1": 2, "C1": 3},
        )
        result = self.agent.classify_all(snap)
        steps = [t.step for t in result.trace]
        self.assertEqual(steps, [1, 2, 3])


class TestAgentMetrics(unittest.TestCase):
    """Test that AgentMetrics accumulates correctly."""

    def test_sat_calls_counted(self) -> None:
        agent = DeductiveAgent()
        snap = _make_snapshot(
            clauses=[[1], [-2]],
            cell_ids=["A1", "B1"],
            cell_to_var={"A1": 1, "B1": 2},
        )
        result = agent.classify_all(snap)
        # 1 consistency check + 2 cells × (1 or 2 queries each).
        # A1: forced CRIMINAL → 1 query (UNSAT on first).
        # B1: forced INNOCENT → 2 queries (SAT on first, UNSAT on second).
        # Total = 1 + 1 + 2 = 4.
        self.assertGreaterEqual(result.metrics.sat_calls, 3)
        self.assertGreater(result.metrics.total_runtime_ms, 0)


class TestDeduceOneStep(unittest.TestCase):
    """Test the deduce_one_step convenience method."""

    def test_returns_forced_cell(self) -> None:
        agent = DeductiveAgent()
        snap = _make_snapshot(
            clauses=[[1], [2, 3]],
            cell_ids=["A1", "B1", "C1"],
            cell_to_var={"A1": 1, "B1": 2, "C1": 3},
        )
        forced, result = agent.deduce_one_step(snap)
        self.assertIsNotNone(forced)
        self.assertEqual(forced[0], "A1")
        self.assertEqual(forced[1], "CRIMINAL")

    def test_returns_none_when_stuck(self) -> None:
        agent = DeductiveAgent()
        snap = _make_snapshot(
            clauses=[[1, 2]],
            cell_ids=["A1", "B1"],
            cell_to_var={"A1": 1, "B1": 2},
        )
        forced, result = agent.deduce_one_step(snap)
        self.assertIsNone(forced)
        self.assertTrue(result.is_consistent)

    def test_inconsistent_returns_none(self) -> None:
        agent = DeductiveAgent()
        snap = _make_snapshot(
            clauses=[[1], [-1]],
            cell_ids=["A1"],
            cell_to_var={"A1": 1},
        )
        forced, result = agent.deduce_one_step(snap)
        self.assertIsNone(forced)
        self.assertFalse(result.is_consistent)


if __name__ == "__main__":
    unittest.main()
