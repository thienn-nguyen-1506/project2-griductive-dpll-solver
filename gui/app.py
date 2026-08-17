"""Griductive Solver GUI - Graphite & Zinc Gray Edition."""

from __future__ import annotations

import textwrap
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Callable, Dict

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageEnhance

from . import theme
from .mock_engine import MockGameGateway
from .models import (
    ActionCode,
    ActionResult,
    CellView,
    GameGateway,
    GamePhase,
    GameView,
    PuzzleOption,
    Status,
    TraceEntry,
    build_verdict_feedback,
)

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# ======================================================================
# BẢNG MÀU GRAPHITE & ZINC GRAY (MINIMALIST)
# ======================================================================
theme.APP_BACKGROUND   = ("#f1f5f9", "#18181b")  # Nền Zinc Dark / Cool Light Gray
theme.PANEL_BACKGROUND = ("#ffffff", "#27272a")  # Panel xám chì trung tính
theme.PANEL_SOFT       = ("#e2e8f0", "#3f3f46")  # Nền mềm xám xi măng
theme.BORDER           = ("#cbd5e1", "#52525b")  # Viền xám kim loại

theme.PRIMARY          = ("#334155", "#e4e4e7")  # Bright Zinc Accent nổi bật trên xám tối
theme.PRIMARY_HOVER    = ("#1e293b", "#f4f4f5")
theme.PRIMARY_SOFT     = ("#e2e8f0", "#3f3f46")
theme.PRIMARY_TEXT     = ("#ffffff", "#18181b")  # Chữ tối tương phản trên nút xám sáng

theme.INNOCENT         = ("#059669", "#34d399")  # Green Mint Accent
theme.INNOCENT_SOFT    = ("#d1fae5", "#064e3b")
theme.INNOCENT_HOVER   = ("#047857", "#6ee7b7")

theme.CRIMINAL         = ("#e11d48", "#fb7185")  # Red Rose Accent
theme.CRIMINAL_SOFT    = ("#ffe4e6", "#4c0519")
theme.CRIMINAL_HOVER   = ("#be123c", "#fca5a5")

theme.SUCCESS          = ("#059669", "#34d399")
theme.WARNING          = ("#d97706", "#fbbf24")
theme.WARNING_SOFT     = ("#fef3c7", "#451a03")
theme.ERROR            = ("#e11d48", "#fb7185")

# Màu chữ & Điểm nhấn linh hoạt (Đã nâng cấp màu Highlight Rực Rỡ)
COLOR_TEXT_MAIN       = ("#0f172a", "#fafafa")  # Chữ trắng bạc sáng
COLOR_TEXT_MUTED      = ("#64748b", "#a1a1aa")  # Chữ phụ xám trung tính
COLOR_ACTIVE_SELECTED = ("#334155", "#ffffff")  # Viền chọn xám bạc
COLOR_RELATION        = ("#2563eb", "#38bdf8")  # Xanh Lam Electric (Cyan)

COLOR_DIMMED_BG      = ("#cbd5e1", "#27272a")
COLOR_DIMMED_TEXT    = ("#94a3b8", "#71717a")

_AVATAR_CACHE: dict[tuple[int, int, bool], ctk.CTkImage] = {}


