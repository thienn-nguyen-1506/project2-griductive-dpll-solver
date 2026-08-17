"""Tests for the reproducible progressive experiment runner."""

from pathlib import Path
import unittest

from core.puzzle import load_puzzle
from experiments import benchmark_file, run_benchmark


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PUZZLES = PROJECT_ROOT / "puzzles"


class TestExperiments(unittest.TestCase):
    def test_benchmark_runs_the_complete_progressive_loop(self) -> None:
        puzzle = load_puzzle(PUZZLES / "level_01_3x3.json")
        result = run_benchmark(
            puzzle,
            puzzle_file="level_01_3x3.json",
            runs=2,
            timeout_seconds=2.0,
        )

        self.assertEqual(result.status, "OK")
        self.assertEqual(result.runs_completed, 2)
        self.assertGreater(result.initial_clauses, 0)
        self.assertGreater(result.full_clauses, result.initial_clauses)
        self.assertEqual(result.deduction_steps, 7)
        self.assertEqual(result.forced_count, 7)
        self.assertEqual(result.unknown_count, 0)
        self.assertGreater(result.sat_calls, result.deduction_steps)
        self.assertTrue(result.is_consistent)
        self.assertTrue(result.is_unique)

    def test_load_failure_is_preserved_as_a_result_row(self) -> None:
        result = benchmark_file(
            PUZZLES / "missing_level.json",
            runs=1,
            timeout_seconds=1.0,
        )
        self.assertEqual(result.status, "FAILED")
        self.assertIn("ValueError", result.error)

    def test_timeout_is_reported_instead_of_dropped(self) -> None:
        puzzle = load_puzzle(PUZZLES / "level_01_3x3.json")
        result = run_benchmark(
            puzzle,
            runs=1,
            timeout_seconds=1e-12,
        )
        self.assertEqual(result.status, "TIMEOUT")
        self.assertIn("exceeded", result.error)


if __name__ == "__main__":
    unittest.main()
