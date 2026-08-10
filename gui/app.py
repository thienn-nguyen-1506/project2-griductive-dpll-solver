"""CustomTkinter presentation layer for Griductive."""

from __future__ import annotations

from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Callable

import customtkinter as ctk

from . import theme
from .mock_engine import MockGameGateway
from .models import (
    ActionCode,
    ActionResult,
    CellView,
    GameGateway,
    GamePhase,
    GameView,
    Status,
    TraceEntry,
)


ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")


STATUS_PRESENTATION = {
    Status.CRIMINAL: ("!  CRIMINAL", theme.CRIMINAL, theme.CRIMINAL_SOFT),
    Status.INNOCENT: ("✓  INNOCENT", theme.INNOCENT, theme.INNOCENT_SOFT),
}
UNSOLVED_PRESENTATION = ("○  UNSOLVED", theme.TEXT_SECONDARY, theme.PANEL_SOFT)

PHASE_PRESENTATION = {
    GamePhase.READY: ("READY", theme.TEXT_SECONDARY, theme.PANEL_SOFT),
    GamePhase.ACTIVE: ("ACTIVE", theme.PRIMARY, theme.PRIMARY_SOFT),
    GamePhase.SOLVED: ("SOLVED", theme.SUCCESS, theme.INNOCENT_SOFT),
    GamePhase.STUCK: ("STUCK", theme.WARNING, theme.WARNING_SOFT),
    GamePhase.INCONSISTENT: ("INCONSISTENT", theme.ERROR, theme.CRIMINAL_SOFT),
}


class CharacterCard(ctk.CTkFrame):
    """One public card. It never receives a hidden solution from the engine."""

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        cell: CellView,
        on_select: Callable[[str], None],
        on_clue_select: Callable[[str], None],
    ) -> None:
        # Keep the border width constant. Changing it when a card is selected
        # changes the widget's requested size and makes Tk recalculate the
        # complete grid, which looks like the neighboring cards are jumping.
        super().__init__(master, corner_radius=14, border_width=3)
        self.cell = cell
        self.on_select = on_select
        self.on_clue_select = on_clue_select
        self._base_surface = theme.PANEL_BACKGROUND
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.card_button = ctk.CTkButton(
            self,
            text="",
            command=lambda: self.on_select(self.cell.cell_id),
            fg_color="transparent",
            hover_color=theme.PANEL_SOFT,
            anchor="w",
            corner_radius=10,
            height=82,
            font=ctk.CTkFont(size=12),
        )
        self.card_button.grid(row=0, column=0, padx=5, pady=(5, 2), sticky="nsew")

        self.clue_button = ctk.CTkButton(
            self,
            text="",
            command=lambda: self.on_clue_select(self.cell.cell_id),
            fg_color="transparent",
            hover_color=theme.PANEL_SOFT,
            text_color=theme.TEXT_SECONDARY,
            anchor="w",
            corner_radius=8,
            height=28,
            font=ctk.CTkFont(size=10),
        )
        self.clue_button.grid(row=1, column=0, padx=5, pady=(0, 5), sticky="ew")

    def update_view(
        self,
        cell: CellView,
        *,
        selected: bool,
        highlighted: bool,
    ) -> None:
        self.cell = cell
        if cell.revealed:
            status_text, status_color, surface = STATUS_PRESENTATION[cell.status]
            clue_preview = cell.clue_text or "Revealed clue"
            # Keep previews compact so newly revealed text cannot change a
            # column's requested width. The complete clue remains available
            # in the detail panel.
            if len(clue_preview) > 18:
                clue_preview = clue_preview[:15] + "..."
            self.clue_button.configure(
                text=f"Clue · {clue_preview}",
                state="normal",
                text_color=status_color,
            )
        else:
            status_text, status_color, surface = UNSOLVED_PRESENTATION
            self.clue_button.configure(
                text="Face-down clue",
                state="disabled",
                text_color=theme.TEXT_SECONDARY,
            )

        self.card_button.configure(
            text=f"{cell.cell_id}\n{cell.name}\n{cell.profession}\n{status_text}",
            text_color=theme.TEXT_PRIMARY,
        )

        self._base_surface = surface
        self.update_style(selected=selected, highlighted=highlighted)

    def update_style(self, *, selected: bool, highlighted: bool) -> None:
        """Update selection/highlight colors without touching card content."""

        surface = self._base_surface
        border_color = theme.BORDER
        if highlighted:
            surface = theme.HIGHLIGHT_SOFT
            border_color = theme.HIGHLIGHT
        if selected:
            border_color = theme.PRIMARY

        self.configure(
            fg_color=surface,
            border_color=border_color,
            border_width=3,
        )


