"""End-to-end checks for the official playable puzzle set."""

from collections import Counter
from pathlib import Path
import unittest

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
        self.assertEqual(len(puzzles), 8)
        self.assertEqual(Counter(puzzle.size for puzzle in puzzles), {3: 3, 4: 3, 5: 2})

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


if __name__ == "__main__":
    unittest.main()
