import json
import tempfile
import unittest
from pathlib import Path

from gui.mock_engine import MockGameGateway
from gui.models import ActionCode, GamePhase, GameGateway, Status


class MockGatewayTests(unittest.TestCase):
    def test_implements_gui_contract(self) -> None:
        self.assertIsInstance(MockGameGateway(), GameGateway)

    def test_hidden_information_never_enters_public_state(self) -> None:
        state = MockGameGateway().get_public_state()
        hidden = [cell for cell in state.cells if not cell.revealed]
        self.assertTrue(hidden)
        self.assertTrue(all(cell.status is Status.UNKNOWN for cell in hidden))
        self.assertTrue(all(cell.clue_text is None for cell in hidden))
        self.assertTrue(all(cell.clue_id is None for cell in hidden))

    def test_not_provable_leaves_logical_state_unchanged(self) -> None:
        gateway = MockGameGateway()
        before = gateway.get_public_state()
        forced_target = gateway.get_hint().target_cells[-1]
        other = next(
            cell.cell_id
            for cell in before.cells
            if not cell.revealed and cell.cell_id != forced_target
        )
        result = gateway.submit_verdict(other, Status.CRIMINAL)
        after = gateway.get_public_state()
        self.assertEqual(ActionCode.NOT_PROVABLE, result.code)
        self.assertEqual(before.step, after.step)
        self.assertEqual(before.cells, after.cells)

    def test_opposite_verdict_is_contradicted(self) -> None:
        first = MockGameGateway()
        second = MockGameGateway()
        target = first.get_hint().target_cells[-1]
        criminal_result = first.submit_verdict(target, Status.CRIMINAL)
        innocent_result = second.submit_verdict(target, Status.INNOCENT)
        self.assertEqual(
            {ActionCode.ACCEPTED, ActionCode.CONTRADICTED},
            {criminal_result.code, innocent_result.code},
        )

    def test_auto_solve_can_complete_demo(self) -> None:
        gateway = MockGameGateway()
        while gateway.get_public_state().phase is GamePhase.ACTIVE:
            last_result = gateway.auto_solve_step()
        state = gateway.get_public_state()
        self.assertEqual(ActionCode.SOLVED, last_result.code)
        self.assertEqual(GamePhase.SOLVED, state.phase)
        self.assertEqual(state.total_count, state.solved_count)

    def test_mock_loader_changes_board_size(self) -> None:
        gateway = MockGameGateway()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "demo.json"
            path.write_text(json.dumps({"name": "Test 3x3", "size": 3}))
            result = gateway.load_puzzle(path)
        self.assertEqual(ActionCode.INFO, result.code)
        self.assertEqual(3, gateway.get_public_state().size)


if __name__ == "__main__":
    unittest.main()
