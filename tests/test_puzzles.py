"""End-to-end checks for the official playable puzzle set."""

from collections import Counter
from pathlib import Path
import unittest

from core.agent import DeductiveAgent
from core.engine import GameEngine
from core.puzzle import (
    CORE_CLUE_TYPES,
    EXTENSION_CLUE_TYPES,
    load_puzzle,
    validate_puzzle,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PUZZLE_FILES = sorted((PROJECT_ROOT / "puzzles").glob("level_*.json"))


class TestOfficialPuzzles(unittest.TestCase):
    def test_expected_level_mix(self) -> None:
        puzzles = [load_puzzle(path) for path in PUZZLE_FILES]
        self.assertEqual(len(puzzles), 6)
        self.assertEqual(
            Counter(puzzle.size for puzzle in puzzles),
            {3: 2, 4: 2, 5: 2},
        )

    def test_every_level_is_true_unique_and_no_guess(self) -> None:
        for path in PUZZLE_FILES:
            with self.subTest(path=path.name):
                puzzle = load_puzzle(path)
                report = validate_puzzle(puzzle)
                self.assertTrue(report.is_valid)
                self.assertTrue(report.is_unique)
                self.assertEqual(
                    len(report.deduction_order),
                    len(puzzle.cells) - len(puzzle.initial_revealed),
                )
                self.assertTrue(all(cell.clue.text for cell in puzzle.cells))

    def test_set_covers_core_and_extension_languages(self) -> None:
        clue_types = {
            cell.clue.type
            for path in PUZZLE_FILES
            for cell in load_puzzle(path).cells
        }
        self.assertTrue(CORE_CLUE_TYPES <= clue_types)
        self.assertTrue(EXTENSION_CLUE_TYPES <= clue_types)

    def test_set_uses_all_required_region_expressions(self) -> None:
        region_kinds = {
            cell.clue.region_kind or "EXPLICIT"
            for path in PUZZLE_FILES
            for cell in load_puzzle(path).cells
            if cell.clue.type in {"EXACTLY", "AT_LEAST", "AT_MOST", "PARITY"}
        }
        self.assertTrue(
            {"ROW", "COLUMN", "NEIGHBORS", "EXPLICIT"} <= region_kinds
        )

    def test_levels_have_non_linear_branching_deductions(self) -> None:
        """Difficulty guard: no level may collapse back to a straight chain."""
        agent = DeductiveAgent()
        for path in PUZZLE_FILES:
            with self.subTest(path=path.name):
                puzzle = load_puzzle(path)
                report = validate_puzzle(puzzle)
                row_major_index = {
                    cell_id: index
                    for index, cell_id in enumerate(puzzle.cell_ids)
                }
                reveal_indices = [
                    row_major_index[cell_id]
                    for cell_id in report.deduction_order
                ]
                self.assertNotEqual(reveal_indices, sorted(reveal_indices))

                engine = GameEngine(puzzle)
                saw_multiple_forced_choices = False
                while engine.phase == "ACTIVE":
                    classifications = agent.classify_all(
                        engine.get_kb_snapshot()
                    ).classifications
                    forced = [
                        status
                        for status in classifications.values()
                        if status in {"CRIMINAL", "INNOCENT"}
                    ]
                    saw_multiple_forced_choices |= len(forced) > 1
                    engine.auto_solve_step()
                self.assertTrue(saw_multiple_forced_choices)


if __name__ == "__main__":
    unittest.main()