def _draw_avatar_silhouette(color: tuple[int, int, int, int]) -> Image.Image:
    """Tạo hình Silhouette nhân vật."""
    img = Image.new("RGBA", (256, 256), color=(0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([88, 36, 168, 116], fill=color)
    draw.chord([40, 130, 216, 280], start=180, end=360, fill=color)
    return img


def get_avatar_ctk_image(
    size: tuple[int, int] = (64, 64),
    dimmed: bool = False,
    image_path: str = "avatar.png",
) -> ctk.CTkImage:
    """Tải Avatar hỗ trợ hiển thị sắc nét cho Gray Theme."""
    cache_key = (size[0], size[1], dimmed)
    if cache_key in _AVATAR_CACHE:
        return _AVATAR_CACHE[cache_key]

    path = Path(image_path)
    if not path.exists():
        path = Path("avatar.jpg")

    if path.exists():
        img = Image.open(path).convert("RGBA")
        if dimmed:
            img = ImageEnhance.Brightness(img).enhance(0.4)
        ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=size)
    else:
        dark_silhouette = (51, 65, 85, 230)      # Slate Slate Dark cho Light Mode
        light_silhouette = (228, 228, 231, 230)  # Zinc Bright Silver cho Dark Mode

        light_img = _draw_avatar_silhouette(dark_silhouette)
        dark_img = _draw_avatar_silhouette(light_silhouette)

        if dimmed:
            light_img = ImageEnhance.Brightness(light_img).enhance(0.4)
            dark_img = ImageEnhance.Brightness(dark_img).enhance(0.4)

        ctk_img = ctk.CTkImage(light_image=light_img, dark_image=dark_img, size=size)

    _AVATAR_CACHE[cache_key] = ctk_img
    return ctk_img


# ----------------------------------------------------------------------
# IN-APP POPUP DIALOGS
# ----------------------------------------------------------------------
class BaseModal(ctk.CTkFrame):
    def __init__(
        self,
        parent: ctk.CTk,
        title: str = "Griductive",
        width: int = 430,
        height: int = 420,
        on_cancel: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(
            parent,
            width=width,
            height=height,
            corner_radius=0,
            fg_color=theme.PANEL_BACKGROUND,
            border_width=2,
            border_color=theme.PRIMARY,
        )
        self.app = parent
        self.on_cancel = on_cancel

        self.place(relx=0.5, rely=0.5, anchor="center")
        self.lift()
        self.grid_propagate(False)

        close_btn = ctk.CTkButton(
            self,
            text="✕",
            width=28,
            height=28,
            corner_radius=0,
            fg_color="transparent",
            hover_color=theme.PANEL_SOFT,
            text_color=COLOR_TEXT_MUTED,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self.close,
        )
        close_btn.place(relx=0.96, rely=0.04, anchor="ne")

        self._click_binding = self.app.bind("<Button-1>", self._on_outside_click, add="+")

    def _on_outside_click(self, event) -> None:
        if not self.winfo_exists():
            return
        x1 = self.winfo_rootx()
        y1 = self.winfo_rooty()
        x2 = x1 + self.winfo_width()
        y2 = y1 + self.winfo_height()
        if not (x1 <= event.x_root <= x2 and y1 <= event.y_root <= y2):
            self.close()

    def close(self) -> None:
        if hasattr(self, "_click_binding") and self._click_binding:
            try:
                self.app.unbind("<Button-1>", self._click_binding)
            except Exception:
                pass
        if hasattr(self.app, "suppress_clicks_temporarily"):
            self.app.suppress_clicks_temporarily(150)
        if self.on_cancel:
            self.on_cancel()
        self.destroy()


class VerdictDialog(BaseModal):
    def __init__(
        self,
        parent: ctk.CTk,
        cell: CellView,
        on_submit: Callable[[Status], None],
        on_cancel: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(
            parent,
            title=f"Verdict - {cell.name}",
            width=430,
            height=420,
            on_cancel=on_cancel,
        )
        self.cell = cell
        self.on_submit = on_submit

        self.grid_columnconfigure(0, weight=1)

        avatar_img = get_avatar_ctk_image(size=(64, 64))
        avatar = ctk.CTkLabel(
            self,
            image=avatar_img,
            text="",
            width=64,
            height=64,
            corner_radius=0,
            fg_color="transparent",
        )
        avatar.grid(row=0, column=0, pady=(20, 6))

        name_label = ctk.CTkLabel(
            self,
            text=cell.name,
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=COLOR_TEXT_MAIN,
        )
        name_label.grid(row=1, column=0, pady=(0, 2))

        meta_label = ctk.CTkLabel(
            self,
            text=f"{cell.cell_id}  ·  {cell.profession}",
            font=ctk.CTkFont(size=13),
            text_color=COLOR_TEXT_MUTED,
        )
        meta_label.grid(row=2, column=0, pady=(0, 14))

        heading_label = ctk.CTkLabel(
            self,
            text="Innocent or criminal?",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=COLOR_TEXT_MAIN,
        )
        heading_label.grid(row=3, column=0, pady=(0, 6))

        desc_text = (
            "You can only lock a verdict the clues actually prove — "
            "a correct call flips them and reveals their statement."
        )
        desc_label = ctk.CTkLabel(
            self,
            text=textwrap.fill(desc_text, width=42),
            font=ctk.CTkFont(size=12),
            text_color=COLOR_TEXT_MUTED,
            justify="center",
        )
        desc_label.grid(row=4, column=0, pady=(0, 18), padx=20)

        buttons_frame = ctk.CTkFrame(self, fg_color="transparent")
        buttons_frame.grid(row=5, column=0, padx=24, pady=(0, 10), sticky="ew")
        buttons_frame.grid_columnconfigure((0, 1), weight=1)

        self.innocent_btn = ctk.CTkButton(
            buttons_frame,
            text="Innocent",
            height=44,
            corner_radius=0,
            fg_color=theme.INNOCENT_SOFT,
            hover_color=theme.INNOCENT_HOVER,
            text_color=theme.INNOCENT,
            border_width=1,
            border_color=theme.INNOCENT,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=lambda: self._choose(Status.INNOCENT),
        )
        self.innocent_btn.grid(row=0, column=0, padx=(0, 6), sticky="ew")

        self.criminal_btn = ctk.CTkButton(
            buttons_frame,
            text="Criminal",
            height=44,
            corner_radius=0,
            fg_color=theme.CRIMINAL_SOFT,
            hover_color=theme.CRIMINAL_HOVER,
            text_color=theme.CRIMINAL,
            border_width=1,
            border_color=theme.CRIMINAL,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=lambda: self._choose(Status.CRIMINAL),
        )
        self.criminal_btn.grid(row=0, column=1, padx=(6, 0), sticky="ew")

        cancel_btn = ctk.CTkButton(
            self,
            text="Cancel",
            fg_color="transparent",
            hover_color=theme.PANEL_SOFT,
            text_color=COLOR_TEXT_MUTED,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self.close,
        )
        cancel_btn.grid(row=6, column=0, pady=(0, 14))

    def _choose(self, status: Status) -> None:
        callback = self.on_submit
        self.on_cancel = None
        self.close()
        if callback:
            callback(status)


class ConclusionNotPossibleDialog(BaseModal):
    def __init__(
        self,
        parent: ctk.CTk,
        cell: CellView,
        attempted_status: Status,
        action_code: ActionCode,
        message: str | None = None,
        on_cancel: Callable[[], None] | None = None,
    ) -> None:
        feedback = build_verdict_feedback(
            action_code,
            cell,
            attempted_status,
            message,
        )
        super().__init__(
            parent,
            title=feedback.title,
            width=440,
            height=380,
            on_cancel=on_cancel,
        )

        self.grid_columnconfigure(0, weight=1)

        icon_badge = ctk.CTkLabel(
            self,
            text=feedback.icon,
            width=56,
            height=56,
            corner_radius=0,
            fg_color=(
                theme.CRIMINAL_SOFT
                if feedback.tone == "error"
                else theme.WARNING_SOFT
            ),
            font=ctk.CTkFont(size=24),
        )
        icon_badge.grid(row=0, column=0, pady=(20, 8))

        title_label = ctk.CTkLabel(
            self,
            text=feedback.title,
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=(
                theme.ERROR if feedback.tone == "error" else theme.WARNING
            ),
        )
        title_label.grid(row=1, column=0, pady=(0, 10))

        desc_label = ctk.CTkLabel(
            self,
            text=feedback.main,
            font=ctk.CTkFont(size=13),
            text_color=COLOR_TEXT_MAIN,
            justify="center",
            wraplength=380,
        )
        desc_label.grid(row=2, column=0, pady=(0, 10), padx=24)

        advice_label = ctk.CTkLabel(
            self,
            text=feedback.advice,
            font=ctk.CTkFont(size=13),
            text_color=COLOR_TEXT_MUTED,
            justify="center",
            wraplength=380,
        )
        advice_label.grid(row=3, column=0, pady=(0, 18), padx=24)

        keep_looking_btn = ctk.CTkButton(
            self,
            text=feedback.button,
            height=44,
            corner_radius=0,
            fg_color=theme.PRIMARY,
            hover_color=theme.PRIMARY_HOVER,
            text_color=theme.PRIMARY_TEXT,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self.close,
        )
        keep_looking_btn.grid(row=4, column=0, padx=24, pady=(0, 16), sticky="ew")


class LevelSelectDialog(BaseModal):
    """In-app catalog for loading one of the bundled logical puzzles."""

    def __init__(
        self,
        parent: ctk.CTk,
        levels: tuple[PuzzleOption, ...],
        current_puzzle_name: str,
        on_select: Callable[[PuzzleOption], None],
    ) -> None:
        super().__init__(
            parent,
            title="Choose Level",
            width=520,
            height=570,
        )
        self.on_select = on_select
        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self,
            text="Choose a level",
            text_color=COLOR_TEXT_MAIN,
            font=ctk.CTkFont(size=22, weight="bold"),
        ).grid(row=0, column=0, padx=24, pady=(22, 4), sticky="w")
        ctk.CTkLabel(
            self,
            text="Select a built-in puzzle. Your current progress will be replaced.",
            text_color=COLOR_TEXT_MUTED,
            font=ctk.CTkFont(size=12),
        ).grid(row=1, column=0, padx=24, pady=(0, 12), sticky="w")

        level_list = ctk.CTkScrollableFrame(
            self,
            width=456,
            height=420,
            fg_color=theme.PANEL_SOFT,
            corner_radius=0,
            scrollbar_button_color=theme.BORDER,
        )
        level_list.grid(row=2, column=0, padx=24, pady=(0, 20), sticky="nsew")
        level_list.grid_columnconfigure(0, weight=1)

        for index, option in enumerate(levels, start=1):
            is_current = option.name == current_puzzle_name
            button = ctk.CTkButton(
                level_list,
                text=f"LEVEL {index:02d}   ·   {option.name}   ·   {option.size}×{option.size}",
                height=48,
                corner_radius=0,
                anchor="w",
                fg_color=theme.PRIMARY if is_current else theme.PANEL_BACKGROUND,
                hover_color=theme.PRIMARY_HOVER if is_current else theme.BORDER,
                text_color=theme.PRIMARY_TEXT if is_current else COLOR_TEXT_MAIN,
                border_width=1,
                border_color=theme.PRIMARY if is_current else theme.BORDER,
                font=ctk.CTkFont(size=13, weight="bold"),
                command=lambda selected=option: self._choose(selected),
            )
            button.grid(row=index - 1, column=0, padx=8, pady=5, sticky="ew")

    def _choose(self, option: PuzzleOption) -> None:
        callback = self.on_select
        self.on_cancel = None
        self.close()
        callback(option)


# ----------------------------------------------------------------------
# CHARACTER CARD
# ----------------------------------------------------------------------
class CharacterCard(ctk.CTkFrame):
    def __init__(
        self,
        master: ctk.CTkBaseClass,
        cell: CellView,
        on_select: Callable[[str], None],
        on_clue_select: Callable[[str], None],
    ) -> None:
        super().__init__(master, corner_radius=0, border_width=1)
        self.cell = cell
        self.on_select = on_select
        self.on_clue_select = on_clue_select

        self._base_surface = theme.PANEL_BACKGROUND
        self._base_border = theme.BORDER

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.id_label = ctk.CTkLabel(
            self,
            text=cell.cell_id,
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=COLOR_TEXT_MUTED,
            fg_color="transparent",
        )
        self.id_label.place(x=6, y=4, anchor="nw")

        self.unrevealed_frame = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        self.unrevealed_frame.grid_columnconfigure(0, weight=1)
        self.unrevealed_frame.grid_rowconfigure((0, 1, 2), weight=1)

        self.unrevealed_avatar = ctk.CTkLabel(
            self.unrevealed_frame,
            image=get_avatar_ctk_image(size=(48, 48)),
            text="",
            fg_color="transparent",
        )
        self.unrevealed_avatar.grid(row=0, column=0, pady=(12, 2))

        self.unrevealed_name = ctk.CTkLabel(
            self.unrevealed_frame,
            text="",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLOR_TEXT_MAIN,
            anchor="center",
        )
        self.unrevealed_name.grid(row=1, column=0, pady=(0, 1))

        self.unrevealed_prof = ctk.CTkLabel(
            self.unrevealed_frame,
            text="",
            font=ctk.CTkFont(size=10),
            text_color=COLOR_TEXT_MUTED,
            anchor="center",
        )
        self.unrevealed_prof.grid(row=2, column=0, pady=(0, 8))

        self.revealed_frame = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        self.revealed_frame.grid_columnconfigure(0, weight=1)
        self.revealed_frame.grid_rowconfigure(1, weight=1)

        header_rev = ctk.CTkFrame(self.revealed_frame, fg_color="transparent", corner_radius=0)
        header_rev.grid(row=0, column=0, pady=(4, 1), padx=(22, 6), sticky="e")

        self.revealed_avatar = ctk.CTkLabel(
            header_rev,
            image=get_avatar_ctk_image(size=(20, 20)),
            text="",
            fg_color="transparent",
        )
        self.revealed_avatar.grid(row=0, column=0, rowspan=2, padx=(0, 4))

        self.revealed_name = ctk.CTkLabel(
            header_rev,
            text="",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COLOR_TEXT_MAIN,
            anchor="w",
        )
        self.revealed_name.grid(row=0, column=1, sticky="w")

        self.revealed_prof = ctk.CTkLabel(
            header_rev,
            text="",
            font=ctk.CTkFont(size=9),
            text_color=COLOR_TEXT_MUTED,
            anchor="w",
        )
        self.revealed_prof.grid(row=1, column=1, sticky="w")

        self.clue_label = ctk.CTkLabel(
            self.revealed_frame,
            text="",
            font=ctk.CTkFont(size=9, weight="bold"),
            text_color=COLOR_TEXT_MAIN,
            justify="center",
            anchor="center",
        )
        self.clue_label.grid(row=1, column=0, padx=4, pady=(1, 4), sticky="nsew")

        self._bind_card_clicks(self)

    def _bind_card_clicks(self, widget: ctk.CTkBaseClass) -> None:
        widget.bind("<Button-1>", lambda _e: self._handle_card_click())
        for child in widget.winfo_children():
            self._bind_card_clicks(child)

    def _handle_card_click(self) -> None:
        if self.cell.revealed:
            self.on_clue_select(self.cell.cell_id)
        else:
            self.on_select(self.cell.cell_id)

    def update_view(
        self,
        cell: CellView,
        *,
        selected: bool,
        highlight_color: str | None,
        is_dimmed: bool,
        board_size: int = 5,
    ) -> None:
        self.cell = cell
        self.id_label.configure(text=cell.cell_id)

        if board_size >= 5:
            av_unrev, av_rev = (42, 42), (18, 18)
            f_name_unrev, f_prof_unrev = 11, 9
            f_name_rev, f_prof_rev, f_clue = 10, 8, 9
            fixed_wraplength = 135
        else:
            av_unrev, av_rev = (52, 52), (22, 22)
            f_name_unrev, f_prof_unrev = 13, 10
            f_name_rev, f_prof_rev, f_clue = 11, 9, 10
            fixed_wraplength = 175

        self.unrevealed_avatar.configure(image=get_avatar_ctk_image(size=av_unrev, dimmed=is_dimmed))
        self.revealed_avatar.configure(image=get_avatar_ctk_image(size=av_rev, dimmed=is_dimmed))

        self.unrevealed_name.configure(font=ctk.CTkFont(size=f_name_unrev, weight="bold"))
        self.unrevealed_prof.configure(font=ctk.CTkFont(size=f_prof_unrev))
        self.revealed_name.configure(font=ctk.CTkFont(size=f_name_rev, weight="bold"))
        self.revealed_prof.configure(font=ctk.CTkFont(size=f_prof_rev))

        if cell.revealed:
            if cell.status == Status.INNOCENT:
                self._base_surface = theme.INNOCENT_SOFT
                self._base_border = theme.INNOCENT
            else:
                self._base_surface = theme.CRIMINAL_SOFT
                self._base_border = theme.CRIMINAL

            self.unrevealed_frame.grid_forget()
            self.revealed_frame.grid(row=0, column=0, sticky="nsew", padx=1, pady=1)

            self.revealed_name.configure(text=cell.name)
            self.revealed_prof.configure(text=cell.profession)

            self.clue_label.configure(
                text=cell.clue_text or "Revealed clue",
                font=ctk.CTkFont(size=f_clue, weight="bold"),
                wraplength=fixed_wraplength,
            )
        else:
            self._base_surface = theme.PANEL_BACKGROUND
            self._base_border = theme.BORDER

            self.revealed_frame.grid_forget()
            self.unrevealed_frame.grid(row=0, column=0, sticky="nsew", padx=1, pady=1)

            self.unrevealed_name.configure(text=cell.name)
            self.unrevealed_prof.configure(text=cell.profession)

        self.id_label.lift()
        self.update_style(selected=selected, highlight_color=highlight_color, is_dimmed=is_dimmed)

    def update_style(self, *, selected: bool, highlight_color: str | None, is_dimmed: bool) -> None:
        if is_dimmed:
            surface = COLOR_DIMMED_BG
            border_color = theme.BORDER
            text_color = COLOR_DIMMED_TEXT
            border_width = 1
        else:
            surface = self._base_surface
            border_color = self._base_border
            text_color = COLOR_TEXT_MAIN
            border_width = 1

            if highlight_color:
                border_color = highlight_color
                border_width = 3  # Tăng lên 3px để viền highlight sáng rực rõ ràng hơn

            if selected:
                border_color = COLOR_ACTIVE_SELECTED
                border_width = 3

        self.configure(fg_color=surface, border_color=border_color, border_width=border_width)

        self.unrevealed_name.configure(text_color=text_color)
        self.unrevealed_prof.configure(text_color=text_color if not is_dimmed else COLOR_DIMMED_TEXT)
        self.revealed_name.configure(text_color=text_color)
        self.revealed_prof.configure(text_color=text_color if not is_dimmed else COLOR_DIMMED_TEXT)
        self.clue_label.configure(text_color=text_color)
        self.id_label.configure(text_color=text_color if not is_dimmed else COLOR_DIMMED_TEXT)


# ----------------------------------------------------------------------
# MAIN APPLICATION GUI
# ----------------------------------------------------------------------
class GriductiveApp(ctk.CTk):
    AUTO_DELAY_MS = 450

    def __init__(self, gateway: GameGateway | None = None) -> None:
        super().__init__(fg_color=theme.APP_BACKGROUND)
        _AVATAR_CACHE.clear()
        self.gateway = gateway or MockGameGateway()
        self.game_view: GameView = self.gateway.get_public_state()
        self.selected_cell_id: str | None = None
        self.highlighted_color_map: Dict[str, str] = {}
        self.cards: dict[str, CharacterCard] = {}
        self.metric_labels: dict[str, ctk.CTkLabel] = {}
        self.auto_running = False
        self.auto_after_id: str | None = None
        self._ignore_clicks = False

        self.title("Griductive Solver - Graphite Gray Edition")
        self.geometry("1380x880")
        self.minsize(1080, 740)
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._build_header()
        self._build_content()
        self._bind_shortcuts()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._refresh_all()

    def suppress_clicks_temporarily(self, ms: int = 150) -> None:
        self._ignore_clicks = True
        self.after(ms, lambda: setattr(self, "_ignore_clicks", False))

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
            corner_radius=0,
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
            text_color=COLOR_TEXT_MAIN,
            font=ctk.CTkFont(size=19, weight="bold"),
        ).pack(anchor="w")
        self.puzzle_label = ctk.CTkLabel(
            title_frame,
            text="",
            text_color=COLOR_TEXT_MUTED,
            font=ctk.CTkFont(size=12),
        )
        self.puzzle_label.pack(anchor="w")

        controls = ctk.CTkFrame(header, fg_color="transparent")
        controls.grid(row=0, column=2, padx=18, pady=14, sticky="e")
        self.appearance_menu = ctk.CTkOptionMenu(
            controls,
            values=["Dark", "Light"],
            command=self._change_appearance_mode,
            width=100,
            corner_radius=0,
            fg_color=theme.PANEL_SOFT,
            button_color=theme.PRIMARY,
            button_hover_color=theme.PRIMARY_HOVER,
            text_color=COLOR_TEXT_MAIN,
        )
        self.appearance_menu.set("Dark")
        self.appearance_menu.pack(side="left", padx=(0, 8))
        self.choose_level_button = ctk.CTkButton(
            controls,
            text="Choose Level",
            width=110,
            corner_radius=0,
            fg_color=theme.PANEL_SOFT,
            hover_color=theme.BORDER,
            text_color=COLOR_TEXT_MAIN,
            command=self._show_level_selector,
        )
        self.choose_level_button.pack(side="left", padx=4)
        ctk.CTkButton(
            controls,
            text="Import Puzzle",
            width=112,
            corner_radius=0,
            fg_color=theme.PANEL_SOFT,
            hover_color=theme.BORDER,
            text_color=COLOR_TEXT_MAIN,
            command=self._import_puzzle,
        ).pack(side="left", padx=4)
        ctk.CTkButton(
            controls,
            text="Restart",
            width=84,
            corner_radius=0,
            fg_color=theme.PANEL_SOFT,
            hover_color=theme.BORDER,
            text_color=COLOR_TEXT_MAIN,
            command=self._restart,
        ).pack(side="left", padx=4)

    def _change_appearance_mode(self, mode: str) -> None:
        ctk.set_appearance_mode(mode)
        self._refresh_all()

    def _build_content(self) -> None:
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.grid(row=1, column=0, padx=18, pady=18, sticky="nsew")
        content.grid_rowconfigure(0, weight=1)
        content.grid_columnconfigure(0, weight=1)
        content.grid_columnconfigure(1, weight=0)

        self.board_panel = ctk.CTkFrame(
            content,
            fg_color=theme.PANEL_BACKGROUND,
            corner_radius=0,
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
            text_color=COLOR_TEXT_MAIN,
            font=ctk.CTkFont(size=16, weight="bold"),
        ).grid(row=0, column=0, sticky="w")
        self.phase_label = ctk.CTkLabel(
            board_head,
            text="",
            corner_radius=0,
            width=92,
            height=26,
            font=ctk.CTkFont(size=11, weight="bold"),
        )
        self.phase_label.grid(row=0, column=1, padx=(8, 6), sticky="e")
        self.progress_label = ctk.CTkLabel(
            board_head,
            text="",
            fg_color=theme.PANEL_SOFT,
            text_color=COLOR_TEXT_MUTED,
            corner_radius=0,
            width=178,
            height=26,
        )
        self.progress_label.grid(row=0, column=2, sticky="e")
        self.progress_bar = ctk.CTkProgressBar(
            board_head,
            height=6,
            corner_radius=0,
            fg_color=theme.PANEL_SOFT,
            progress_color=theme.PRIMARY,
        )
        self.progress_bar.grid(row=1, column=0, columnspan=3, pady=(10, 0), sticky="ew")

        self.board = ctk.CTkFrame(self.board_panel, fg_color="transparent")
        self.board.grid(row=1, column=0, padx=12, pady=(0, 12), sticky="nsew")

        self.sidebar = ctk.CTkScrollableFrame(
            content,
            width=380,
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
            corner_radius=0,
            border_width=1,
            border_color=theme.BORDER,
        )
        panel.grid(row=row, column=0, pady=(0, 10), sticky="ew")
        panel.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            panel,
            text=title,
            text_color=COLOR_TEXT_MAIN,
            font=ctk.CTkFont(size=15, weight="bold"),
        ).grid(row=0, column=0, padx=14, pady=(12, 6), sticky="w")
        return panel

    def _build_sidebar(self) -> None:
        solver = self._panel(0, "Deduction controls")
        solver_buttons = ctk.CTkFrame(solver, fg_color="transparent")
        solver_buttons.grid(row=1, column=0, padx=14, pady=(0, 14), sticky="ew")
        solver_buttons.grid_columnconfigure((0, 1), weight=1)

        self.hint_button = ctk.CTkButton(
            solver_buttons,
            text="Hint",
            corner_radius=0,
            fg_color=theme.PANEL_SOFT,
            hover_color=theme.BORDER,
            text_color=COLOR_TEXT_MAIN,
            command=self._show_hint,
        )
        self.hint_button.grid(row=0, column=0, padx=(0, 4), pady=(0, 8), sticky="ew")

        self.step_button = ctk.CTkButton(
            solver_buttons,
            text="Next Step",
            corner_radius=0,
            fg_color=theme.PANEL_SOFT,
            hover_color=theme.BORDER,
            text_color=COLOR_TEXT_MAIN,
            command=self._solve_one_step,
        )
        self.step_button.grid(row=0, column=1, padx=(4, 0), pady=(0, 8), sticky="ew")

        self.auto_button = ctk.CTkButton(
            solver_buttons,
            text="▶  Auto Solve",
            corner_radius=0,
            fg_color=theme.PRIMARY,
            hover_color=theme.PRIMARY_HOVER,
            text_color=theme.PRIMARY_TEXT,
            font=ctk.CTkFont(weight="bold"),
            command=self._toggle_auto_solve,
        )
        self.auto_button.grid(row=1, column=0, columnspan=2, sticky="ew")

        metrics = self._panel(1, "Solver metrics")
        metrics_grid = ctk.CTkFrame(metrics, fg_color="transparent")
        metrics_grid.grid(row=1, column=0, padx=12, pady=(0, 14), sticky="ew")

        items = [
            ("SAT", "sat"),
            ("Decisions", "dec"),
            ("Propagation", "prop"),
            ("Backtrack", "back"),
            ("Time", "time"),
        ]

        for idx, (title, key) in enumerate(items):
            metrics_grid.grid_columnconfigure(idx, weight=1)

            card = ctk.CTkFrame(
                metrics_grid,
                fg_color=theme.PANEL_SOFT,
                corner_radius=0,
            )
            card.grid(row=0, column=idx, padx=2, sticky="ew")
            card.grid_columnconfigure(0, weight=1)

            title_lbl = ctk.CTkLabel(
                card,
                text=title,
                font=ctk.CTkFont(size=9),
                text_color=COLOR_TEXT_MUTED,
            )
            title_lbl.grid(row=0, column=0, pady=(6, 0))

            val_lbl = ctk.CTkLabel(
                card,
                text="0",
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=COLOR_TEXT_MAIN,
            )
            val_lbl.grid(row=1, column=0, pady=(0, 6))

            self.metric_labels[key] = val_lbl

        trace = self._panel(2, "Deduction trace")
        self.trace_text = ctk.CTkTextbox(
            trace,
            height=380,
            wrap="none",
            corner_radius=0,
            fg_color=theme.PANEL_SOFT,
            text_color=COLOR_TEXT_MAIN,
            font=ctk.CTkFont(family="Consolas", size=11),
        )
        self.trace_text.grid(row=1, column=0, padx=14, pady=(0, 14), sticky="ew")
        self.trace_text.configure(state="disabled")

    def _build_board(self) -> None:
        for widget in self.board.winfo_children():
            widget.destroy()
        self.cards.clear()

        size = self.game_view.size
        previous_size = getattr(self, "_configured_board_size", 0)
        configured_size = max(previous_size, size)

        for column in range(configured_size):
            self.board.grid_columnconfigure(column, weight=0, uniform="")
        for row in range(configured_size):
            self.board.grid_rowconfigure(row, weight=0, uniform="")

        for column in range(size):
            self.board.grid_columnconfigure(column, weight=1, uniform="card_columns")
        for row in range(size):
            self.board.grid_rowconfigure(row, weight=1, uniform="card_rows")
        self._configured_board_size = size

        cells_by_id = {cell.cell_id: cell for cell in self.game_view.cells}
        for row_idx in range(size):
            row = row_idx + 1
            for column in range(size):
                cell_id = f"{chr(ord('A') + column)}{row}"
                cell = cells_by_id.get(cell_id)
                if cell is None:
                    continue
                card = CharacterCard(self.board, cell, self._select_cell, self._select_clue)
                pad_val = 3 if size >= 5 else 5
                card.grid(row=row_idx, column=column, padx=pad_val, pady=pad_val, sticky="nsew")
                self.cards[cell_id] = card

    def _refresh_all(self, *, rebuild_board: bool = False) -> None:
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

        phase_map = {
            GamePhase.READY: ("READY", COLOR_TEXT_MUTED, theme.PANEL_SOFT),
            GamePhase.ACTIVE: ("ACTIVE", theme.PRIMARY, theme.PANEL_SOFT),
            GamePhase.SOLVED: ("SOLVED", theme.SUCCESS, theme.INNOCENT_SOFT),
            GamePhase.STUCK: ("STUCK", theme.WARNING, theme.WARNING_SOFT),
            GamePhase.INCONSISTENT: ("INCONSISTENT", theme.ERROR, theme.CRIMINAL_SOFT),
        }
        phase_text, phase_color, phase_surface = phase_map.get(
            self.game_view.phase, ("READY", COLOR_TEXT_MUTED, theme.PANEL_SOFT)
        )

        self.phase_label.configure(
            text=phase_text,
            text_color=phase_color,
            fg_color=phase_surface,
        )

        if self.game_view.phase == GamePhase.SOLVED:
            self.selected_cell_id = None
            self.highlighted_color_map.clear()
            has_active_focus = False
        else:
            selected_cell = self._selected_cell()
            has_active_focus = (
                bool(self.highlighted_color_map)
                or (selected_cell is not None and selected_cell.revealed)
            )

        by_id = {cell.cell_id: cell for cell in self.game_view.cells}

        for cell_id, card in self.cards.items():
            if cell_id in by_id:
                is_highlighted = cell_id in self.highlighted_color_map
                is_selected = cell_id == self.selected_cell_id
                is_dimmed = has_active_focus and (not is_selected) and (not is_highlighted)

                card.update_view(
                    by_id[cell_id],
                    selected=is_selected,
                    highlight_color=self.highlighted_color_map.get(cell_id),
                    is_dimmed=is_dimmed,
                    board_size=self.game_view.size,
                )

        self._refresh_metrics()
        self._refresh_trace()
        self._refresh_controls()

    def _selected_cell(self) -> CellView | None:
        return next(
            (cell for cell in self.game_view.cells if cell.cell_id == self.selected_cell_id),
            None,
        )

    def _clear_selection(self) -> None:
        self.selected_cell_id = None
        self.highlighted_color_map.clear()
        self._refresh_all()

    def _select_cell(self, cell_id: str) -> None:
        if self._ignore_clicks:
            return

        if self.selected_cell_id == cell_id:
            self._clear_selection()
            return

        self.selected_cell_id = cell_id
        self.highlighted_color_map.clear()
        self._refresh_all()

        cell = self._selected_cell()
        if cell and not cell.revealed and self.game_view.phase is GamePhase.ACTIVE and not self.auto_running:
            VerdictDialog(
                self,
                cell=cell,
                on_submit=lambda status: self._submit_verdict_for(cell_id, status),
                on_cancel=self._clear_selection,
            )

    def _select_clue(self, cell_id: str) -> None:
        """Highlight the exact region referenced by a revealed clue."""
        if self._ignore_clicks:
            return

        cell = next((c for c in self.game_view.cells if c.cell_id == cell_id), None)
        if cell is None or not cell.revealed:
            return

        if self.selected_cell_id == cell_id:
            self._clear_selection()
            return

        self.selected_cell_id = cell_id
        self.highlighted_color_map.clear()

        valid_cell_ids = {item.cell_id for item in self.game_view.cells}
        for referenced_id in cell.clue_references:
            if referenced_id in valid_cell_ids:
                self.highlighted_color_map[referenced_id] = COLOR_RELATION

        self._refresh_all()

    def _submit_verdict_for(self, cell_id: str, status: Status) -> None:
        result = self.gateway.submit_verdict(cell_id, status)
        game_changed = result.code in {
            ActionCode.ACCEPTED,
            ActionCode.SOLVED,
        }

        if not game_changed:
            cell = self._selected_cell()
            if cell:
                ConclusionNotPossibleDialog(
                    self,
                    cell=cell,
                    attempted_status=status,
                    action_code=result.code,
                    message=getattr(result, "message", None),
                    on_cancel=self._clear_selection,
                )
            else:
                self._clear_selection()
        else:
            self._handle_action_result(result, refresh_state=True)

    def _show_hint(self) -> None:
        hint = self.gateway.get_hint()
        self.highlighted_color_map.clear()
        for cid in hint.target_cells:
            self.highlighted_color_map[cid] = COLOR_RELATION
        if hint.clue_source:
            self.selected_cell_id = hint.clue_source

        self._refresh_all()

    def _solve_one_step(self) -> None:
        self._handle_action_result(self.gateway.auto_solve_step())

    def _toggle_auto_solve(self) -> None:
        if self.auto_running:
            self._stop_auto("Auto Solve paused.")
            return
        if self.game_view.phase not in (GamePhase.READY, GamePhase.ACTIVE):
            return
        self.auto_running = True
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
        self._refresh_controls()

    def _restart(self) -> None:
        if not messagebox.askyesno("Restart puzzle", "Reset all current progress?"):
            return
        self._stop_auto()
        result = self.gateway.restart()
        self.selected_cell_id = None
        self.highlighted_color_map.clear()
        self._handle_action_result(result, rebuild_board=True)

    def _show_level_selector(self) -> None:
        levels = self.gateway.list_puzzles()
        if not levels:
            messagebox.showerror("Choose Level", "No built-in puzzle was found.")
            return
        LevelSelectDialog(
            self,
            levels=levels,
            current_puzzle_name=self.game_view.puzzle_name,
            on_select=self._select_level,
        )

    def _select_level(self, option: PuzzleOption) -> None:
        self._load_puzzle_path(option.path)

    def _import_puzzle(self) -> None:
        selected = filedialog.askopenfilename(
            title="Import Griductive puzzle",
            filetypes=[("JSON puzzle", "*.json"), ("All files", "*.*")],
        )
        if not selected:
            return
        self._load_puzzle_path(Path(selected))

    def _load_puzzle_path(self, path: Path) -> None:
        self._stop_auto()
        result = self.gateway.load_puzzle(path)
        if result.code is ActionCode.ERROR:
            messagebox.showerror("Load puzzle", result.message)
            return
        self.selected_cell_id = None
        self.highlighted_color_map.clear()
        self._handle_action_result(result, rebuild_board=True)

    def _handle_action_result(
        self,
        result: ActionResult,
        *,
        rebuild_board: bool = False,
        refresh_state: bool = True,
    ) -> None:
        if refresh_state or result.highlighted_cells:
            self.highlighted_color_map.clear()
            for cid in result.highlighted_cells:
                self.highlighted_color_map[cid] = COLOR_RELATION
        if result.cell_id:
            self.selected_cell_id = result.cell_id

        self._refresh_all(rebuild_board=rebuild_board)

    def _refresh_metrics(self) -> None:
        m = self.game_view.metrics
        if m and "sat" in self.metric_labels:
            self.metric_labels["sat"].configure(text=str(m.sat_calls))
            self.metric_labels["dec"].configure(text=str(m.decisions))
            self.metric_labels["prop"].configure(text=str(m.propagations))
            self.metric_labels["back"].configure(text=str(m.backtracks))
            self.metric_labels["time"].configure(text=f"{m.runtime_ms:.4f}ms")

    @staticmethod
    def _format_trace_entry(entry: TraceEntry) -> str:
        msg = entry.message or ""
        msg = msg.replace(" was proved ", " proved ").replace("; its clue joined the KB.", "")

        if entry.step == 0:
            lines = [f"[STEP {entry.step:02d}] {msg}"]
            if entry.active_clue_ids:
                lines.append(f"  └── Active: {', '.join(entry.active_clue_ids)}")
            return "\n".join(lines)

        lines = [f"[STEP {entry.step:02d}] {msg}"]

        if entry.sat_queries:
            queries_str = " | ".join(entry.sat_queries)
            queries_str = queries_str.replace(" and not ", " ∧ ¬").replace(" and ", " ∧ ")
            lines.append(f"  ├── SAT Query : {queries_str}")

        if entry.verdict:
            lines.append(f"  ├── Verdict   : {entry.verdict}")

        if entry.revealed_clue_id:
            clue_label = entry.revealed_clue_id
            if entry.revealed_clue_type:
                clue_label += f" [{entry.revealed_clue_type}]"
            has_details = bool(
                entry.revealed_clue_text or entry.revealed_clue_references
            )
            branch = "├──" if has_details else "└──"
            lines.append(f"  {branch} KB Update : + {clue_label}")
            if entry.revealed_clue_text:
                text_branch = (
                    "│  " if entry.revealed_clue_references else "└──"
                )
                lines.append(
                    f"  {text_branch} Clue      : {entry.revealed_clue_text}"
                )
            if entry.revealed_clue_references:
                references = ", ".join(entry.revealed_clue_references)
                lines.append(f"  └── References: {references}")

        return "\n".join(lines)

    def _refresh_trace(self) -> None:
        content = "\n\n".join(self._format_trace_entry(entry) for entry in self.game_view.trace)
        self.trace_text.configure(state="normal")
        self.trace_text.delete("1.0", "end")
        self.trace_text.insert("1.0", content or "No deduction step yet.")
        self.trace_text.see("end")
        self.trace_text.configure(state="disabled")

    def _refresh_controls(self) -> None:
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
            text_color="#ffffff" if self.auto_running else theme.PRIMARY_TEXT,
        )

    def _bind_shortcuts(self) -> None:
        for modifier in ("Control", "Command"):
            self.bind(f"<{modifier}-l>", lambda _event: self._show_level_selector())
            self.bind(f"<{modifier}-o>", lambda _event: self._import_puzzle())
            self.bind(f"<{modifier}-r>", lambda _event: self._restart())
        self.bind("<Key-h>", lambda _event: self._show_hint())

    def _on_close(self) -> None:
        self._stop_auto()
        self.destroy()


def run_app(gateway: GameGateway | None = None) -> None:
    app = GriductiveApp(gateway=gateway)
    app.mainloop()


if __name__ == "__main__":
    run_app()
