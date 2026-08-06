from __future__ import annotations

from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Callable

import customtkinter as ctk

from . import theme
from .mock_engine import MockGameGateway
from .models import ActionCode, ActionResult, CellView, GameGateway, GameView, Status


ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")


STATUS_PRESENTATION = {
    Status.CRIMINAL: ("!  CRIMINAL", theme.CRIMINAL),
    Status.INNOCENT: ("✓  INNOCENT", theme.INNOCENT),
    Status.UNKNOWN: ("?  UNKNOWN", theme.TEXT_SECONDARY),
}


class CharacterCard(ctk.CTkFrame):
    def __init__(
        self,
        master: ctk.CTkBaseClass,
        cell: CellView,
        on_select: Callable[[str], None],
        on_clue_select: Callable[[str], None],
    ) -> None:
        super().__init__(master, corner_radius=14, border_width=1)
        self.cell = cell
        self.on_select = on_select
        self.on_clue_select = on_clue_select
        self.grid_columnconfigure(0, weight=1)

        self.card_button = ctk.CTkButton(
            self,
            text="",
            command=lambda: self.on_select(self.cell.cell_id),
            fg_color="transparent",
            hover_color=theme.PANEL_SOFT,
            anchor="w",
            corner_radius=10,
            height=78,
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
            font=ctk.CTkFont(size=11),
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
        status_text, status_color = STATUS_PRESENTATION[cell.status]
        if not cell.revealed:
            status_text, status_color = STATUS_PRESENTATION[Status.UNKNOWN]

        body = (
            f"{cell.cell_id}\n"
            f"{cell.name}\n"
            f"{cell.profession}\n"
            f"{status_text}"
        )
        self.card_button.configure(text=body, text_color=theme.TEXT_PRIMARY)

        if cell.revealed:
            surface = (
                theme.CRIMINAL_SOFT
                if cell.status is Status.CRIMINAL
                else theme.INNOCENT_SOFT
            )
            clue_preview = cell.clue_text or "Revealed clue"
            if len(clue_preview) > 34:
                clue_preview = clue_preview[:31] + "..."
            self.clue_button.configure(
                text=f"Clue · {clue_preview}",
                state="normal",
                text_color=status_color,
            )
        else:
            surface = theme.PANEL_BACKGROUND
            self.clue_button.configure(
                text="Face-down clue",
                state="disabled",
                text_color=theme.TEXT_SECONDARY,
            )

        border_color = theme.BORDER
        border_width = 1
        if highlighted:
            surface = theme.HIGHLIGHT_SOFT
            border_color = theme.HIGHLIGHT
            border_width = 2
        if selected:
            border_color = theme.PRIMARY
            border_width = 3

        self.configure(
            fg_color=surface,
            border_color=border_color,
            border_width=border_width,
        )


class GriductiveApp(ctk.CTk):
    def __init__(self, gateway: GameGateway | None = None) -> None:
        super().__init__(fg_color=theme.APP_BACKGROUND)
        self.gateway = gateway or MockGameGateway()
        self.state: GameView = self.gateway.get_public_state()
        self.selected_cell_id: str | None = None
        self.highlighted_cells: set[str] = set()
        self.cards: dict[str, CharacterCard] = {}

        self.title("Griductive Solver · GUI Template")
        self.geometry("1280x820")
        self.minsize(1020, 700)
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._build_header()
        self._build_content()
        self._build_footer()
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
            width=40,
            height=40,
            corner_radius=12,
            fg_color=theme.PRIMARY,
            text_color=theme.PRIMARY_TEXT,
            font=ctk.CTkFont(size=20, weight="bold"),
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
            text="Load",
            width=78,
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
        content.grid_columnconfigure(1, weight=1, minsize=300)

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
        self.progress_label = ctk.CTkLabel(
            board_head,
            text="",
            fg_color=theme.PANEL_SOFT,
            text_color=theme.TEXT_SECONDARY,
            corner_radius=12,
            width=150,
            height=28,
        )
        self.progress_label.grid(row=0, column=1, sticky="e")

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
        self.selected_meta = ctk.CTkLabel(
            detail,
            text="",
            text_color=theme.TEXT_SECONDARY,
        )
        self.selected_meta.grid(row=2, column=0, padx=14, pady=(2, 6), sticky="w")
        self.selected_status = ctk.CTkLabel(
            detail,
            text="?  UNKNOWN",
            fg_color=theme.PANEL_SOFT,
            text_color=theme.TEXT_SECONDARY,
            corner_radius=10,
            width=118,
            height=30,
        )
        self.selected_status.grid(row=3, column=0, padx=14, pady=(0, 8), sticky="w")
        self.clue_text = ctk.CTkTextbox(
            detail,
            height=82,
            wrap="word",
            fg_color=theme.PANEL_SOFT,
            border_width=0,
            text_color=theme.TEXT_PRIMARY,
        )
        self.clue_text.grid(row=4, column=0, padx=14, pady=(0, 14), sticky="ew")
        self.clue_text.insert("1.0", "Choose a card to inspect its public information.")
        self.clue_text.configure(state="disabled")

        verdict = self._panel(1, "Submit verdict")
        buttons = ctk.CTkFrame(verdict, fg_color="transparent")
        buttons.grid(row=1, column=0, padx=14, pady=(0, 14), sticky="ew")
        buttons.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkButton(
            buttons,
            text="!  Criminal",
            fg_color=theme.CRIMINAL_SOFT,
            hover_color=theme.CRIMINAL_HOVER,
            text_color=theme.CRIMINAL,
            command=lambda: self._submit_verdict(Status.CRIMINAL),
        ).grid(row=0, column=0, padx=(0, 4), sticky="ew")
        ctk.CTkButton(
            buttons,
            text="✓  Innocent",
            fg_color=theme.INNOCENT_SOFT,
            hover_color=theme.INNOCENT_HOVER,
            text_color=theme.INNOCENT,
            command=lambda: self._submit_verdict(Status.INNOCENT),
        ).grid(row=0, column=1, padx=(4, 0), sticky="ew")

        solver = self._panel(2, "Solver controls")
        solver_buttons = ctk.CTkFrame(solver, fg_color="transparent")
        solver_buttons.grid(row=1, column=0, padx=14, pady=(0, 14), sticky="ew")
        solver_buttons.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkButton(
            solver_buttons,
            text="Hint",
            fg_color=theme.PANEL_SOFT,
            hover_color=theme.BORDER,
            text_color=theme.TEXT_PRIMARY,
            command=self._show_hint,
        ).grid(row=0, column=0, padx=(0, 4), sticky="ew")
        ctk.CTkButton(
            solver_buttons,
            text="Auto Solve",
            fg_color=theme.PRIMARY,
            hover_color=theme.PRIMARY_HOVER,
            text_color=theme.PRIMARY_TEXT,
            command=self._auto_solve,
        ).grid(row=0, column=1, padx=(4, 0), sticky="ew")

        trace = self._panel(3, "Deduction trace")
        self.trace_text = ctk.CTkTextbox(
            trace,
            height=140,
            wrap="word",
            fg_color=theme.PANEL_SOFT,
            text_color=theme.TEXT_PRIMARY,
        )
        self.trace_text.grid(row=1, column=0, padx=14, pady=(0, 14), sticky="ew")
        self.trace_text.configure(state="disabled")

    def _build_footer(self) -> None:
        footer = ctk.CTkFrame(
            self,
            fg_color=theme.PANEL_BACKGROUND,
            corner_radius=0,
        )
        footer.grid(row=2, column=0, sticky="ew")
        footer.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(
            footer,
            text="● Criminal    ● Innocent    ● Unknown",
            text_color=theme.TEXT_SECONDARY,
        ).grid(row=0, column=0, padx=18, pady=10, sticky="w")
        self.feedback_label = ctk.CTkLabel(
            footer,
            text="Ready · Public knowledge only",
            text_color=theme.TEXT_SECONDARY,
            anchor="e",
        )
        self.feedback_label.grid(row=0, column=1, padx=18, pady=10, sticky="e")

    def _build_board(self) -> None:
        for widget in self.board.winfo_children():
            widget.destroy()
        self.cards.clear()

        size = self.state.size
        for column in range(size + 1):
            self.board.grid_columnconfigure(column, weight=1 if column else 0)
        for row in range(size + 1):
            self.board.grid_rowconfigure(row, weight=1 if row else 0)

        for column in range(size):
            ctk.CTkLabel(
                self.board,
                text=chr(ord("A") + column),
                text_color=theme.TEXT_SECONDARY,
                font=ctk.CTkFont(weight="bold"),
            ).grid(row=0, column=column + 1, pady=(0, 4))

        cells_by_id = {cell.cell_id: cell for cell in self.state.cells}
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
                cell = cells_by_id[cell_id]
                card = CharacterCard(
                    self.board,
                    cell,
                    self._select_cell,
                    self._select_clue,
                )
                card.grid(
                    row=row,
                    column=column + 1,
                    padx=5,
                    pady=5,
                    sticky="nsew",
                )
                self.cards[cell_id] = card

    def _refresh_all(self, *, rebuild_board: bool = False) -> None:
        previous_size = getattr(self, "_rendered_size", None)
        self.state = self.gateway.get_public_state()
        if rebuild_board or previous_size != self.state.size or not self.cards:
            self._build_board()
            self._rendered_size = self.state.size

        self.puzzle_label.configure(text=self.state.puzzle_name)
        self.progress_label.configure(
            text=f"Step {self.state.step} · {self.state.solved_count}/{len(self.state.cells)} solved"
        )
        by_id = {cell.cell_id: cell for cell in self.state.cells}
        for cell_id, card in self.cards.items():
            card.update_view(
                by_id[cell_id],
                selected=cell_id == self.selected_cell_id,
                highlighted=cell_id in self.highlighted_cells,
            )
        self._refresh_detail()
        self._refresh_trace()

    def _selected_cell(self) -> CellView | None:
        return next(
            (cell for cell in self.state.cells if cell.cell_id == self.selected_cell_id),
            None,
        )

    def _refresh_detail(self) -> None:
        cell = self._selected_cell()
        if cell is None:
            self.selected_title.configure(text="Select a card")
            self.selected_meta.configure(text="")
            self.selected_status.configure(
                text="?  UNKNOWN",
                fg_color=theme.PANEL_SOFT,
                text_color=theme.TEXT_SECONDARY,
            )
            clue = "Choose a card to inspect its public information."
        else:
            self.selected_title.configure(text=f"{cell.cell_id} · {cell.name}")
            self.selected_meta.configure(text=cell.profession)
            status = cell.status if cell.revealed else Status.UNKNOWN
            status_text, status_color = STATUS_PRESENTATION[status]
            surface = theme.PANEL_SOFT
            if status is Status.CRIMINAL:
                surface = theme.CRIMINAL_SOFT
            elif status is Status.INNOCENT:
                surface = theme.INNOCENT_SOFT
            self.selected_status.configure(
                text=status_text,
                fg_color=surface,
                text_color=status_color,
            )
            clue = cell.clue_text or "Face-down clue — prove a verdict to reveal it."

        self.clue_text.configure(state="normal")
        self.clue_text.delete("1.0", "end")
        self.clue_text.insert("1.0", clue)
        self.clue_text.configure(state="disabled")

    def _refresh_trace(self) -> None:
        content = "\n".join(
            f"{index}. {entry}" for index, entry in enumerate(self.state.trace, 1)
        )
        self.trace_text.configure(state="normal")
        self.trace_text.delete("1.0", "end")
        self.trace_text.insert("1.0", content or "No deduction step yet.")
        self.trace_text.configure(state="disabled")

    def _select_cell(self, cell_id: str) -> None:
        self.selected_cell_id = cell_id
        self.highlighted_cells.clear()
        self._show_feedback(f"Selected {cell_id}.", ActionCode.INFO)
        self._refresh_all()

    def _select_clue(self, cell_id: str) -> None:
        cell = next(cell for cell in self.state.cells if cell.cell_id == cell_id)
        if not cell.revealed:
            return
        self.selected_cell_id = cell_id
        self.highlighted_cells = set(cell.clue_references)
        self._show_feedback(
            f"Clue {cell_id}: highlighted {len(self.highlighted_cells)} referenced cells.",
            ActionCode.INFO,
        )
        self._refresh_all()

    def _submit_verdict(self, status: Status) -> None:
        if self.selected_cell_id is None:
            self._show_feedback("Select an unresolved character first.", ActionCode.INFO)
            return
        result = self.gateway.submit_verdict(self.selected_cell_id, status)
        self._handle_action_result(result)

    def _show_hint(self) -> None:
        hint = self.gateway.get_hint()
        self.highlighted_cells = set(hint.target_cells)
        if hint.clue_source:
            self.selected_cell_id = hint.clue_source
        self._show_feedback(hint.message, ActionCode.INFO)
        self._refresh_all()

    def _auto_solve(self) -> None:
        result = self.gateway.auto_solve_step()
        self._handle_action_result(result)

    def _restart(self) -> None:
        if not messagebox.askyesno("Restart puzzle", "Reset all current progress?"):
            return
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
        result = self.gateway.load_puzzle(Path(selected))
        self.selected_cell_id = None
        self.highlighted_cells.clear()
        self._handle_action_result(result, rebuild_board=True)

    def _handle_action_result(
        self,
        result: ActionResult,
        *,
        rebuild_board: bool = False,
    ) -> None:
        self.highlighted_cells = set(result.highlighted_cells)
        if result.cell_id:
            self.selected_cell_id = result.cell_id
        self._show_feedback(result.message, result.code)
        self._refresh_all(rebuild_board=rebuild_board)

    def _show_feedback(self, message: str, code: ActionCode) -> None:
        colors = {
            ActionCode.ACCEPTED: theme.SUCCESS,
            ActionCode.NOT_PROVABLE: theme.WARNING,
            ActionCode.CONTRADICTED: theme.ERROR,
            ActionCode.INCONSISTENT: theme.ERROR,
            ActionCode.INFO: theme.TEXT_SECONDARY,
        }
        self.feedback_label.configure(text=message, text_color=colors[code])


def run_app() -> None:
    app = GriductiveApp()
    app.mainloop()
