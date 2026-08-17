"""Public-state-only demo gateway used to design and test the GUI.

This module deliberately does not implement CNF, DPLL, or logical deduction.
It simulates their public responses so the GUI can be completed independently.
Replace ``MockGameGateway`` with a real adapter during team integration.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from .models import (
    ActionCode,
    ActionResult,
    CellView,
    GamePhase,
    GameView,
    HintResult,
    PuzzleOption,
    SolverMetrics,
    Status,
    TraceEntry,
)


CHARACTERS = (
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
    ("Quinn", "Designer"),
    ("Rosa", "Scientist"),
    ("Sam", "Journalist"),
    ("Tara", "Musician"),
    ("Uma", "Architect"),
    ("Victor", "Mechanic"),
    ("Wendy", "Pharmacist"),
    ("Xavier", "Photographer"),
    ("Yara", "Librarian"),
)


class MockGameGateway:
    """Predictable demo behavior for exercising all important UI states."""

    MIN_SIZE = 3
    MAX_SIZE = 5

    def __init__(self, size: int = 4) -> None:
        self._size = size
        self._puzzle_name = f"GUI Demo {size}x{size}"
        self._cells: list[CellView] = []
        self._solution: dict[str, Status] = {}
        self._solve_order: list[str] = []
        self._initial_revealed: tuple[str, ...] = ()
        self._step = 0
        self._phase = GamePhase.READY
        self._trace: list[TraceEntry] = []
        self._metrics = SolverMetrics()
        self._configure_demo(size, self._puzzle_name)

    def _configure_demo(self, size: int, puzzle_name: str) -> None:
        if not self.MIN_SIZE <= size <= self.MAX_SIZE:
            raise ValueError("GUI demo size must be between 3 and 5.")

        self._size = size
        self._puzzle_name = puzzle_name
        ids = [
            f"{chr(ord('A') + column)}{row + 1}"
            for row in range(size)
            for column in range(size)
        ]
        self._solution = {
            cell_id: (
                Status.CRIMINAL
                if (index * 2 + index // size) % 5 in (1, 3)
                else Status.INNOCENT
            )
            for index, cell_id in enumerate(ids)
        }

        candidates = (
            "A1",
            f"{chr(ord('A') + size - 1)}1",
            f"{chr(ord('A') + size // 2)}{size // 2 + 1}",
            f"A{size}",
        )
        self._initial_revealed = tuple(dict.fromkeys(candidates))
        self._solve_order = [cell_id for cell_id in ids if cell_id not in self._initial_revealed]
        self._cells = []

        for index, cell_id in enumerate(ids):
            name, profession = CHARACTERS[index]
            cell = CellView(cell_id=cell_id, name=name, profession=profession)
            if cell_id in self._initial_revealed:
                clue, references = self._clue_for(cell_id)
                cell = replace(
                    cell,
                    revealed=True,
                    status=self._solution[cell_id],
                    clue_id=f"CLUE-{cell_id}",
                    clue_text=clue,
                    clue_references=references,
                )
            self._cells.append(cell)

        self._step = 0
        self._phase = GamePhase.ACTIVE
        self._metrics = SolverMetrics()
        self._trace = [
            TraceEntry(
                step=0,
                message=f"Loaded {len(self._initial_revealed)} initial public clues.",
                active_clue_ids=tuple(f"CLUE-{cell_id}" for cell_id in self._initial_revealed),
            )
        ]

    def _coordinates(self, cell_id: str) -> tuple[int, int]:
        return int(cell_id[1:]) - 1, ord(cell_id[0]) - ord("A")

    def _neighbors(self, cell_id: str) -> tuple[str, ...]:
        row, column = self._coordinates(cell_id)
        result: list[str] = []
        for row_offset in (-1, 0, 1):
            for column_offset in (-1, 0, 1):
                if row_offset == 0 and column_offset == 0:
                    continue
                next_row = row + row_offset
                next_column = column + column_offset
                if 0 <= next_row < self._size and 0 <= next_column < self._size:
                    result.append(
                        f"{chr(ord('A') + next_column)}{next_row + 1}"
                    )
        return tuple(result)

    def _clue_for(self, cell_id: str) -> tuple[str, tuple[str, ...]]:
        references = self._neighbors(cell_id)
        count = sum(
            self._solution[other] is Status.CRIMINAL for other in references
        )
        return (
            f"Exactly {count} Criminal(s) are among the neighbors of {cell_id}.",
            references,
        )

    def _find_cell_index(self, cell_id: str) -> int | None:
        return next(
            (index for index, cell in enumerate(self._cells) if cell.cell_id == cell_id),
            None,
        )

    def _next_forced_cell(self) -> str | None:
        return self._solve_order[0] if self._solve_order else None

    def _simulate_solver_call(self, contradicted: bool = False) -> None:
        self._metrics = replace(
            self._metrics,
            sat_calls=self._metrics.sat_calls + 2,
            decisions=self._metrics.decisions + 1,
            propagations=self._metrics.propagations + (3 if contradicted else 5),
            backtracks=self._metrics.backtracks + int(contradicted),
            runtime_ms=self._metrics.runtime_ms + (0.8 if contradicted else 1.2),
        )

    def get_public_state(self) -> GameView:
        return GameView(
            size=self._size,
            puzzle_name=self._puzzle_name,
            step=self._step,
            cells=tuple(self._cells),
            phase=self._phase,
            trace=tuple(self._trace),
            metrics=self._metrics,
        )

    def list_puzzles(self) -> tuple[PuzzleOption, ...]:
        project_root = Path(__file__).resolve().parents[1]
        return tuple(
            PuzzleOption(
                puzzle_id=f"gui_demo_{size}x{size}",
                name=f"GUI Demo {size}x{size}",
                size=size,
                path=project_root / "puzzles" / f"gui_demo_{size}x{size}.json",
            )
            for size in range(self.MIN_SIZE, self.MAX_SIZE + 1)
        )

    def submit_verdict(self, cell_id: str, status: Status) -> ActionResult:
        cell_index = self._find_cell_index(cell_id)
        if cell_index is None:
            return ActionResult(ActionCode.ERROR, f"Cell {cell_id} does not exist.")
        if status is Status.UNKNOWN:
            return ActionResult(
                ActionCode.ERROR,
                "UNKNOWN is an agent result, not a verdict that can be submitted.",
                cell_id,
            )

        cell = self._cells[cell_index]
        if cell.revealed:
            return ActionResult(
                ActionCode.INFO,
                f"{cell_id} is already revealed as {cell.status.value}.",
                cell_id,
            )

        forced_cell = self._next_forced_cell()
        if forced_cell != cell_id:
            self._simulate_solver_call()
            return ActionResult(
                ActionCode.NOT_PROVABLE,
                f"{cell_id}: the current KB entails neither CRIMINAL nor INNOCENT.",
                cell_id,
            )

        forced_status = self._solution[cell_id]
        if status is not forced_status:
            self._simulate_solver_call(contradicted=True)
            return ActionResult(
                ActionCode.CONTRADICTED,
                f"{cell_id}: the KB entails {forced_status.value}, so "
                f"{status.value} is contradicted.",
                cell_id,
            )

        self._simulate_solver_call()
        clue, references = self._clue_for(cell_id)
        clue_id = f"CLUE-{cell_id}"
        self._cells[cell_index] = replace(
            cell,
            revealed=True,
            status=forced_status,
            clue_id=clue_id,
            clue_text=clue,
            clue_references=references,
        )
        self._solve_order.pop(0)
        self._step += 1
        self._phase = GamePhase.SOLVED if not self._solve_order else GamePhase.ACTIVE
        self._trace.append(
            TraceEntry(
                step=self._step,
                message=f"{cell_id} was proved {forced_status.value}; its clue joined the KB.",
                active_clue_ids=(clue_id,),
                sat_queries=(f"SAT(KB and {cell_id})", f"SAT(KB and not {cell_id})"),
                verdict=f"{cell_id} = {forced_status.value}",
                revealed_clue_id=clue_id,
                revealed_clue_type="MOCK",
                revealed_clue_text=clue,
                revealed_clue_references=references,
            )
        )

        code = ActionCode.SOLVED if self._phase is GamePhase.SOLVED else ActionCode.ACCEPTED
        message = (
            "All characters have been solved."
            if code is ActionCode.SOLVED
            else f"{cell_id}: verdict accepted. A new clue was revealed."
        )
        return ActionResult(
            code,
            message,
            cell_id,
            revealed_clue=clue,
            highlighted_cells=references,
        )

    def get_hint(self) -> HintResult:
        target = self._next_forced_cell()
        if target is None:
            return HintResult("The puzzle is already solved.")

        clue_source = next(
            (
                cell.cell_id
                for cell in self._cells
                if cell.revealed and target in cell.clue_references
            ),
            next((cell.cell_id for cell in self._cells if cell.revealed), None),
        )
        targets = tuple(dict.fromkeys((clue_source, target))) if clue_source else (target,)
        return HintResult(
            f"Review clue {clue_source}; {target} can be proved next."
            if clue_source
            else f"A forced verdict is available for {target}.",
            clue_source=clue_source,
            target_cells=targets,
        )

    def auto_solve_step(self) -> ActionResult:
        target = self._next_forced_cell()
        if target is None:
            if all(cell.revealed for cell in self._cells):
                self._phase = GamePhase.SOLVED
                return ActionResult(ActionCode.SOLVED, "All characters are solved.")
            self._phase = GamePhase.STUCK
            return ActionResult(
                ActionCode.UNKNOWN,
                "No unsolved character is logically forced by the current KB.",
            )
        return self.submit_verdict(target, self._solution[target])

    def restart(self) -> ActionResult:
        self._configure_demo(self._size, self._puzzle_name)
        return ActionResult(ActionCode.INFO, "Puzzle restarted from its initial clues.")

    def load_puzzle(self, path: Path) -> ActionResult:
        """Load a tiny GUI-demo configuration, not the final project format.

        Expected JSON keys are ``name`` and ``size``. The real engine adapter is
        responsible for parsing the team's official puzzle representation.
        """

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            size = int(data["size"])
            name = str(data.get("name") or f"GUI Demo {size}x{size}")
            self._configure_demo(size, name)
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as error:
            return ActionResult(
                ActionCode.ERROR,
                f"Could not load {path.name}: {error}",
            )
        return ActionResult(
            ActionCode.INFO,
            f"Loaded {path.name}. This is mock data for testing the GUI.",
        )
