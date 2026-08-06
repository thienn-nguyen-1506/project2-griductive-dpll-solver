"""A public-state-only mock used to design and test the GUI.

Replace ``MockGameGateway`` with the real GameEngine adapter during integration.
The GUI should not need to change as long as the adapter implements GameGateway.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from .models import (
    ActionCode,
    ActionResult,
    CellView,
    GameView,
    HintResult,
    Status,
)


NAMES = (
    ("Abel", "Astronaut"),
    ("Bea", "Cook"),
    ("Clara", "Guard"),
    ("Derek", "Pilot"),
    ("Eliza", "Detective"),
    ("Franz", "Farmer"),
    ("Grant", "Clerk"),
    ("Hannah", "Doctor"),
    ("Ivy", "Artist"),
    ("Jonas", "Teacher"),
    ("Karl", "Chef"),
    ("Leo", "Guard"),
    ("Mara", "Nurse"),
    ("Noah", "Engineer"),
    ("Owen", "Painter"),
    ("Priya", "Lawyer"),
)


class MockGameGateway:
    """Predictable demo behavior for exercising all important UI states."""

    def __init__(self) -> None:
        self._initial_cells = self._make_initial_cells()
        self._forced = {
            "B2": Status.CRIMINAL,
            "A2": Status.INNOCENT,
            "D2": Status.CRIMINAL,
        }
        self._revealed_clues = {
            "B2": ("Exactly 2 Criminals are in row 2.", ("A2", "B2", "C2", "D2")),
            "A2": ("B1 and C1 have the same status.", ("B1", "C1")),
            "D2": ("At least 1 neighbor of D2 is Innocent.", ("C1", "C2", "C3", "D1", "D3")),
        }
        self._cells: list[CellView] = []
        self._step = 0
        self._trace: list[str] = []
        self.restart()

    @staticmethod
    def _make_initial_cells() -> tuple[CellView, ...]:
        cells: list[CellView] = []
        for index, (name, profession) in enumerate(NAMES):
            row = index // 4 + 1
            column = chr(ord("A") + index % 4)
            cells.append(CellView(f"{column}{row}", name, profession))

        public_clues = {
            "A1": (
                Status.INNOCENT,
                "Bea and Clara have the same status.",
                ("B1", "C1"),
            ),
            "D1": (
                Status.CRIMINAL,
                "Exactly 2 Criminals are in column D.",
                ("D1", "D2", "D3", "D4"),
            ),
            "C2": (
                Status.INNOCENT,
                "No Criminal is in a corner.",
                ("A1", "D1", "A4", "D4"),
            ),
            "D3": (
                Status.CRIMINAL,
                "A1 and B2 have different statuses.",
                ("A1", "B2"),
            ),
        }
        for index, cell in enumerate(cells):
            if cell.cell_id in public_clues:
                status, clue, references = public_clues[cell.cell_id]
                cells[index] = replace(
                    cell,
                    revealed=True,
                    status=status,
                    clue_text=clue,
                    clue_references=references,
                )
        return tuple(cells)

    def get_public_state(self) -> GameView:
        return GameView(
            size=4,
            puzzle_name="Demo 4×4 · Medium",
            step=self._step,
            cells=tuple(self._cells),
            trace=tuple(self._trace),
        )

    def submit_verdict(self, cell_id: str, status: Status) -> ActionResult:
        cell_index = next(
            (index for index, cell in enumerate(self._cells) if cell.cell_id == cell_id),
            None,
        )
        if cell_index is None:
            return ActionResult(ActionCode.INFO, f"Unknown cell: {cell_id}")

        cell = self._cells[cell_index]
        if cell.revealed:
            return ActionResult(
                ActionCode.INFO,
                f"{cell_id} is already revealed as {cell.status.value}.",
                cell_id,
            )

        forced_status = self._forced.get(cell_id)
        if forced_status is None:
            return ActionResult(
                ActionCode.NOT_PROVABLE,
                f"{cell_id}: neither status is forced by the current KB.",
                cell_id,
            )

        if status is not forced_status:
            return ActionResult(
                ActionCode.CONTRADICTED,
                f"{cell_id}: the opposite status is logically forced.",
                cell_id,
            )

        clue, references = self._revealed_clues[cell_id]
        self._cells[cell_index] = replace(
            cell,
            revealed=True,
            status=forced_status,
            clue_text=clue,
            clue_references=references,
        )
        self._step += 1
        self._trace.append(
            f"Step {self._step}: {cell_id} → {forced_status.value}; clue revealed."
        )
        self._forced.pop(cell_id, None)
        return ActionResult(
            ActionCode.ACCEPTED,
            f"{cell_id}: verdict accepted. A new clue was revealed.",
            cell_id,
            revealed_clue=clue,
            highlighted_cells=references,
        )

    def get_hint(self) -> HintResult:
        if "B2" in self._forced:
            return HintResult(
                "Review clue D3; B2 can be proved next.",
                clue_source="D3",
                target_cells=("D3", "A1", "B2"),
            )
        if self._forced:
            target = next(iter(self._forced))
            return HintResult(
                f"A forced verdict is available for {target}.",
                target_cells=(target,),
            )
        return HintResult("No more demo hints are available.")

    def auto_solve_step(self) -> ActionResult:
        if not self._forced:
            return ActionResult(ActionCode.INFO, "No forced demo verdict remains.")
        cell_id, status = next(iter(self._forced.items()))
        return self.submit_verdict(cell_id, status)

    def restart(self) -> ActionResult:
        self._cells = list(self._initial_cells)
        self._step = 0
        self._trace = ["Initial public clues loaded."]
        self._forced = {
            "B2": Status.CRIMINAL,
            "A2": Status.INNOCENT,
            "D2": Status.CRIMINAL,
        }
        return ActionResult(ActionCode.INFO, "Puzzle restarted.")

    def load_puzzle(self, path: Path) -> ActionResult:
        return ActionResult(
            ActionCode.INFO,
            f"Selected {path.name}. Connect this hook to the real puzzle loader.",
        )
