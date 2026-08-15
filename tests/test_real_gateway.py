"""Integration tests for GUI -> gateway -> engine -> SAT agent."""

from pathlib import Path
import unittest

from gui.models import ActionCode, GamePhase, GameGateway, Status
from gui.real_gateway import RealGameGateway


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PUZZLES = PROJECT_ROOT / "puzzles"


class TestRealGameGateway(unittest.TestCase):
    def setUp(self) -> None:
        self.gateway = RealGameGateway(PUZZLES / "level_01_3x3.json")

    def test_implements_gui_contract(self) -> None:
        self.assertIsInstance(self.gateway, GameGateway)

    def test_builtin_catalog_lists_seven_levels(self) -> None:
        options = self.gateway.list_puzzles()
        self.assertEqual(len(options), 7)
        self.assertEqual(
            [option.size for option in options],
            [3, 3, 3, 4, 4, 4, 5],
        )
        self.assertTrue(all(option.path.exists() for option in options))

    def test_public_state_never_contains_unrevealed_content(self) -> None:
        state = self.gateway.get_public_state()
        self.assertEqual(state.solved_count, 2)
        for cell in state.cells:
            if cell.revealed:
                self.assertIn(cell.status, (Status.CRIMINAL, Status.INNOCENT))
                self.assertIsNotNone(cell.clue_text)
            else:
                self.assertEqual(cell.status, Status.UNKNOWN)
                self.assertIsNone(cell.clue_id)
                self.assertIsNone(cell.clue_text)
                self.assertEqual(cell.clue_references, ())

    def test_manual_verdict_uses_entailment(self) -> None:
        before = self.gateway.get_public_state()

        not_provable = self.gateway.submit_verdict("C3", Status.INNOCENT)
        self.assertEqual(not_provable.code, ActionCode.NOT_PROVABLE)
        self.assertEqual(self.gateway.get_public_state().solved_count, before.solved_count)

        contradicted = self.gateway.submit_verdict("B1", Status.CRIMINAL)
        self.assertEqual(contradicted.code, ActionCode.CONTRADICTED)
        self.assertEqual(self.gateway.get_public_state().solved_count, before.solved_count)

        accepted = self.gateway.submit_verdict("B1", Status.INNOCENT)
        self.assertEqual(accepted.code, ActionCode.ACCEPTED)
        after = self.gateway.get_public_state()
        self.assertEqual(after.solved_count, before.solved_count + 1)
        revealed = next(cell for cell in after.cells if cell.cell_id == "B1")
        self.assertTrue(revealed.revealed)
        self.assertIsNotNone(revealed.clue_text)

    def test_hint_does_not_reveal_status(self) -> None:
        hint = self.gateway.get_hint()
        self.assertIn("B1", hint.target_cells)
        b1 = next(
            cell for cell in self.gateway.get_public_state().cells
            if cell.cell_id == "B1"
        )
        self.assertEqual(b1.status, Status.UNKNOWN)
        self.assertFalse(b1.revealed)

    def test_auto_solve_completes_real_puzzle(self) -> None:
        while self.gateway.get_public_state().phase is GamePhase.ACTIVE:
            result = self.gateway.auto_solve_step()
            self.assertIn(result.code, (ActionCode.ACCEPTED, ActionCode.SOLVED))
        state = self.gateway.get_public_state()
        self.assertEqual(state.phase, GamePhase.SOLVED)
        self.assertEqual(state.solved_count, state.total_count)
        self.assertGreater(state.metrics.sat_calls, 0)
        self.assertEqual(len(state.trace), state.step + 1)

    def test_restart_restores_initial_public_state(self) -> None:
        self.gateway.auto_solve_step()
        result = self.gateway.restart()
        self.assertEqual(result.code, ActionCode.INFO)
        state = self.gateway.get_public_state()
        self.assertEqual(state.step, 0)
        self.assertEqual(state.solved_count, 2)
        self.assertEqual(state.metrics.sat_calls, 0)

    def test_load_all_official_sizes(self) -> None:
        expected = {
            "level_01_3x3.json": 3,
            "level_04_4x4.json": 4,
            "level_07_5x5.json": 5,
        }
        for filename, size in expected.items():
            with self.subTest(filename=filename):
                result = self.gateway.load_puzzle(PUZZLES / filename)
                self.assertEqual(result.code, ActionCode.INFO)
                self.assertEqual(self.gateway.get_public_state().size, size)

    def test_invalid_load_leaves_current_puzzle_unchanged(self) -> None:
        before = self.gateway.get_public_state().puzzle_name
        result = self.gateway.load_puzzle(PUZZLES / "gui_demo_3x3.json")
        self.assertEqual(result.code, ActionCode.ERROR)
        self.assertEqual(self.gateway.get_public_state().puzzle_name, before)


if __name__ == "__main__":
    unittest.main()