class GriductiveApp(ctk.CTk):
    """GUI shell that can run with either the mock or a real gateway adapter."""

    AUTO_DELAY_MS = 450

    def __init__(self, gateway: GameGateway | None = None) -> None:
        super().__init__(fg_color=theme.APP_BACKGROUND)
        self.gateway = gateway or MockGameGateway()
        self.game_view: GameView = self.gateway.get_public_state()
        self.selected_cell_id: str | None = None
        self.highlighted_cells: set[str] = set()
        self.cards: dict[str, CharacterCard] = {}
        self.clue_menu_lookup: dict[str, str] = {}
        self.auto_running = False
        self.auto_after_id: str | None = None

        self.title("Griductive Solver")
        self.geometry("1320x860")
        self.minsize(1040, 720)
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._build_header()
        self._build_content()
        self._build_footer()
        self._bind_shortcuts()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._refresh_all()

    def _build_header(self) -> None:
        header = ctk.CTkFrame(
            self,
            fg_color=theme.PANEL_BACKGROUND,
            corner_radius=0,
            border_width=0,
        )
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(1, weight=1)

        logo = ctk.CTkLabel(
            header,
            text="G",
            width=42,
            height=42,
            corner_radius=12,
            fg_color=theme.PRIMARY,
            text_color=theme.PRIMARY_TEXT,
            font=ctk.CTkFont(size=21, weight="bold"),
        )
        logo.grid(row=0, column=0, padx=(18, 10), pady=14)

        title_frame = ctk.CTkFrame(header, fg_color="transparent")
        title_frame.grid(row=0, column=1, sticky="w")
        ctk.CTkLabel(
            title_frame,
            text="Griductive Solver",
            text_color=theme.TEXT_PRIMARY,
            font=ctk.CTkFont(size=19, weight="bold"),
        ).pack(anchor="w")
        self.puzzle_label = ctk.CTkLabel(
            title_frame,
            text="",
            text_color=theme.TEXT_SECONDARY,
            font=ctk.CTkFont(size=12),
        )
        self.puzzle_label.pack(anchor="w")

        controls = ctk.CTkFrame(header, fg_color="transparent")
        controls.grid(row=0, column=2, padx=18, pady=14, sticky="e")
        self.appearance_menu = ctk.CTkOptionMenu(
            controls,
            values=["System", "Light", "Dark"],
            command=ctk.set_appearance_mode,
            width=100,
            fg_color=theme.PANEL_SOFT,
            button_color=theme.PRIMARY,
            text_color=theme.TEXT_PRIMARY,
        )
        self.appearance_menu.set("System")
        self.appearance_menu.pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            controls,
            text="Load JSON",
            width=94,
            fg_color=theme.PANEL_SOFT,
            hover_color=theme.BORDER,
            text_color=theme.TEXT_PRIMARY,
            command=self._load_puzzle,
        ).pack(side="left", padx=4)
        ctk.CTkButton(
            controls,
            text="Restart",
            width=84,
            fg_color=theme.PANEL_SOFT,
            hover_color=theme.BORDER,
            text_color=theme.TEXT_PRIMARY,
            command=self._restart,
        ).pack(side="left", padx=4)

    def _build_content(self) -> None:
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.grid(row=1, column=0, padx=18, pady=18, sticky="nsew")
        content.grid_rowconfigure(0, weight=1)
        content.grid_columnconfigure(0, weight=3)
        content.grid_columnconfigure(1, weight=1, minsize=330)

        self.board_panel = ctk.CTkFrame(
            content,
            fg_color=theme.PANEL_BACKGROUND,
            corner_radius=16,
            border_width=1,
            border_color=theme.BORDER,
        )
        self.board_panel.grid(row=0, column=0, padx=(0, 12), sticky="nsew")
        self.board_panel.grid_rowconfigure(1, weight=1)
        self.board_panel.grid_columnconfigure(0, weight=1)

        board_head = ctk.CTkFrame(self.board_panel, fg_color="transparent")
        board_head.grid(row=0, column=0, padx=16, pady=(14, 8), sticky="ew")
        board_head.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            board_head,
            text="Public Board",
            text_color=theme.TEXT_PRIMARY,
            font=ctk.CTkFont(size=16, weight="bold"),
        ).grid(row=0, column=0, sticky="w")
        self.phase_label = ctk.CTkLabel(
            board_head,
            text="",
            corner_radius=10,
            width=92,
            height=26,
            font=ctk.CTkFont(size=11, weight="bold"),
        )
        self.phase_label.grid(row=0, column=1, padx=(8, 6), sticky="e")
        self.progress_label = ctk.CTkLabel(
            board_head,
            text="",
            fg_color=theme.PANEL_SOFT,
            text_color=theme.TEXT_SECONDARY,
            corner_radius=10,
            width=178,
            height=26,
        )
        self.progress_label.grid(row=0, column=2, sticky="e")
        self.progress_bar = ctk.CTkProgressBar(
            board_head,
            height=7,
            fg_color=theme.PANEL_SOFT,
            progress_color=theme.PRIMARY,
        )
        self.progress_bar.grid(row=1, column=0, columnspan=3, pady=(10, 0), sticky="ew")

        self.board = ctk.CTkFrame(self.board_panel, fg_color="transparent")
        self.board.grid(row=1, column=0, padx=14, pady=(0, 14), sticky="nsew")

        self.sidebar = ctk.CTkScrollableFrame(
            content,
            fg_color="transparent",
            scrollbar_button_color=theme.BORDER,
        )
        self.sidebar.grid(row=0, column=1, sticky="nsew")
        self.sidebar.grid_columnconfigure(0, weight=1)
        self._build_sidebar()

    def _panel(self, row: int, title: str) -> ctk.CTkFrame:
        panel = ctk.CTkFrame(
            self.sidebar,
            fg_color=theme.PANEL_BACKGROUND,
            corner_radius=14,
            border_width=1,
            border_color=theme.BORDER,
        )
        panel.grid(row=row, column=0, pady=(0, 10), sticky="ew")
        panel.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            panel,
            text=title,
            text_color=theme.TEXT_PRIMARY,
            font=ctk.CTkFont(size=14, weight="bold"),
        ).grid(row=0, column=0, padx=14, pady=(12, 6), sticky="w")
        return panel

    def _build_sidebar(self) -> None:
        detail = self._panel(0, "Selected character")
        self.selected_title = ctk.CTkLabel(
            detail,
            text="Select a card",
            text_color=theme.TEXT_PRIMARY,
            font=ctk.CTkFont(size=17, weight="bold"),
        )
        self.selected_title.grid(row=1, column=0, padx=14, sticky="w")
        self.selected_meta = ctk.CTkLabel(detail, text="", text_color=theme.TEXT_SECONDARY)
        self.selected_meta.grid(row=2, column=0, padx=14, pady=(2, 6), sticky="w")
        self.selected_status = ctk.CTkLabel(
            detail,
            text=UNSOLVED_PRESENTATION[0],
            fg_color=theme.PANEL_SOFT,
            text_color=theme.TEXT_SECONDARY,
            corner_radius=10,
            width=126,
            height=30,
        )
        self.selected_status.grid(row=3, column=0, padx=14, pady=(0, 8), sticky="w")
        self.clue_text = ctk.CTkTextbox(
            detail,
            height=78,
            wrap="word",
            fg_color=theme.PANEL_SOFT,
            border_width=0,
            text_color=theme.TEXT_PRIMARY,
        )
        self.clue_text.grid(row=4, column=0, padx=14, pady=(0, 14), sticky="ew")
        self.clue_text.configure(state="disabled")

        verdict = self._panel(1, "Submit verdict")
        ctk.CTkLabel(
            verdict,
            text="Only submit when the current KB proves a status.",
            text_color=theme.TEXT_SECONDARY,
            font=ctk.CTkFont(size=11),
        ).grid(row=1, column=0, padx=14, pady=(0, 7), sticky="w")
        buttons = ctk.CTkFrame(verdict, fg_color="transparent")
        buttons.grid(row=2, column=0, padx=14, pady=(0, 14), sticky="ew")
        buttons.grid_columnconfigure((0, 1), weight=1)
        self.criminal_button = ctk.CTkButton(
            buttons,
            text="!  Criminal",
            fg_color=theme.CRIMINAL_SOFT,
            hover_color=theme.CRIMINAL_HOVER,
            text_color=theme.CRIMINAL,
            command=lambda: self._submit_verdict(Status.CRIMINAL),
        )
        self.criminal_button.grid(row=0, column=0, padx=(0, 4), sticky="ew")
        self.innocent_button = ctk.CTkButton(
            buttons,
            text="✓  Innocent",
            fg_color=theme.INNOCENT_SOFT,
            hover_color=theme.INNOCENT_HOVER,
            text_color=theme.INNOCENT,
            command=lambda: self._submit_verdict(Status.INNOCENT),
        )
        self.innocent_button.grid(row=0, column=1, padx=(4, 0), sticky="ew")

        clues = self._panel(2, "Revealed clue browser")
        self.clue_menu = ctk.CTkOptionMenu(
            clues,
            values=["No revealed clues"],
            command=self._select_clue_from_menu,
            fg_color=theme.PANEL_SOFT,
            button_color=theme.PRIMARY,
            text_color=theme.TEXT_PRIMARY,
        )
        self.clue_menu.grid(row=1, column=0, padx=14, pady=(0, 14), sticky="ew")

        solver = self._panel(3, "Deduction controls")
        solver_buttons = ctk.CTkFrame(solver, fg_color="transparent")
        solver_buttons.grid(row=1, column=0, padx=14, pady=(0, 14), sticky="ew")
        solver_buttons.grid_columnconfigure((0, 1), weight=1)
        self.hint_button = ctk.CTkButton(
            solver_buttons,
            text="Hint",
            fg_color=theme.PANEL_SOFT,
            hover_color=theme.BORDER,
            text_color=theme.TEXT_PRIMARY,
            command=self._show_hint,
        )
        self.hint_button.grid(row=0, column=0, padx=(0, 4), pady=(0, 8), sticky="ew")
        self.step_button = ctk.CTkButton(
            solver_buttons,
            text="Next Step",
            fg_color=theme.PANEL_SOFT,
            hover_color=theme.BORDER,
            text_color=theme.TEXT_PRIMARY,
            command=self._solve_one_step,
        )
        self.step_button.grid(row=0, column=1, padx=(4, 0), pady=(0, 8), sticky="ew")
        self.auto_button = ctk.CTkButton(
            solver_buttons,
            text="▶  Auto Solve",
            fg_color=theme.PRIMARY,
            hover_color=theme.PRIMARY_HOVER,
            text_color=theme.PRIMARY_TEXT,
            command=self._toggle_auto_solve,
        )
        self.auto_button.grid(row=1, column=0, columnspan=2, sticky="ew")

        metrics = self._panel(4, "Solver metrics")
        self.metrics_label = ctk.CTkLabel(
            metrics,
            text="",
            justify="left",
            anchor="w",
            text_color=theme.TEXT_SECONDARY,
            font=ctk.CTkFont(family="Courier", size=11),
        )
        self.metrics_label.grid(row=1, column=0, padx=14, pady=(0, 14), sticky="ew")

        trace = self._panel(5, "Deduction trace")
        self.trace_text = ctk.CTkTextbox(
            trace,
            height=180,
            wrap="word",
            fg_color=theme.PANEL_SOFT,
            text_color=theme.TEXT_PRIMARY,
            font=ctk.CTkFont(size=11),
        )
        self.trace_text.grid(row=1, column=0, padx=14, pady=(0, 14), sticky="ew")
        self.trace_text.configure(state="disabled")

    def _build_footer(self) -> None:
        footer = ctk.CTkFrame(self, fg_color=theme.PANEL_BACKGROUND, corner_radius=0)
        footer.grid(row=2, column=0, sticky="ew")
        footer.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(
            footer,
            text="● Criminal    ● Innocent    ○ Unsolved    ◆ Highlighted",
            text_color=theme.TEXT_SECONDARY,
            font=ctk.CTkFont(size=11),
        ).grid(row=0, column=0, padx=18, pady=10, sticky="w")
        feedback = ctk.CTkFrame(footer, fg_color="transparent")
        feedback.grid(row=0, column=1, padx=18, pady=8, sticky="e")
        self.feedback_code = ctk.CTkLabel(
            feedback,
            text="READY",
            fg_color=theme.PANEL_SOFT,
            text_color=theme.TEXT_SECONDARY,
            corner_radius=8,
            width=96,
            height=25,
            font=ctk.CTkFont(size=10, weight="bold"),
        )
        self.feedback_code.pack(side="left", padx=(0, 8))
        self.feedback_label = ctk.CTkLabel(
            feedback,
            text="Public knowledge only",
            text_color=theme.TEXT_SECONDARY,
            anchor="e",
        )
        self.feedback_label.pack(side="left")

    def _build_board(self) -> None:
        for widget in self.board.winfo_children():
            widget.destroy()
        self.cards.clear()

        size = self.game_view.size
        previous_size = getattr(self, "_configured_board_size", 0)
        configured_size = max(previous_size, size)

        # Clear old grid weights first. This matters when loading a smaller
        # puzzle after a larger one; otherwise invisible columns keep space.
        for column in range(configured_size + 1):
            self.board.grid_columnconfigure(column, weight=0, uniform="")
        for row in range(configured_size + 1):
            self.board.grid_rowconfigure(row, weight=0, uniform="")

        self.board.grid_columnconfigure(0, weight=0)
        self.board.grid_rowconfigure(0, weight=0)
        for column in range(1, size + 1):
            self.board.grid_columnconfigure(column, weight=1, uniform="card_columns")
        for row in range(1, size + 1):
            self.board.grid_rowconfigure(row, weight=1, uniform="card_rows")
        self._configured_board_size = size

        for column in range(size):
            ctk.CTkLabel(
                self.board,
                text=chr(ord("A") + column),
                text_color=theme.TEXT_SECONDARY,
                font=ctk.CTkFont(weight="bold"),
            ).grid(row=0, column=column + 1, pady=(0, 4))

        cells_by_id = {cell.cell_id: cell for cell in self.game_view.cells}
        for row in range(1, size + 1):
            ctk.CTkLabel(
                self.board,
                text=str(row),
                width=24,
                text_color=theme.TEXT_SECONDARY,
                font=ctk.CTkFont(weight="bold"),
            ).grid(row=row, column=0, padx=(0, 4))
            for column in range(size):
                cell_id = f"{chr(ord('A') + column)}{row}"
                cell = cells_by_id.get(cell_id)
                if cell is None:
                    continue
                card = CharacterCard(self.board, cell, self._select_cell, self._select_clue)
                card.grid(row=row, column=column + 1, padx=5, pady=5, sticky="nsew")
                self.cards[cell_id] = card

    def _refresh_all(self, *, rebuild_board: bool = False) -> None:
        """Refresh after the logical game state has actually changed."""

        previous_size = getattr(self, "_rendered_size", None)
        self.game_view = self.gateway.get_public_state()
        if rebuild_board or previous_size != self.game_view.size or not self.cards:
            self._build_board()
            self._rendered_size = self.game_view.size

        self.puzzle_label.configure(
            text=f"{self.game_view.puzzle_name}  ·  {self.game_view.size}x{self.game_view.size} board"
        )
        self.progress_label.configure(
            text=f"Step {self.game_view.step}  ·  {self.game_view.solved_count}/{self.game_view.total_count} solved"
        )
        progress = (
            self.game_view.solved_count / self.game_view.total_count
            if self.game_view.total_count
            else 0
        )
        self.progress_bar.set(progress)
        phase_text, phase_color, phase_surface = PHASE_PRESENTATION[self.game_view.phase]
        self.phase_label.configure(
            text=phase_text,
            text_color=phase_color,
            fg_color=phase_surface,
        )

        by_id = {cell.cell_id: cell for cell in self.game_view.cells}
        for cell_id, card in self.cards.items():
            if cell_id in by_id:
                card.update_view(
                    by_id[cell_id],
                    selected=cell_id == self.selected_cell_id,
                    highlighted=cell_id in self.highlighted_cells,
                )
        self._refresh_detail()
        self._refresh_clue_browser()
        self._refresh_metrics()
        self._refresh_trace()
        self._refresh_controls()

    def _refresh_diagnostics(self) -> None:
        """Refresh solver diagnostics without repainting the board cards."""

        self.game_view = self.gateway.get_public_state()
        self._refresh_metrics()
        self._refresh_trace()

    def _selected_cell(self) -> CellView | None:
        return next(
            (cell for cell in self.game_view.cells if cell.cell_id == self.selected_cell_id),
            None,
        )

    def _refresh_card_styles(self, cell_ids: set[str] | None = None) -> None:
        """Refresh only visual selection/highlight state for specified cards."""

        targets = self.cards.keys() if cell_ids is None else cell_ids
        for cell_id in targets:
            card = self.cards.get(cell_id)
            if card is not None:
                card.update_style(
                    selected=cell_id == self.selected_cell_id,
                    highlighted=cell_id in self.highlighted_cells,
                )

    def _refresh_selection_view(
        self,
        previous_selected: str | None,
        previous_highlights: set[str],
    ) -> None:
        """Update only widgets affected by a selection/highlight change."""

        affected_cells = previous_highlights | self.highlighted_cells
        if previous_selected:
            affected_cells.add(previous_selected)
        if self.selected_cell_id:
            affected_cells.add(self.selected_cell_id)
        self._refresh_card_styles(affected_cells)
        self._refresh_detail()
        self._sync_clue_menu_selection()
        self._refresh_controls()

    def _refresh_detail(self) -> None:
        cell = self._selected_cell()
        if cell is None:
            self.selected_title.configure(text="Select a card")
            self.selected_meta.configure(text="No character selected")
            text, color, surface = UNSOLVED_PRESENTATION
            clue = "Choose a card to inspect its public information."
        else:
            self.selected_title.configure(text=f"{cell.cell_id} · {cell.name}")
            self.selected_meta.configure(text=cell.profession)
            if cell.revealed:
                text, color, surface = STATUS_PRESENTATION[cell.status]
                clue = cell.clue_text or "The engine did not provide clue text."
                if cell.clue_id:
                    clue = f"{cell.clue_id}\n{clue}"
            else:
                text, color, surface = UNSOLVED_PRESENTATION
                clue = "Face-down clue — prove CRIMINAL or INNOCENT to reveal it."

        self.selected_status.configure(text=text, fg_color=surface, text_color=color)
        self.clue_text.configure(state="normal")
        self.clue_text.delete("1.0", "end")
        self.clue_text.insert("1.0", clue)
        self.clue_text.configure(state="disabled")

    def _refresh_clue_browser(self) -> None:
        self.clue_menu_lookup = {
            f"{cell.cell_id} · {cell.clue_id or 'clue'}": cell.cell_id
            for cell in self.game_view.cells
            if cell.revealed and cell.clue_text
        }
        values = list(self.clue_menu_lookup) or ["No revealed clues"]
        self.clue_menu.configure(values=values)
        self.clue_menu.set(values[0])
        self._sync_clue_menu_selection()

    def _sync_clue_menu_selection(self) -> None:
        selected_label = next(
            (
                label
                for label, cell_id in self.clue_menu_lookup.items()
                if cell_id == self.selected_cell_id
            ),
            None,
        )
        if selected_label:
            self.clue_menu.set(selected_label)

    def _refresh_metrics(self) -> None:
        metrics = self.game_view.metrics
        self.metrics_label.configure(
            text=(
                f"SAT calls      {metrics.sat_calls:>6}\n"
                f"Decisions      {metrics.decisions:>6}\n"
                f"Propagations   {metrics.propagations:>6}\n"
                f"Backtracks     {metrics.backtracks:>6}\n"
                f"Runtime        {metrics.runtime_ms:>6.1f} ms"
            )
        )

    @staticmethod
    def _format_trace_entry(entry: TraceEntry) -> str:
        lines = [f"[Step {entry.step}] {entry.message}"]
        if entry.active_clue_ids:
            lines.append(f"  Active clues: {', '.join(entry.active_clue_ids)}")
        if entry.sat_queries:
            lines.extend(f"  Query: {query}" for query in entry.sat_queries)
        if entry.verdict:
            lines.append(f"  Verdict: {entry.verdict}")
        if entry.revealed_clue_id:
            lines.append(f"  Added to KB: {entry.revealed_clue_id}")
        return "\n".join(lines)

    def _refresh_trace(self) -> None:
        content = "\n\n".join(self._format_trace_entry(entry) for entry in self.game_view.trace)
        self.trace_text.configure(state="normal")
        self.trace_text.delete("1.0", "end")
        self.trace_text.insert("1.0", content or "No deduction step yet.")
        self.trace_text.see("end")
        self.trace_text.configure(state="disabled")

    def _refresh_controls(self) -> None:
        selected = self._selected_cell()
        can_submit = bool(
            selected
            and not selected.revealed
            and self.game_view.phase is GamePhase.ACTIVE
            and not self.auto_running
        )
        verdict_state = "normal" if can_submit else "disabled"
        self.criminal_button.configure(state=verdict_state)
        self.innocent_button.configure(state=verdict_state)

        can_deduce = self.game_view.phase in (GamePhase.READY, GamePhase.ACTIVE)
        self.hint_button.configure(
            state="normal" if can_deduce and not self.auto_running else "disabled"
        )
        self.step_button.configure(
            state="normal" if can_deduce and not self.auto_running else "disabled"
        )
        self.auto_button.configure(
            text="■  Stop" if self.auto_running else "▶  Auto Solve",
            state="normal" if can_deduce or self.auto_running else "disabled",
            fg_color=theme.ERROR if self.auto_running else theme.PRIMARY,
        )

    def _select_cell(self, cell_id: str) -> None:
        previous_selected = self.selected_cell_id
        previous_highlights = set(self.highlighted_cells)
        self.selected_cell_id = cell_id
        self.highlighted_cells.clear()
        self._show_feedback(f"Selected {cell_id}.", ActionCode.INFO)
        self._refresh_selection_view(previous_selected, previous_highlights)

    def _select_clue(self, cell_id: str) -> None:
        cell = next((cell for cell in self.game_view.cells if cell.cell_id == cell_id), None)
        if cell is None or not cell.revealed:
            return
        previous_selected = self.selected_cell_id
        previous_highlights = set(self.highlighted_cells)
        self.selected_cell_id = cell_id
        self.highlighted_cells = set(cell.clue_references)
        self._show_feedback(
            f"{cell.clue_id or cell_id}: highlighted {len(self.highlighted_cells)} referenced cells.",
            ActionCode.INFO,
        )
        self._refresh_selection_view(previous_selected, previous_highlights)

    def _select_clue_from_menu(self, label: str) -> None:
        cell_id = self.clue_menu_lookup.get(label)
        if cell_id:
            self._select_clue(cell_id)

    def _submit_verdict(self, status: Status) -> None:
        cell = self._selected_cell()
        if cell is None or cell.revealed:
            self._show_feedback("Select an unsolved character first.", ActionCode.INFO)
            return
        result = self.gateway.submit_verdict(cell.cell_id, status)
        game_changed = result.code in {
            ActionCode.ACCEPTED,
            ActionCode.SOLVED,
            ActionCode.UNKNOWN,
            ActionCode.INCONSISTENT,
        }
        self._handle_action_result(result, refresh_state=game_changed)

    def _show_hint(self) -> None:
        hint = self.gateway.get_hint()
        previous_selected = self.selected_cell_id
        previous_highlights = set(self.highlighted_cells)
        self.highlighted_cells = set(hint.target_cells)
        if hint.clue_source:
            self.selected_cell_id = hint.clue_source
        self._show_feedback(hint.message, ActionCode.INFO)
        self._refresh_selection_view(previous_selected, previous_highlights)

    def _solve_one_step(self) -> None:
        self._handle_action_result(self.gateway.auto_solve_step())

    def _toggle_auto_solve(self) -> None:
        if self.auto_running:
            self._stop_auto("Auto Solve paused.")
            return
        if self.game_view.phase not in (GamePhase.READY, GamePhase.ACTIVE):
            return
        self.auto_running = True
        self._show_feedback("Auto Solve is running one deduction at a time.", ActionCode.INFO)
        self._refresh_controls()
        self.auto_after_id = self.after(40, self._auto_solve_tick)

    def _auto_solve_tick(self) -> None:
        self.auto_after_id = None
        if not self.auto_running:
            return
        result = self.gateway.auto_solve_step()
        self._handle_action_result(result)
        if result.code is ActionCode.ACCEPTED and self.game_view.phase is GamePhase.ACTIVE:
            self.auto_after_id = self.after(self.AUTO_DELAY_MS, self._auto_solve_tick)
            return
        self._stop_auto()

    def _stop_auto(self, message: str | None = None) -> None:
        self.auto_running = False
        if self.auto_after_id is not None:
            self.after_cancel(self.auto_after_id)
            self.auto_after_id = None
        if message:
            self._show_feedback(message, ActionCode.INFO)
        self._refresh_controls()

    def _restart(self) -> None:
        if not messagebox.askyesno("Restart puzzle", "Reset all current progress?"):
            return
        self._stop_auto()
        result = self.gateway.restart()
        self.selected_cell_id = None
        self.highlighted_cells.clear()
        self._handle_action_result(result, rebuild_board=True)

    def _load_puzzle(self) -> None:
        selected = filedialog.askopenfilename(
            title="Load Griductive puzzle",
            filetypes=[("JSON puzzle", "*.json"), ("All files", "*.*")],
        )
        if not selected:
            return
        self._stop_auto()
        result = self.gateway.load_puzzle(Path(selected))
        self.selected_cell_id = None
        self.highlighted_cells.clear()
        self._handle_action_result(result, rebuild_board=True)

    def _handle_action_result(
        self,
        result: ActionResult,
        *,
        rebuild_board: bool = False,
        refresh_state: bool = True,
    ) -> None:
        previous_selected = self.selected_cell_id
        previous_highlights = set(self.highlighted_cells)
        if refresh_state or result.highlighted_cells:
            self.highlighted_cells = set(result.highlighted_cells)
        if result.cell_id:
            self.selected_cell_id = result.cell_id
        self._show_feedback(result.message, result.code)
        if refresh_state:
            self._refresh_all(rebuild_board=rebuild_board)
        else:
            # A rejected verdict cannot change cards/clues, but the solver may
            # still report new SAT-call metrics. Refresh those diagnostics only.
            self._refresh_diagnostics()
            self._refresh_selection_view(previous_selected, previous_highlights)

    def _show_feedback(self, message: str, code: ActionCode) -> None:
        colors = {
            ActionCode.ACCEPTED: theme.SUCCESS,
            ActionCode.SOLVED: theme.SUCCESS,
            ActionCode.NOT_PROVABLE: theme.WARNING,
            ActionCode.UNKNOWN: theme.WARNING,
            ActionCode.CONTRADICTED: theme.ERROR,
            ActionCode.INCONSISTENT: theme.ERROR,
            ActionCode.ERROR: theme.ERROR,
            ActionCode.INFO: theme.TEXT_SECONDARY,
        }
        surfaces = {
            ActionCode.ACCEPTED: theme.INNOCENT_SOFT,
            ActionCode.SOLVED: theme.INNOCENT_SOFT,
            ActionCode.NOT_PROVABLE: theme.WARNING_SOFT,
            ActionCode.UNKNOWN: theme.WARNING_SOFT,
            ActionCode.CONTRADICTED: theme.CRIMINAL_SOFT,
            ActionCode.INCONSISTENT: theme.CRIMINAL_SOFT,
            ActionCode.ERROR: theme.CRIMINAL_SOFT,
            ActionCode.INFO: theme.PANEL_SOFT,
        }
        self.feedback_code.configure(
            text=code.value,
            text_color=colors[code],
            fg_color=surfaces[code],
        )
        self.feedback_label.configure(text=message, text_color=colors[code])

    def _bind_shortcuts(self) -> None:
        for modifier in ("Control", "Command"):
            self.bind(f"<{modifier}-o>", lambda _event: self._load_puzzle())
            self.bind(f"<{modifier}-r>", lambda _event: self._restart())
        self.bind("<Key-c>", lambda _event: self._submit_verdict(Status.CRIMINAL))
        self.bind("<Key-i>", lambda _event: self._submit_verdict(Status.INNOCENT))
        self.bind("<Key-h>", lambda _event: self._show_hint())

    def _on_close(self) -> None:
        self._stop_auto()
        self.destroy()


def run_app(gateway: GameGateway | None = None) -> None:
    app = GriductiveApp(gateway=gateway)
    app.mainloop()
