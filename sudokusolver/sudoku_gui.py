#!/usr/bin/env python3
"""
sudoku_gui.py — Pygame GUI for the Sudoku Tutor

Keys (solve mode):
    SPACE / →        next step          ← / BACKSPACE    previous step
    A                toggle auto-play   C                toggle candidates
    R                reset to step 0    D                toggle dark mode
    H                progressive hint   P                enter play mode
    1–9              digit filter       0                clear filter
    Ctrl+E           export PNG         I                enter input mode
    ESC              quit

Keys (input mode):
    1–9  set digit   0/Del  clear cell   Arrows  move   X  clear all
    Ctrl+Z  undo     Ctrl+Y  redo        Enter  solve    ESC  cancel

Keys (play mode):
    1–9  fill digit / toggle mark (in mark mode)
    0/Del  erase / clear marks   Arrows  move   H  hint
    M    toggle fill/mark mode   K  clear all user marks
    C    toggle candidates       ESC  exit play mode

Drop an image file onto the window to extract a puzzle via Claude API.
Right-click any cell (solve mode): toggle pencilmarks
"""

import sys, json, os, threading
from copy import deepcopy
from pathlib import Path

import pygame

from sudoku_tutor import (
    Grid, Step, ALL_STRATEGIES, DEFAULT_PUZZLE, read_puzzle,
)

# ── Optional imports ──────────────────────────────────────────────────────────
try:
    from puzzles import PUZZLES, get_puzzles_by_tier, get_all_tiers
    HAS_PUZZLES = True
except ImportError:
    PUZZLES, HAS_PUZZLES = [], False

try:
    from sudoku_generator import generate_puzzle
    HAS_GENERATOR = True
except ImportError:
    HAS_GENERATOR = False

try:
    import anthropic as _anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

try:
    from PIL import Image as _PILImage, ImageGrab as _ImageGrab
    import base64 as _base64, io as _io
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# ── Clipboard helper ──────────────────────────────────────────────────────────
def _get_clipboard() -> str:
    try:
        import subprocess
        if sys.platform == "darwin":
            return subprocess.run(["pbpaste"], capture_output=True, text=True).stdout
        elif sys.platform == "win32":
            import ctypes
            ctypes.windll.user32.OpenClipboard(0)
            handle = ctypes.windll.user32.GetClipboardData(1)
            data = ctypes.c_char_p(handle).value or b""
            ctypes.windll.user32.CloseClipboard()
            return data.decode("utf-8", errors="ignore")
        else:
            for cmd in (["xclip", "-selection", "clipboard", "-o"], ["xsel", "-bo"]):
                r = subprocess.run(cmd, capture_output=True, text=True)
                if r.returncode == 0:
                    return r.stdout
    except Exception:
        pass
    return ""

# ── Config ────────────────────────────────────────────────────────────────────
CONFIG_PATH = Path.home() / ".sudokurc"

def load_config() -> dict:
    defaults = {
        "dark_mode": False,
        "show_candidates": True,
        "auto_interval": 1000,
        "last_puzzle": "sd0.txt",
        "anthropic_api_key": "",
    }
    try:
        with open(CONFIG_PATH) as f:
            return {**defaults, **json.load(f)}
    except Exception:
        return defaults

def save_config(cfg: dict):
    try:
        with open(CONFIG_PATH, "w") as f:
            json.dump(cfg, f, indent=2)
    except Exception:
        pass

# ── Layout ────────────────────────────────────────────────────────────────────
MARGIN      = 16
CELL_SIZE   = 64
GRID_PX     = 576           # 9 × 64
PANEL_W     = 320
BTN_H       = 34
TIMELINE_H  = 12

GRID_X      = MARGIN
GRID_Y      = MARGIN
PANEL_X     = GRID_X + GRID_PX + MARGIN          # 608
TIMELINE_Y  = GRID_Y + GRID_PX + MARGIN          # 608
BTN_Y       = TIMELINE_Y + TIMELINE_H + 8        # 628
WIN_W       = PANEL_X + PANEL_W + MARGIN          # 944
WIN_H       = BTN_Y + BTN_H + MARGIN              # 680

SUBCELL_W   = CELL_SIZE // 3
SUBCELL_H   = CELL_SIZE // 3
PANEL_SURF_H = 1400

# ── Colour palettes ───────────────────────────────────────────────────────────
LIGHT: dict = {
    "bg":           (240, 240, 235),
    "given_bg":     (215, 228, 248),
    "given_fg":     ( 10,  40, 120),
    "solved_fg":    ( 30,  30,  30),
    "cand_fg":      (120, 120, 120),
    "elim_cand":    (220,  60,  60),
    "place_bg":     (160, 240, 160),
    "elim_bg":      (255, 220, 180),
    "pattern_bg":   (180, 235, 255),
    "house_bg":     (255, 252, 200),
    "selected":     (190, 220, 255),
    "peer_bg":      (228, 234, 245),
    "conflict_bg":  (255, 155, 155),
    "filter_hi":    (255, 248, 190),
    "filter_dim":   (210, 208, 200),
    "grid_thin":    ( 80,  80,  80),
    "grid_thick":   ( 20,  20,  20),
    "panel_bg":     (255, 255, 255),
    "panel_line":   (200, 200, 200),
    "btn":          ( 70, 130, 180),
    "btn_hover":    (100, 160, 210),
    "btn_on":       ( 60, 150,  60),
    "btn_on_hov":   ( 80, 180,  80),
    "btn_danger":   (180,  60,  60),
    "btn_danger_h": (210,  80,  80),
    "btn_text":     (255, 255, 255),
    "warn":         (200,  60,  60),
    "ok":           (  0, 140,  60),
    "accent":       (180,  80,   0),
    "brute_fg":     (120,  50, 180),
    "play_fg":      (  0, 130,  80),
    "play_err":     (200,  30,  30),
    "hint_bg":      (255, 255, 210),
    "timeline_bg":  (210, 210, 205),
    "timeline_fg":  ( 70, 130, 180),
    "scrollbar":    (150, 150, 150),
    "strategy_fg":  ( 60, 100, 180),
}
DARK: dict = {
    "bg":           ( 28,  28,  32),
    "given_bg":     ( 38,  52,  88),
    "given_fg":     (140, 170, 255),
    "solved_fg":    (220, 220, 220),
    "cand_fg":      (130, 130, 145),
    "elim_cand":    (255,  80,  80),
    "place_bg":     ( 35, 105,  45),
    "elim_bg":      (120,  75,  20),
    "pattern_bg":   ( 25,  85, 125),
    "house_bg":     ( 85,  80,  25),
    "selected":     ( 45,  75, 145),
    "peer_bg":      ( 42,  52,  72),
    "conflict_bg":  (120,  28,  28),
    "filter_hi":    ( 75,  70,  25),
    "filter_dim":   ( 38,  38,  42),
    "grid_thin":    ( 90,  90,  95),
    "grid_thick":   (185, 185, 185),
    "panel_bg":     ( 36,  36,  42),
    "panel_line":   ( 68,  68,  80),
    "btn":          ( 45,  88, 138),
    "btn_hover":    ( 65, 118, 168),
    "btn_on":       ( 28, 108,  42),
    "btn_on_hov":   ( 40, 138,  58),
    "btn_danger":   (135,  38,  38),
    "btn_danger_h": (165,  58,  58),
    "btn_text":     (228, 228, 228),
    "warn":         (255,  80,  80),
    "ok":           ( 45, 195,  75),
    "accent":       (215, 128,  38),
    "brute_fg":     (175, 115, 255),
    "play_fg":      ( 45, 195, 115),
    "play_err":     (255,  70,  70),
    "hint_bg":      ( 55,  55,  18),
    "timeline_bg":  ( 52,  52,  58),
    "timeline_fg":  ( 55, 125, 195),
    "scrollbar":    ( 95,  95, 108),
    "strategy_fg":  ( 90, 145, 230),
}

# ── Strategy tier ─────────────────────────────────────────────────────────────
STRATEGY_TIER: dict[str, int] = {
    "Full House": 1, "Naked Single": 1, "Hidden Single": 1,
    "Naked Pair": 2, "Hidden Pair": 2, "Naked Triple": 2,
    "Hidden Triple": 2, "Naked Quad": 2, "Hidden Quad": 2,
    "Pointing Pairs": 2, "Box-Line Reduction": 2,
    "X-Wing": 3, "Swordfish": 3, "Jellyfish": 3, "Squirmbag": 3, "Y-Wing": 3, "XYZ-Wing": 3,
    "Simple Coloring": 3,
    "Unique Rectangle": 4, "W-Wing": 4, "Skyscraper": 4,
    "2-String Kite": 4, "BUG+1": 4,
    "Finned X-Wing": 5, "XY-Chain": 5,
}

# ── Button bar ────────────────────────────────────────────────────────────────
BUTTONS = [
    {"id": "prev",   "label": "< PREV"},
    {"id": "next",   "label": "NEXT >"},
    {"id": "auto",   "label": "> AUTO",  "toggle": True},
    {"id": "reset",  "label": "RESET"},
    {"id": "cands",  "label": "CANDS",   "toggle": True},
    {"id": "input",  "label": "INPUT",   "toggle": True},
    {"id": "play",   "label": "PLAY",    "toggle": True},
    {"id": "create", "label": "CREATE",  "toggle": True},
    {"id": "puzzle", "label": "PUZZLE"},
    {"id": "load",   "label": "LOAD"},
    {"id": "save",   "label": "SAVE"},
    {"id": "apikey", "label": "API KEY"},
]

# ── Backtracking solver ───────────────────────────────────────────────────────
def _bt_candidates(grid: list[list[int]], r: int, c: int) -> set[int]:
    used: set[int] = set()
    for cc in range(9): used.add(grid[r][cc])
    for rr in range(9): used.add(grid[rr][c])
    br, bc = (r // 3) * 3, (c // 3) * 3
    for dr in range(3):
        for dc in range(3):
            used.add(grid[br+dr][bc+dc])
    return set(range(1, 10)) - used

def _bt_solve(grid: list[list[int]], _iters: list[int] | None = None) -> list[list[int]] | None:
    if _iters is not None:
        _iters[0] += 1
    best_r, best_c, best_cands = -1, -1, None
    for r in range(9):
        for c in range(9):
            if grid[r][c] == 0:
                cands = _bt_candidates(grid, r, c)
                if not cands:
                    return None
                if best_cands is None or len(cands) < len(best_cands):
                    best_r, best_c, best_cands = r, c, cands
                    if len(best_cands) == 1:
                        break
        if best_cands and len(best_cands) == 1:
            break
    if best_r == -1:
        return grid
    for d in sorted(best_cands):   # type: ignore[arg-type]
        grid[best_r][best_c] = d
        result = _bt_solve([row[:] for row in grid], _iters)
        if result is not None:
            return result
        grid[best_r][best_c] = 0
    return None

# ── Board validation ──────────────────────────────────────────────────────────
def validate_board(values: list[list[int]]) -> set[tuple[int, int]]:
    conflicts: set[tuple[int, int]] = set()
    for r in range(9):
        seen: dict[int, int] = {}
        for c in range(9):
            v = values[r][c]
            if v:
                if v in seen:
                    conflicts.add((r, c)); conflicts.add((r, seen[v]))
                else:
                    seen[v] = c
    for c in range(9):
        seen = {}
        for r in range(9):
            v = values[r][c]
            if v:
                if v in seen:
                    conflicts.add((r, c)); conflicts.add((seen[v], c))
                else:
                    seen[v] = r
    for box in range(9):
        seen_cell: dict[int, tuple[int, int]] = {}
        for r, c in Grid.cells_of_box(box):
            v = values[r][c]
            if v:
                if v in seen_cell:
                    conflicts.add((r, c)); conflicts.add(seen_cell[v])
                else:
                    seen_cell[v] = (r, c)
    return conflicts

# ── Font loader ───────────────────────────────────────────────────────────────
def _load_fonts() -> dict:
    mono_names = ["menlo", "couriernew", "andalemono", "dejavusansmono", "monospace"]
    mono = None
    for name in mono_names:
        f = pygame.font.match_font(name)
        if f:
            mono = f
            break
    def make(size):
        return pygame.font.Font(mono, size) if mono else pygame.font.Font(None, size+6)
    return {
        "digit":       make(34),
        "cand":        make(13),
        "panel_title": make(17),
        "panel_body":  make(13),
        "btn":         make(13),
        "small":       make(11),
    }

def _make_icon() -> pygame.Surface:
    """Return a 64×64 surface that looks like a partially-filled Sudoku grid."""
    SIZE = 64
    PAD  = 4
    CELL = (SIZE - 2 * PAD) // 9   # 6 px per cell

    BG         = ( 18,  26,  46)   # dark navy background
    CELL_BG    = ( 28,  42,  72)   # cell interior
    THIN_LINE  = ( 80,  95, 130)   # minor grid lines
    THICK_LINE = (200, 210, 240)   # box / border lines
    FILLED     = ( 55, 105, 190)   # solved / pencilmark cell
    GIVEN      = (210, 160,  40)   # given (gold) cell

    surf = pygame.Surface((SIZE, SIZE))
    surf.fill(BG)

    # Cell interiors
    for r in range(9):
        for c in range(9):
            pygame.draw.rect(
                surf, CELL_BG,
                (PAD + c * CELL + 1, PAD + r * CELL + 1, CELL - 1, CELL - 1),
            )

    # A sparse but plausible given/filled pattern
    givens = {(0, 0), (0, 5), (2, 3), (4, 4), (6, 1), (6, 7), (8, 4), (8, 8)}
    filled = {
        (0, 2), (0, 7), (1, 4), (1, 6),
        (3, 1), (3, 5), (3, 8),
        (5, 0), (5, 3), (5, 7),
        (7, 2), (7, 5), (8, 0),
    }
    for r, c in givens:
        pygame.draw.rect(
            surf, GIVEN,
            (PAD + c * CELL + 1, PAD + r * CELL + 1, CELL - 1, CELL - 1),
        )
    for r, c in filled:
        pygame.draw.rect(
            surf, FILLED,
            (PAD + c * CELL + 1, PAD + r * CELL + 1, CELL - 1, CELL - 1),
        )

    # Grid lines (thick at box boundaries, thin elsewhere)
    for i in range(10):
        is_box  = (i % 3 == 0)
        colour  = THICK_LINE if is_box else THIN_LINE
        width   = 2          if is_box else 1
        px = PAD + i * CELL
        pygame.draw.line(surf, colour, (PAD, px),  (PAD + 9 * CELL, px),  width)
        pygame.draw.line(surf, colour, (px,  PAD), (px, PAD + 9 * CELL),  width)

    return surf


# ── Rate puzzle difficulty ────────────────────────────────────────────────────
def rate_puzzle(steps: list[Step]) -> int:
    if not steps:
        return 0
    return max(STRATEGY_TIER.get(s.strategy, 0) for s in steps)


# ─────────────────────────────────────────────────────────────────────────────
# Main application
# ─────────────────────────────────────────────────────────────────────────────

class SudokuApp:
    """Pygame Sudoku tutor GUI."""

    def __init__(self, puzzle_file: str | None = None):
        pygame.init()
        self.screen = pygame.display.set_mode((WIN_W, WIN_H))
        pygame.display.set_caption("Sudoku Tutor")
        pygame.display.set_icon(_make_icon())
        self.clock  = pygame.time.Clock()
        self.fonts  = _load_fonts()

        cfg = load_config()

        # ── Solver state ──────────────────────────────────────────────────────
        self.initial_values:  list[list[int]] = []
        self.grid_states:     list[Grid]      = []
        self.steps:           list[Step]      = []
        self.step_idx:        int             = 0
        self.highlight:       dict            = {}
        self.elim_set:        set             = set()
        self.conflict_cells:  set             = set()
        self.show_candidates: bool            = cfg.get("show_candidates", True)
        self.auto_play:       bool            = False
        self.auto_interval:   int             = cfg.get("auto_interval", 1000)
        self.auto_timer:      int             = 0
        self.stuck:           bool            = False
        self.difficulty:      int             = 0       # max tier used
        self.brute_force_grid:  list[list[int]] | None = None
        self.brute_force_iters: int                   = 0

        # ── Async computation ─────────────────────────────────────────────────
        self._computing:       bool = False
        self._compute_ready:   bool = False   # set by thread when done

        # ── UI state ──────────────────────────────────────────────────────────
        self.dark_mode:       bool            = cfg.get("dark_mode", False)
        self.mode:            str             = "solve"   # solve | input | play | create
        self.input_values:    list[list[int]] | None = None
        self.input_history:   list            = []    # for undo
        self.input_future:    list            = []    # for redo
        self.selected:        tuple | None    = None
        self.panel_scroll:    int             = 0
        self.filter_digit:    int             = 0     # 0=off, 1-9=filter

        # pencilmark overrides: user_cands[(r,c)] = set of toggled digits
        self.user_cands:      dict           = {}

        # ── Create mode ───────────────────────────────────────────────────────
        self.create_values:   list[list[int]] | None = None
        self.create_history:  list            = []
        self.create_future:   list            = []

        # ── Play mode ─────────────────────────────────────────────────────────
        self.play_values:     list[list[int]] | None = None
        self.play_solution:   list[list[int]] | None = None
        self.hint_level:      int             = 0    # 0=none shown; advances 0→4→0
        self.hint_step_idx:   int             = -1   # which step hint refers to
        self.play_user_cands: dict            = {}   # (r,c) -> set of user-entered candidates
        self.play_cand_mode:  bool            = False # True=mark mode, False=fill mode

        # ── Claude API ────────────────────────────────────────────────────────
        self.anthropic_api_key: str = (
            cfg.get("anthropic_api_key") or os.environ.get("ANTHROPIC_API_KEY", "")
        )

        self.btn_rects: dict = {}
        self._compute_btn_rects()

        # ── Load puzzle ───────────────────────────────────────────────────────
        source = puzzle_file or cfg.get("last_puzzle", "sd0.txt")
        vals = read_puzzle(source) if source else None
        if vals:
            print(f"Loaded: {source}")
            self.load_puzzle(vals)
        else:
            print("Using built-in default puzzle.")
            self.load_puzzle(DEFAULT_PUZZLE)

    # ──────────────────────────────────────────────────────────────────────────
    # Palette shortcut
    # ──────────────────────────────────────────────────────────────────────────

    @property
    def p(self) -> dict:
        return DARK if self.dark_mode else LIGHT

    # ──────────────────────────────────────────────────────────────────────────
    # Layout helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _compute_btn_rects(self):
        n   = len(BUTTONS)
        avail = WIN_W - 2 * MARGIN
        gap   = 4
        btn_w = (avail - gap * (n - 1)) // n
        x = MARGIN
        for btn in BUTTONS:
            self.btn_rects[btn["id"]] = pygame.Rect(x, BTN_Y, btn_w, BTN_H)
            x += btn_w + gap

    def _cell_rect(self, r: int, c: int) -> pygame.Rect:
        return pygame.Rect(GRID_X + c * CELL_SIZE, GRID_Y + r * CELL_SIZE,
                           CELL_SIZE, CELL_SIZE)

    def _is_peer_of_selected(self, r: int, c: int) -> bool:
        if self.selected is None:
            return False
        sr, sc = self.selected
        if (r, c) == (sr, sc):
            return False
        return r == sr or c == sc or Grid.box_of(r, c) == Grid.box_of(sr, sc)

    # ──────────────────────────────────────────────────────────────────────────
    # Puzzle loading / step computation
    # ──────────────────────────────────────────────────────────────────────────

    def load_puzzle(self, values: list[list[int]]):
        self.initial_values = [row[:] for row in values]
        self.user_cands     = {}
        self.compute_all_steps_async()

    def compute_all_steps_async(self):
        """Run compute_all_steps in a background thread."""
        self.steps        = []
        self.grid_states  = []
        self.stuck        = False
        self.difficulty   = 0
        self._computing   = True
        self._compute_ready = False
        self.brute_force_grid = None
        self.conflict_cells   = set()
        self.highlight    = {}
        self.elim_set     = set()
        self.step_idx     = 0
        self.panel_scroll = 0
        t = threading.Thread(target=self._compute_worker, daemon=True)
        t.start()

    def _compute_worker(self):
        """Run in background thread: compute all steps, set flag when done."""
        steps: list[Step] = []
        stuck = False
        grid_states: list[Grid] = []
        conflict_cells: set = set()

        init_conflicts = validate_board(self.initial_values)
        if init_conflicts:
            conflict_cells = init_conflicts
            grid_states    = [Grid(self.initial_values)]
            stuck          = True
        else:
            grid = Grid(self.initial_values)
            grid_states = [deepcopy(grid)]
            while not grid.is_solved():
                step = None
                for _, fn in ALL_STRATEGIES:
                    step = fn(grid)
                    if step:
                        break
                if step is None:
                    stuck = True
                    break
                steps.append(step)
                grid.apply_step(step)
                conflicts = validate_board(grid.values)
                if conflicts:
                    conflict_cells = conflicts
                    grid_states.append(deepcopy(grid))
                    stuck = True
                    break
                grid_states.append(deepcopy(grid))

        self.steps           = steps
        self.grid_states     = grid_states
        self.stuck           = stuck
        self.conflict_cells  = conflict_cells
        self.difficulty      = rate_puzzle(steps)
        self._computing      = False
        self._compute_ready  = True

        msg = "STUCK" if stuck else "Solved!"
        print(f"Computed {len(steps)} steps. {msg} Difficulty: Tier {self.difficulty}")

    def _check_compute_ready(self):
        """Call from main loop; applies results when background thread finishes."""
        if self._compute_ready:
            self._compute_ready = False
            self.go_to_step(0)

    # ──────────────────────────────────────────────────────────────────────────
    # Navigation
    # ──────────────────────────────────────────────────────────────────────────

    def go_to_step(self, idx: int):
        self.brute_force_grid = None
        self.panel_scroll     = 0
        self.hint_level       = 0
        self.step_idx = max(0, min(idx, len(self.steps)))
        if self.step_idx > 0:
            step = self.steps[self.step_idx - 1]
            self.highlight = self._build_highlight(step)
            self.elim_set  = {(r, c, d) for r, c, d in step.eliminations}
        else:
            self.highlight = {}
            self.elim_set  = set()
        self.conflict_cells = validate_board(
            self.grid_states[self.step_idx].values)

    def _build_highlight(self, step: Step) -> dict:
        h: dict = {}
        if step.house_type and step.house_index >= 0:
            if step.house_type == "row":
                cells = [(step.house_index, c) for c in range(9)]
            elif step.house_type == "col":
                cells = [(r, step.house_index) for r in range(9)]
            else:
                cells = Grid.cells_of_box(step.house_index)
            for rc in cells:
                h[rc] = "house"
        for rc in step.pattern_cells:
            if h.get(rc) in (None, "house"):
                h[rc] = "pattern"
        for r, c, _d in step.eliminations:
            if h.get((r, c)) in (None, "house", "pattern"):
                h[(r, c)] = "elim"
        for r, c, _d in step.placements:
            h[(r, c)] = "place"
        return h

    # ──────────────────────────────────────────────────────────────────────────
    # Drawing
    # ──────────────────────────────────────────────────────────────────────────

    def draw(self):
        self.screen.fill(self.p["bg"])
        self.draw_grid()
        self.draw_panel()
        self.draw_timeline()
        self.draw_buttons()
        if self._computing:
            self._draw_computing_overlay()
        pygame.display.flip()

    # ── Grid ──────────────────────────────────────────────────────────────────

    def draw_grid(self):
        for r in range(9):
            for c in range(9):
                self.draw_cell(r, c)
        for i in range(10):
            thick = (i % 3 == 0)
            color = self.p["grid_thick"] if thick else self.p["grid_thin"]
            width = 2 if thick else 1
            y = GRID_Y + i * CELL_SIZE
            pygame.draw.line(self.screen, color,
                             (GRID_X, y), (GRID_X + GRID_PX, y), width)
            x = GRID_X + i * CELL_SIZE
            pygame.draw.line(self.screen, color,
                             (x, GRID_Y), (x, GRID_Y + GRID_PX), width)

    def draw_cell(self, r: int, c: int):
        rect = self._cell_rect(r, c)
        p    = self.p

        # ── Brute-force view ─────────────────────────────────────────────────
        if self.brute_force_grid is not None and self.mode == "solve":
            last = self.grid_states[-1]
            bf_v = self.brute_force_grid[r][c]
            bg   = p["given_bg"] if last.givens[r][c] else p["bg"]
            pygame.draw.rect(self.screen, bg, rect)
            if bf_v:
                color = (p["given_fg"] if last.givens[r][c]
                         else p["solved_fg"] if last.values[r][c] != 0
                         else p["brute_fg"])
                surf = self.fonts["digit"].render(str(bf_v), True, color)
                self.screen.blit(surf, surf.get_rect(center=rect.center))
            return

        # ── Play mode ─────────────────────────────────────────────────────────
        if self.mode == "play" and self.play_values is not None:
            self._draw_cell_play(r, c, rect)
            return

        # ── Background ────────────────────────────────────────────────────────
        if self.mode in ("input", "create"):
            edit_vals = self.input_values if self.mode == "input" else self.create_values
            if (r, c) in self.conflict_cells:
                bg = p["conflict_bg"]
            elif self.selected == (r, c):
                bg = p["selected"]
            elif self._is_peer_of_selected(r, c):
                bg = p["peer_bg"]
            elif edit_vals[r][c] != 0:   # type: ignore[index]
                bg = p["given_bg"]
            else:
                bg = p["bg"]
        else:
            if not self.grid_states:
                pygame.draw.rect(self.screen, p["bg"], rect)
                return
            grid = self.grid_states[self.step_idx]
            if (r, c) in self.conflict_cells:
                bg = p["conflict_bg"]
            else:
                tag = self.highlight.get((r, c))
                if tag == "place":
                    bg = p["place_bg"]
                elif tag == "elim":
                    bg = p["elim_bg"]
                elif tag == "pattern":
                    bg = p["pattern_bg"]
                elif tag == "house":
                    bg = p["house_bg"]
                elif self.selected == (r, c):
                    bg = p["selected"]
                elif self._is_peer_of_selected(r, c):
                    bg = p["peer_bg"]
                elif self.filter_digit and self.mode == "solve":
                    has_d = (grid.values[r][c] == self.filter_digit
                             or (grid.values[r][c] == 0
                                 and self.filter_digit in grid.candidates[r][c]))
                    bg = p["filter_hi"] if has_d else p["filter_dim"]
                elif grid.givens[r][c]:
                    bg = p["given_bg"]
                else:
                    bg = p["bg"]

        pygame.draw.rect(self.screen, bg, rect)

        # ── Content ───────────────────────────────────────────────────────────
        if self.mode in ("input", "create"):
            edit_vals = self.input_values if self.mode == "input" else self.create_values
            v = edit_vals[r][c]   # type: ignore[index]
            if v:
                surf = self.fonts["digit"].render(str(v), True, p["given_fg"])
                self.screen.blit(surf, surf.get_rect(center=rect.center))
        else:
            grid = self.grid_states[self.step_idx]
            v = grid.values[r][c]
            if v:
                color = p["given_fg"] if grid.givens[r][c] else p["solved_fg"]
                surf = self.fonts["digit"].render(str(v), True, color)
                self.screen.blit(surf, surf.get_rect(center=rect.center))
            elif self.show_candidates:
                self.draw_candidates(r, c, rect, grid)

    def _draw_cell_play(self, r: int, c: int, rect: pygame.Rect):
        p = self.p
        initial = Grid(self.initial_values)
        is_given = initial.givens[r][c]
        pv = self.play_values[r][c]        # type: ignore[index]

        if self.selected == (r, c):
            bg = p["selected"]
        elif self._is_peer_of_selected(r, c):
            bg = p["peer_bg"]
        elif is_given:
            bg = p["given_bg"]
        elif pv:
            sol = self.play_solution[r][c] if self.play_solution else None
            bg = p["bg"]  # colored by correctness below
        else:
            bg = p["bg"]
        pygame.draw.rect(self.screen, bg, rect)

        # Mark-mode border on selected cell
        if self.play_cand_mode and self.selected == (r, c):
            pygame.draw.rect(self.screen, p["accent"], rect, 3)

        if pv:
            if is_given:
                color = p["given_fg"]
            elif self.play_solution and pv != self.play_solution[r][c]:
                color = p["play_err"]
            else:
                color = p["play_fg"]
            surf = self.fonts["digit"].render(str(pv), True, color)
            self.screen.blit(surf, surf.get_rect(center=rect.center))
        elif self.show_candidates:
            user_set  = self.play_user_cands.get((r, c))
            cands     = user_set if user_set is not None else _bt_candidates(self.play_values, r, c)  # type: ignore[arg-type]
            is_manual = user_set is not None
            for d in range(1, 10):
                if d in cands:
                    dc = (d - 1) % 3
                    dr = (d - 1) // 3
                    cx = rect.x + dc * SUBCELL_W + SUBCELL_W // 2
                    cy = rect.y + dr * SUBCELL_H + SUBCELL_H // 2
                    color = p["accent"] if is_manual else p["cand_fg"]
                    surf = self.fonts["cand"].render(str(d), True, color)
                    self.screen.blit(surf, surf.get_rect(centerx=cx, centery=cy))

    def draw_candidates(self, r: int, c: int, cell_rect: pygame.Rect,
                        grid: Grid):
        p = self.p
        current_cands = grid.candidates[r][c]
        # Apply user pencilmark overrides (toggle XOR)
        override = self.user_cands.get((r, c), set())
        display_cands = current_cands.symmetric_difference(override)

        prev_cands: set = set()
        if self.step_idx > 0:
            prev_cands = self.grid_states[self.step_idx - 1].candidates[r][c]

        for d in range(1, 10):
            dr = (d - 1) // 3
            dc = (d - 1) % 3
            cx = cell_rect.x + dc * SUBCELL_W + SUBCELL_W // 2
            cy = cell_rect.y + dr * SUBCELL_H + SUBCELL_H // 2

            in_display  = d in display_cands
            in_current  = d in current_cands
            was_in_prev = d in prev_cands
            is_elim     = (r, c, d) in self.elim_set
            is_override = d in override

            if in_display or (is_elim and was_in_prev):
                color = (p["elim_cand"] if is_elim and was_in_prev and not in_current
                         else (p["accent"] if is_override else p["cand_fg"]))
                surf = self.fonts["cand"].render(str(d), True, color)
                self.screen.blit(surf, surf.get_rect(centerx=cx, centery=cy))

    # ── Info panel ────────────────────────────────────────────────────────────

    def draw_panel(self):
        panel_view = pygame.Rect(PANEL_X, GRID_Y, PANEL_W, GRID_PX)
        pygame.draw.rect(self.screen, self.p["panel_bg"], panel_view)

        psurf = pygame.Surface((PANEL_W, PANEL_SURF_H))
        psurf.fill(self.p["panel_bg"])

        x, y = 10, 10
        max_w = PANEL_W - 20

        # Title
        tier_str = f"  Tier {self.difficulty}" if self.difficulty else ""
        title = "SUDOKU TUTOR" + tier_str
        surf = self.fonts["panel_title"].render(title, True, self.p["given_fg"])
        psurf.blit(surf, (x, y))
        y += surf.get_height() + 6
        pygame.draw.line(psurf, self.p["panel_line"], (6, y), (PANEL_W-6, y), 1)
        y += 8

        if self.mode == "input":
            y = self._panel_input(psurf, x, y, max_w)
        elif self.mode == "play":
            y = self._panel_play(psurf, x, y, max_w)
        elif self.mode == "create":
            y = self._panel_create(psurf, x, y, max_w)
        else:
            y = self._panel_solve(psurf, x, y, max_w)

        # Scroll clamping
        content_h  = max(y + 10, GRID_PX)
        max_scroll = max(0, content_h - GRID_PX)
        self.panel_scroll = max(0, min(self.panel_scroll, max_scroll))

        viewport = pygame.Rect(0, self.panel_scroll, PANEL_W, GRID_PX)
        self.screen.blit(psurf, (PANEL_X, GRID_Y), viewport)
        pygame.draw.rect(self.screen, self.p["grid_thin"], panel_view, 1)

        # Scrollbar
        if max_scroll > 0:
            bar_track = GRID_PX - 4
            bar_h = max(18, int(bar_track * GRID_PX / content_h))
            bar_y = GRID_Y + 2 + int((bar_track - bar_h) * self.panel_scroll / max_scroll)
            pygame.draw.rect(self.screen, self.p["scrollbar"],
                             pygame.Rect(PANEL_X + PANEL_W - 5, bar_y, 3, bar_h),
                             border_radius=2)

        # Hint overlay on top
        if self.hint_level > 0 and self.mode == "solve":
            self._draw_hint_overlay()

    def _panel_solve(self, s: pygame.Surface, x: int, y: int, max_w: int) -> int:
        p = self.p

        if self._computing:
            surf = self.fonts["panel_body"].render("Computing steps…", True, p["accent"])
            s.blit(surf, (x, y))
            return y + surf.get_height() + 4

        if self.brute_force_grid is not None:
            surf = self.fonts["panel_title"].render("BRUTE FORCE", True, p["brute_fg"])
            s.blit(surf, (x, y)); y += surf.get_height() + 6
            iters = self.brute_force_iters
            for line in ("Puzzle solved by backtracking.", "",
                         "Purple digits = brute-forced.", "",
                         f"Iterations: {iters:,}", "",
                         "Press PREV to return."):
                if not line:
                    y += 4; continue
                surf = self.fonts["panel_body"].render(line, True, p["solved_fg"])
                s.blit(surf, (x, y)); y += surf.get_height() + 2
            return y

        total = len(self.steps)
        diff_label = f"  (Tier {self.difficulty})" if self.difficulty else ""
        surf = self.fonts["panel_body"].render(
            f"Step {self.step_idx} / {total}{diff_label}", True, p["solved_fg"])
        s.blit(surf, (x, y)); y += surf.get_height() + 6

        if self.conflict_cells:
            n = len(self.conflict_cells)
            surf = self.fonts["panel_body"].render(
                f"CONFLICT: {n} cell(s) violate rules!", True, p["warn"])
            s.blit(surf, (x, y)); y += surf.get_height() + 4
            if self.step_idx == 0:
                surf = self.fonts["panel_body"].render(
                    "Fix the puzzle in INPUT mode.", True, p["cand_fg"])
                s.blit(surf, (x, y)); y += surf.get_height() + 2
            return y

        if self.step_idx == 0:
            if self.stuck:
                surf = self.fonts["panel_body"].render(
                    "STUCK! No strategy found.", True, p["warn"])
                s.blit(surf, (x, y)); y += surf.get_height() + 6
                surf = self.fonts["panel_body"].render(
                    "NEXT to try brute force.", True, p["cand_fg"])
                s.blit(surf, (x, y)); y += surf.get_height() + 2
            else:
                for line in ("Initial puzzle.", "", "SPACE/NEXT to advance.",
                             "C=candidates  D=dark  H=hint",
                             "1–9=digit filter  P=play mode"):
                    if not line:
                        y += 4; continue
                    surf = self.fonts["panel_body"].render(line, True, p["cand_fg"])
                    s.blit(surf, (x, y)); y += surf.get_height() + 2
            return y

        step = self.steps[self.step_idx - 1]

        if self.stuck and self.step_idx == total:
            surf = self.fonts["panel_body"].render(
                "STUCK! No further strategy.", True, p["warn"])
            s.blit(surf, (x, y)); y += surf.get_height() + 2
            surf = self.fonts["panel_body"].render(
                "NEXT to try brute force.", True, p["cand_fg"])
            s.blit(surf, (x, y)); y += surf.get_height() + 6

        surf = self.fonts["panel_title"].render(step.strategy, True, p["strategy_fg"])
        s.blit(surf, (x, y)); y += surf.get_height() + 2

        tier = STRATEGY_TIER.get(step.strategy, "?")
        surf = self.fonts["panel_body"].render(f"Tier {tier}", True, p["cand_fg"])
        s.blit(surf, (x, y)); y += surf.get_height() + 8

        if step.placements:
            surf = self.fonts["panel_body"].render("Placed:", True, p["ok"])
            s.blit(surf, (x, y)); y += surf.get_height() + 2
            for r, c, d in step.placements:
                surf = self.fonts["panel_body"].render(
                    f"  R{r+1}C{c+1} = {d}", True, p["solved_fg"])
                s.blit(surf, (x, y)); y += surf.get_height() + 1

        if step.eliminations:
            y += 4
            surf = self.fonts["panel_body"].render("Eliminated:", True, p["accent"])
            s.blit(surf, (x, y)); y += surf.get_height() + 2
            by_cell: dict = {}
            for r, c, d in step.eliminations:
                by_cell.setdefault((r, c), []).append(d)
            for (r, c), ds in by_cell.items():
                txt = f"  R{r+1}C{c+1}: {{{','.join(str(d) for d in sorted(ds))}}}"
                surf = self.fonts["panel_body"].render(txt, True, p["solved_fg"])
                s.blit(surf, (x, y)); y += surf.get_height() + 1

        y += 8
        pygame.draw.line(s, self.p["panel_line"], (6, y), (PANEL_W-6, y), 1)
        y += 6
        y = self._wrapped(s, step.explanation, x, y, max_w,
                          self.fonts["panel_body"], p["solved_fg"])

        # ── Full step list ─────────────────────────────────────────────────
        y += 12
        pygame.draw.line(s, p["panel_line"], (6, y), (PANEL_W-6, y), 1)
        y += 6
        hdr = self.fonts["small"].render("ALL STEPS", True, p["cand_fg"])
        s.blit(hdr, (x, y)); y += hdr.get_height() + 4

        for i, st in enumerate(self.steps[:self.step_idx]):
            idx = i + 1
            placements = ", ".join(f"R{r+1}C{c+1}={d}" for r, c, d in st.placements)
            line_text = f"{idx:2}. {placements or '—'}  [{st.strategy}]"
            color = p["selected"] if idx == self.step_idx else p["solved_fg"]
            surf = self.fonts["small"].render(line_text, True, color)
            s.blit(surf, (x, y)); y += surf.get_height() + 1

        return y

    def _panel_input(self, s: pygame.Surface, x: int, y: int, max_w: int) -> int:
        p = self.p
        surf = self.fonts["panel_body"].render("INPUT MODE", True, p["accent"])
        s.blit(surf, (x, y)); y += surf.get_height() + 6

        if self.conflict_cells:
            msg = f"  {len(self.conflict_cells)} conflict(s) — fix before solving"
            surf = self.fonts["panel_body"].render(msg, True, p["warn"])
        else:
            surf = self.fonts["panel_body"].render("  Board is valid", True, p["ok"])
        s.blit(surf, (x, y)); y += surf.get_height() + 10
        pygame.draw.line(s, p["panel_line"], (6, y), (PANEL_W-6, y), 1); y += 8

        for text in ["1–9   set digit", "0/Del   clear",
                     "Arrows   move", "X   clear all",
                     "Ctrl+Z/Y   undo/redo",
                     "Enter   solve", "ESC   cancel"]:
            surf = self.fonts["panel_body"].render(text, True, p["solved_fg"])
            s.blit(surf, (x, y)); y += surf.get_height() + 3
        return y

    def _panel_play(self, s: pygame.Surface, x: int, y: int, max_w: int) -> int:
        p = self.p
        surf = self.fonts["panel_title"].render("PLAY MODE", True, p["play_fg"])
        s.blit(surf, (x, y)); y += surf.get_height() + 6

        if self.play_values is not None:
            filled  = sum(1 for r in range(9) for c in range(9)
                          if self.play_values[r][c] != 0
                          and not Grid(self.initial_values).givens[r][c])
            total_e = sum(1 for r in range(9) for c in range(9)
                          if not Grid(self.initial_values).givens[r][c])
            surf = self.fonts["panel_body"].render(
                f"Filled: {filled} / {total_e}", True, p["cand_fg"])
            s.blit(surf, (x, y)); y += surf.get_height() + 8

        # Mode indicator
        mode_label = "MARK MODE  (M to switch)" if self.play_cand_mode else "FILL MODE  (M to switch)"
        mode_color = p["accent"] if self.play_cand_mode else p["play_fg"]
        surf = self.fonts["panel_body"].render(mode_label, True, mode_color)
        s.blit(surf, (x, y)); y += surf.get_height() + 6

        pygame.draw.line(s, p["panel_line"], (6, y), (PANEL_W-6, y), 1); y += 8
        cands_label = "C   hide candidates" if self.show_candidates else "C   show candidates"
        digit_label = "1–9   toggle pencilmark" if self.play_cand_mode else "1–9   fill digit"
        erase_label = "0/Del   clear marks" if self.play_cand_mode else "0/Del   erase"
        for text in [digit_label, erase_label,
                     "Arrows   move", "H   hint",
                     cands_label,
                     "K   clear all user marks",
                     "ESC   exit play mode"]:
            surf = self.fonts["panel_body"].render(text, True, p["solved_fg"])
            s.blit(surf, (x, y)); y += surf.get_height() + 3

        if self.hint_level > 0:
            y += 6
            pygame.draw.line(s, p["panel_line"], (6, y), (PANEL_W-6, y), 1); y += 6
            surf = self.fonts["panel_body"].render(
                f"Hint level {self.hint_level}/4:", True, p["accent"])
            s.blit(surf, (x, y)); y += surf.get_height() + 4
            step = self._hint_step()
            if step:
                hints = self._hint_texts(step)
                for txt in hints[:self.hint_level]:
                    y = self._wrapped(s, txt, x, y, max_w,
                                      self.fonts["panel_body"], p["solved_fg"])
                    y += 2
        return y

    def _draw_hint_overlay(self):
        """Draw hint box on top of the panel (for solve mode H key)."""
        p    = self.p
        step = self._hint_step()
        if step is None:
            return
        hints = self._hint_texts(step)
        lines = hints[:self.hint_level]
        if not lines:
            return

        box_x = PANEL_X + 6
        box_y = GRID_Y + GRID_PX - 120
        box_w = PANEL_W - 12
        box_h = 110

        pygame.draw.rect(self.screen, p["hint_bg"],
                         pygame.Rect(box_x, box_y, box_w, box_h), border_radius=5)
        pygame.draw.rect(self.screen, p["accent"],
                         pygame.Rect(box_x, box_y, box_w, box_h), 1, border_radius=5)

        surf = self.fonts["small"].render(
            f"Hint {self.hint_level}/4 (H=more)", True, p["accent"])
        self.screen.blit(surf, (box_x + 6, box_y + 5))
        y = box_y + 20
        for txt in lines:
            y = self._wrapped(self.screen, txt, box_x + 6, y,
                              box_w - 12, self.fonts["small"], p["solved_fg"])
            y += 2

    def _draw_computing_overlay(self):
        """Dimmed overlay with 'Computing…' while background thread runs."""
        p = self.p
        dim = pygame.Surface((GRID_PX, GRID_PX), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 80))
        self.screen.blit(dim, (GRID_X, GRID_Y))
        surf = self.fonts["panel_title"].render("Computing…", True, p["btn_text"])
        r = surf.get_rect(center=(GRID_X + GRID_PX//2, GRID_Y + GRID_PX//2))
        pygame.draw.rect(self.screen, p["btn"],
                         r.inflate(20, 12), border_radius=6)
        self.screen.blit(surf, r)

    # ── Timeline scrubber ─────────────────────────────────────────────────────

    def draw_timeline(self):
        p = self.p
        total = len(self.steps)
        rect  = pygame.Rect(GRID_X, TIMELINE_Y, GRID_PX, TIMELINE_H)
        pygame.draw.rect(self.screen, p["timeline_bg"], rect, border_radius=4)

        if total > 0:
            fill_w = int(GRID_PX * self.step_idx / total)
            if fill_w > 0:
                pygame.draw.rect(self.screen, p["timeline_fg"],
                                 pygame.Rect(GRID_X, TIMELINE_Y, fill_w, TIMELINE_H),
                                 border_radius=4)
            # Thumb
            tx = GRID_X + fill_w
            thumb = pygame.Rect(tx - 4, TIMELINE_Y - 1, 8, TIMELINE_H + 2)
            pygame.draw.rect(self.screen, p["grid_thick"], thumb, border_radius=3)

        # Tick marks at box boundaries (every 3 steps if total >= 27, else just quarters)
        if total >= 9:
            for i in range(1, total):
                x = GRID_X + int(GRID_PX * i / total)
                if i % max(1, total // 9) == 0:
                    pygame.draw.line(self.screen, p["grid_thin"],
                                     (x, TIMELINE_Y), (x, TIMELINE_Y + TIMELINE_H), 1)

    # ── Button bar ────────────────────────────────────────────────────────────

    def draw_buttons(self):
        p = self.p
        mouse_pos = pygame.mouse.get_pos()
        for btn in BUTTONS:
            bid   = btn["id"]
            rect  = self.btn_rects[bid]
            hover = rect.collidepoint(mouse_pos)

            is_on = ((bid == "auto"   and self.auto_play) or
                     (bid == "cands"  and self.show_candidates) or
                     (bid == "input"  and self.mode == "input") or
                     (bid == "play"   and self.mode == "play") or
                     (bid == "create" and self.mode == "create"))

            if is_on:
                bg = p["btn_on_hov"] if hover else p["btn_on"]
            else:
                bg = p["btn_hover"] if hover else p["btn"]

            pygame.draw.rect(self.screen, bg, rect, border_radius=4)
            surf = self.fonts["btn"].render(btn["label"], True, p["btn_text"])
            self.screen.blit(surf, surf.get_rect(center=rect.center))

        # Filter digit indicator
        if self.filter_digit:
            surf = self.fonts["small"].render(
                f"Filter: {self.filter_digit}", True, self.p["accent"])
            self.screen.blit(surf, (PANEL_X, BTN_Y + BTN_H + 2))

    # ──────────────────────────────────────────────────────────────────────────
    # Event handling
    # ──────────────────────────────────────────────────────────────────────────

    def handle_events(self) -> bool:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            elif event.type == pygame.KEYDOWN:
                if not self.handle_key(event):
                    return False
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    self.handle_click(event.pos)
                elif event.button == 3:
                    self.handle_rightclick(event.pos)
            elif event.type == pygame.MOUSEWHEEL:
                mx, my = pygame.mouse.get_pos()
                if PANEL_X <= mx < PANEL_X + PANEL_W and GRID_Y <= my < GRID_Y + GRID_PX:
                    self.panel_scroll = max(0, self.panel_scroll - event.y * 20)
            elif event.type == pygame.DROPFILE:
                self._handle_dropped_file(event.file)
        return True

    def handle_key(self, event) -> bool:
        mods = pygame.key.get_mods()
        ctrl = mods & pygame.KMOD_CTRL

        # Global shortcuts
        if event.key == pygame.K_ESCAPE and self.mode == "solve":
            return False
        if event.key == pygame.K_d and self.mode == "solve":
            self.dark_mode = not self.dark_mode
            return True
        if event.key == pygame.K_v and (mods & (pygame.KMOD_CTRL | pygame.KMOD_META)):
            self._paste_from_clipboard()
            return True

        if self.mode == "solve":
            return self._key_solve(event, ctrl)
        elif self.mode == "input":
            return self._key_input(event, ctrl)
        elif self.mode == "play":
            return self._key_play(event)
        elif self.mode == "create":
            return self._key_create(event, ctrl)
        return True

    def _key_solve(self, event, ctrl: bool) -> bool:
        k = event.key
        if k in (pygame.K_RIGHT, pygame.K_SPACE):
            if (self.stuck and self.step_idx == len(self.steps)
                    and self.brute_force_grid is None):
                self._offer_brute_force()
            else:
                self.go_to_step(self.step_idx + 1)
        elif k in (pygame.K_LEFT, pygame.K_BACKSPACE):
            self.go_to_step(self.step_idx - 1)
        elif k == pygame.K_a:
            self.auto_play = not self.auto_play
            self.auto_timer = 0
        elif k == pygame.K_c:
            self.show_candidates = not self.show_candidates
        elif k == pygame.K_r:
            self.auto_play = False
            self.go_to_step(0)
        elif k == pygame.K_i:
            self.enter_input_mode()
        elif k == pygame.K_p:
            self.enter_play_mode()
        elif k == pygame.K_h:
            self._advance_hint()
        elif ctrl and k == pygame.K_e:
            self._export_png()
        elif k == pygame.K_0:
            self.filter_digit = 0
        elif event.unicode.isdigit() and event.unicode != "0":
            d = int(event.unicode)
            self.filter_digit = d if self.filter_digit != d else 0
        return True

    def _key_input(self, event, ctrl: bool) -> bool:
        k = event.key
        if k == pygame.K_ESCAPE:
            self.exit_input_mode(solve=False)
        elif k == pygame.K_RETURN:
            self.exit_input_mode(solve=True)
        elif k == pygame.K_x:
            self._clear_all_input()
        elif ctrl and k == pygame.K_z:
            self._undo()
        elif ctrl and k == pygame.K_y:
            self._redo()
        elif k in (pygame.K_DELETE, pygame.K_BACKSPACE):
            if self.selected:
                self._input_push_history()
                r, c = self.selected
                self.input_values[r][c] = 0   # type: ignore[index]
                self._update_input_conflicts()
        elif event.unicode == "0":
            if self.selected:
                self._input_push_history()
                r, c = self.selected
                self.input_values[r][c] = 0   # type: ignore[index]
                self._update_input_conflicts()
                nc = c + 1 if c < 8 else 0
                nr = r + (1 if c == 8 and r < 8 else 0)
                self.selected = (nr, nc)
        elif event.unicode.isdigit() and event.unicode != "0":
            if self.selected:
                self._input_push_history()
                r, c = self.selected
                self.input_values[r][c] = int(event.unicode)  # type: ignore[index]
                self._update_input_conflicts()
                nc = c + 1 if c < 8 else 0
                nr = r + (1 if c == 8 and r < 8 else 0)
                self.selected = (nr, nc)
        elif k == pygame.K_UP:
            if self.selected:
                self.selected = (max(0, self.selected[0]-1), self.selected[1])
        elif k == pygame.K_DOWN:
            if self.selected:
                self.selected = (min(8, self.selected[0]+1), self.selected[1])
        elif k == pygame.K_LEFT:
            if self.selected:
                self.selected = (self.selected[0], max(0, self.selected[1]-1))
        elif k == pygame.K_RIGHT:
            if self.selected:
                self.selected = (self.selected[0], min(8, self.selected[1]+1))
        return True

    def _key_play(self, event) -> bool:
        k = event.key
        if k == pygame.K_ESCAPE:
            self.exit_play_mode()
        elif k == pygame.K_c:
            self.show_candidates = not self.show_candidates
        elif k == pygame.K_h:
            self._advance_hint()
        elif k == pygame.K_m:
            self.play_cand_mode = not self.play_cand_mode
        elif k == pygame.K_k:
            # K = clear all user candidates (revert everything to auto)
            self.play_user_cands.clear()
        elif k in (pygame.K_DELETE, pygame.K_BACKSPACE) or event.unicode == "0":
            if self.selected:
                r, c = self.selected
                initial = Grid(self.initial_values)
                if not initial.givens[r][c]:
                    if self.play_cand_mode:
                        # clear user candidates for this cell → revert to auto
                        self.play_user_cands.pop((r, c), None)
                    else:
                        self.play_values[r][c] = 0   # type: ignore[index]
        elif event.unicode.isdigit() and event.unicode != "0":
            if self.selected:
                r, c = self.selected
                initial = Grid(self.initial_values)
                if not initial.givens[r][c]:
                    if self.play_cand_mode:
                        # toggle pencilmark candidate
                        d = int(event.unicode)
                        cell_cands = self.play_user_cands.setdefault((r, c), set())
                        if d in cell_cands:
                            cell_cands.discard(d)
                        else:
                            cell_cands.add(d)
                        if not cell_cands:
                            del self.play_user_cands[(r, c)]
                    else:
                        self.play_values[r][c] = int(event.unicode)  # type: ignore[index]
                        self.play_user_cands.pop((r, c), None)  # clear marks when filling
                        self._check_play_complete()
                        nc = c + 1 if c < 8 else 0
                        nr = r + (1 if c == 8 and r < 8 else 0)
                        self.selected = (nr, nc)
        elif k == pygame.K_UP:
            if self.selected:
                self.selected = (max(0, self.selected[0]-1), self.selected[1])
        elif k == pygame.K_DOWN:
            if self.selected:
                self.selected = (min(8, self.selected[0]+1), self.selected[1])
        elif k == pygame.K_LEFT:
            if self.selected:
                self.selected = (self.selected[0], max(0, self.selected[1]-1))
        elif k == pygame.K_RIGHT:
            if self.selected:
                self.selected = (self.selected[0], min(8, self.selected[1]+1))
        return True

    def _key_create(self, event, ctrl: bool) -> bool:
        k = event.key
        if k == pygame.K_ESCAPE:
            self.exit_create_mode(None)
        elif k == pygame.K_RETURN:
            if not self.conflict_cells:
                action = self._create_action_dialog()
                if action:
                    self.exit_create_mode(action)
        elif k == pygame.K_x:
            self._create_clear_all()
        elif ctrl and k == pygame.K_z:
            self._create_undo()
        elif ctrl and k == pygame.K_y:
            self._create_redo()
        elif k in (pygame.K_DELETE, pygame.K_BACKSPACE):
            if self.selected:
                self._create_push_history()
                r, c = self.selected
                self.create_values[r][c] = 0   # type: ignore[index]
                self._update_create_conflicts()
        elif event.unicode == "0":
            if self.selected:
                self._create_push_history()
                r, c = self.selected
                self.create_values[r][c] = 0   # type: ignore[index]
                self._update_create_conflicts()
                nc = c + 1 if c < 8 else 0
                nr = r + (1 if c == 8 and r < 8 else 0)
                self.selected = (nr, nc)
        elif event.unicode.isdigit() and event.unicode != "0":
            if self.selected:
                self._create_push_history()
                r, c = self.selected
                self.create_values[r][c] = int(event.unicode)  # type: ignore[index]
                self._update_create_conflicts()
                nc = c + 1 if c < 8 else 0
                nr = r + (1 if c == 8 and r < 8 else 0)
                self.selected = (nr, nc)
        elif k == pygame.K_UP:
            if self.selected:
                self.selected = (max(0, self.selected[0]-1), self.selected[1])
        elif k == pygame.K_DOWN:
            if self.selected:
                self.selected = (min(8, self.selected[0]+1), self.selected[1])
        elif k == pygame.K_LEFT:
            if self.selected:
                self.selected = (self.selected[0], max(0, self.selected[1]-1))
        elif k == pygame.K_RIGHT:
            if self.selected:
                self.selected = (self.selected[0], min(8, self.selected[1]+1))
        return True

    def handle_click(self, pos: tuple):
        # Button bar
        for btn in BUTTONS:
            if self.btn_rects[btn["id"]].collidepoint(pos):
                self._handle_button(btn["id"])
                return
        # Timeline
        tl = pygame.Rect(GRID_X, TIMELINE_Y, GRID_PX, TIMELINE_H + 4)
        if tl.collidepoint(pos) and len(self.steps) > 0:
            frac = (pos[0] - GRID_X) / GRID_PX
            self.go_to_step(round(frac * len(self.steps)))
            return
        # Grid
        gx = pos[0] - GRID_X
        gy = pos[1] - GRID_Y
        if 0 <= gx < GRID_PX and 0 <= gy < GRID_PX:
            self.selected = (gy // CELL_SIZE, gx // CELL_SIZE)

    def handle_rightclick(self, pos: tuple):
        """Right-click toggles pencilmark mode for a cell (solve mode only)."""
        if self.mode != "solve" or self.brute_force_grid is not None:
            return
        gx = pos[0] - GRID_X
        gy = pos[1] - GRID_Y
        if not (0 <= gx < GRID_PX and 0 <= gy < GRID_PX):
            return
        r, c = gy // CELL_SIZE, gx // CELL_SIZE
        if not self.grid_states:
            return
        grid = self.grid_states[self.step_idx]
        if grid.values[r][c] != 0:
            return   # cell already has a value
        self.selected = (r, c)
        # Prompt via digit filter indicator
        d = self.filter_digit
        if d:
            ov = self.user_cands.setdefault((r, c), set())
            if d in ov:
                ov.discard(d)
            else:
                ov.add(d)
            if not ov:
                del self.user_cands[(r, c)]

    def _handle_button(self, bid: str):
        if bid == "prev":
            self.go_to_step(self.step_idx - 1)
        elif bid == "next":
            if (self.stuck and self.step_idx == len(self.steps)
                    and self.brute_force_grid is None):
                self._offer_brute_force()
            else:
                self.go_to_step(self.step_idx + 1)
        elif bid == "auto":
            self.auto_play = not self.auto_play
            self.auto_timer = 0
        elif bid == "reset":
            self.auto_play = False
            self.go_to_step(0)
        elif bid == "cands":
            self.show_candidates = not self.show_candidates
        elif bid == "input":
            if self.mode == "solve":
                self.enter_input_mode()
            else:
                self.exit_input_mode(solve=True)
        elif bid == "play":
            if self.mode == "play":
                self.exit_play_mode()
            else:
                self.enter_play_mode()
        elif bid == "create":
            if self.mode == "create":
                self.exit_create_mode(None)
            else:
                self.enter_create_mode()
        elif bid == "puzzle":
            self._puzzle_library_dialog()
        elif bid == "load":
            self._prompt_load_file()
        elif bid == "save":
            self._prompt_save_file()
        elif bid == "apikey":
            self._prompt_api_key()

    # ──────────────────────────────────────────────────────────────────────────
    # Input mode
    # ──────────────────────────────────────────────────────────────────────────

    def enter_input_mode(self):
        self.mode         = "input"
        self.input_values = [row[:] for row in self.initial_values]
        self.input_history = []
        self.input_future  = []
        self.selected      = (0, 0)
        self.auto_play     = False
        self._update_input_conflicts()

    def exit_input_mode(self, solve: bool = True):
        if solve and self.input_values is not None:
            if self.conflict_cells:
                return
            self.initial_values = [row[:] for row in self.input_values]
            self.mode           = "solve"
            self.selected       = None
            self.input_values   = None
            self.input_history  = []
            self.input_future   = []
            self.user_cands     = {}
            self.compute_all_steps_async()
        else:
            self.mode          = "solve"
            self.selected      = None
            self.input_values  = None
            self.conflict_cells = validate_board(
                self.grid_states[self.step_idx].values)

    def _clear_all_input(self):
        if self.input_values is not None:
            self._input_push_history()
            self.input_values   = [[0]*9 for _ in range(9)]
            self.conflict_cells = set()

    def _update_input_conflicts(self):
        if self.input_values is not None:
            self.conflict_cells = validate_board(self.input_values)

    def _input_push_history(self):
        if self.input_values is not None:
            self.input_history.append(
                ([row[:] for row in self.input_values], self.selected))
            self.input_future.clear()

    def _undo(self):
        if not self.input_history:
            return
        self.input_future.append(
            ([row[:] for row in self.input_values], self.selected))   # type: ignore
        vals, sel = self.input_history.pop()
        self.input_values = vals
        self.selected     = sel
        self._update_input_conflicts()

    def _redo(self):
        if not self.input_future:
            return
        self.input_history.append(
            ([row[:] for row in self.input_values], self.selected))   # type: ignore
        vals, sel = self.input_future.pop()
        self.input_values = vals
        self.selected     = sel
        self._update_input_conflicts()

    # ──────────────────────────────────────────────────────────────────────────
    # Create mode
    # ──────────────────────────────────────────────────────────────────────────

    def enter_create_mode(self):
        self.mode           = "create"
        self.create_values  = [[0]*9 for _ in range(9)]
        self.create_history = []
        self.create_future  = []
        self.selected       = (0, 0)
        self.auto_play      = False
        self.conflict_cells = set()

    def exit_create_mode(self, action: str | None):
        """action: 'play', 'solve', or None (cancel)."""
        if action == "play":
            self.initial_values = [row[:] for row in self.create_values]  # type: ignore
            self.create_values  = None
            self.user_cands     = {}
            self.compute_all_steps_async()
            self.mode           = "solve"
            self.selected       = None
            self.conflict_cells = set()
            self.enter_play_mode()
        elif action == "solve":
            self.initial_values = [row[:] for row in self.create_values]  # type: ignore
            self.create_values  = None
            self.user_cands     = {}
            self.mode           = "solve"
            self.selected       = None
            self.conflict_cells = set()
            self.compute_all_steps_async()
        else:
            self.create_values  = None
            self.mode           = "solve"
            self.selected       = None
            self.conflict_cells = validate_board(
                self.grid_states[self.step_idx].values)

    def _create_clear_all(self):
        self._create_push_history()
        self.create_values  = [[0]*9 for _ in range(9)]
        self.conflict_cells = set()

    def _update_create_conflicts(self):
        if self.create_values is not None:
            self.conflict_cells = validate_board(self.create_values)

    def _create_push_history(self):
        if self.create_values is not None:
            self.create_history.append(
                ([row[:] for row in self.create_values], self.selected))
            self.create_future.clear()

    def _create_undo(self):
        if not self.create_history:
            return
        self.create_future.append(
            ([row[:] for row in self.create_values], self.selected))  # type: ignore
        vals, sel        = self.create_history.pop()
        self.create_values = vals
        self.selected      = sel
        self._update_create_conflicts()

    def _create_redo(self):
        if not self.create_future:
            return
        self.create_history.append(
            ([row[:] for row in self.create_values], self.selected))  # type: ignore
        vals, sel        = self.create_future.pop()
        self.create_values = vals
        self.selected      = sel
        self._update_create_conflicts()

    def _create_action_dialog(self) -> str | None:
        """Three-button dialog: Play / Solve / Cancel. Returns 'play', 'solve', or None."""
        DW, DH = 420, 150
        dx = (WIN_W - DW) // 2
        dy = (WIN_H - DH) // 2

        self.draw()
        background = self.screen.copy()
        dim = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 110))
        background.blit(dim, (0, 0))

        btn_w, btn_h = 110, 32
        gap = 12
        total_w = btn_w * 3 + gap * 2
        bx = dx + (DW - total_w) // 2
        by = dy + DH - btn_h - 16
        play_r   = pygame.Rect(bx,                  by, btn_w, btn_h)
        solve_r  = pygame.Rect(bx + btn_w + gap,    by, btn_w, btn_h)
        cancel_r = pygame.Rect(bx + (btn_w + gap)*2, by, btn_w, btn_h)

        while True:
            self.clock.tick(30)
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    return None
                elif ev.type == pygame.KEYDOWN:
                    if ev.key == pygame.K_ESCAPE:
                        return None
                    elif ev.key == pygame.K_p:
                        return "play"
                    elif ev.key == pygame.K_s:
                        return "solve"
                elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                    if play_r.collidepoint(ev.pos):
                        return "play"
                    if solve_r.collidepoint(ev.pos):
                        return "solve"
                    if cancel_r.collidepoint(ev.pos):
                        return None

            p = self.p
            self.screen.blit(background, (0, 0))
            box = pygame.Rect(dx, dy, DW, DH)
            pygame.draw.rect(self.screen, p["panel_bg"], box, border_radius=6)
            pygame.draw.rect(self.screen, p["grid_thick"], box, 2, border_radius=6)

            surf = self.fonts["panel_title"].render(
                "Puzzle ready — what next?", True, p["given_fg"])
            self.screen.blit(surf, (dx + 14, dy + 12))
            surf = self.fonts["panel_body"].render(
                "P = Play it yourself    S = Let computer solve", True, p["cand_fg"])
            self.screen.blit(surf, (dx + 14, dy + 40))

            mouse = pygame.mouse.get_pos()
            for rect, label, base in (
                (play_r,   "PLAY  (P)",   p["btn_on"]),
                (solve_r,  "SOLVE  (S)",  p["btn"]),
                (cancel_r, "CANCEL",      p["btn"]),
            ):
                r, g, b = base
                bg = (min(r+20,255), min(g+20,255), min(b+20,255)) \
                     if rect.collidepoint(mouse) else base
                pygame.draw.rect(self.screen, bg, rect, border_radius=4)
                s = self.fonts["btn"].render(label, True, p["btn_text"])
                self.screen.blit(s, s.get_rect(center=rect.center))

            pygame.display.flip()

    def _panel_create(self, s: pygame.Surface, x: int, y: int, max_w: int) -> int:
        p = self.p
        surf = self.fonts["panel_body"].render("CREATE MODE", True, p["accent"])
        s.blit(surf, (x, y)); y += surf.get_height() + 6

        filled = sum(1 for r in range(9) for c in range(9)
                     if self.create_values and self.create_values[r][c] != 0)
        surf = self.fonts["panel_body"].render(
            f"  Digits placed: {filled}", True, p["cand_fg"])
        s.blit(surf, (x, y)); y += surf.get_height() + 4

        if self.conflict_cells:
            msg = f"  {len(self.conflict_cells)} conflict(s) — fix before continuing"
            surf = self.fonts["panel_body"].render(msg, True, p["warn"])
        else:
            surf = self.fonts["panel_body"].render("  Board is valid", True, p["ok"])
        s.blit(surf, (x, y)); y += surf.get_height() + 10
        pygame.draw.line(s, p["panel_line"], (6, y), (PANEL_W-6, y), 1); y += 8

        for text in ["1–9   place digit", "0/Del   clear cell",
                     "Arrows   move", "X   clear all",
                     "Ctrl+Z/Y   undo/redo",
                     "Enter   Play or Solve", "ESC   cancel"]:
            surf = self.fonts["panel_body"].render(text, True, p["solved_fg"])
            s.blit(surf, (x, y)); y += surf.get_height() + 3
        return y

    # ──────────────────────────────────────────────────────────────────────────
    # Play mode
    # ──────────────────────────────────────────────────────────────────────────

    def enter_play_mode(self):
        if self._computing:
            return
        self.mode            = "play"
        self.auto_play       = False
        self.selected        = (0, 0)
        self.hint_level      = 0
        self.play_values     = [row[:] for row in self.initial_values]
        self.play_user_cands = {}
        self.play_cand_mode  = False
        # Compute solution for validation
        sol = _bt_solve([row[:] for row in self.initial_values])
        self.play_solution = sol

    def exit_play_mode(self):
        self.mode            = "solve"
        self.play_values     = None
        self.play_solution   = None
        self.selected        = None
        self.hint_level      = 0
        self.play_user_cands = {}
        self.play_cand_mode  = False
        self.conflict_cells = validate_board(
            self.grid_states[self.step_idx].values)

    def _check_play_complete(self):
        if (self.play_values is not None and self.play_solution is not None
                and self.play_values == self.play_solution):
            self._confirm_dialog("Congratulations!",
                                 "You solved the puzzle! Press OK to continue.")

    # ──────────────────────────────────────────────────────────────────────────
    # Progressive hint
    # ──────────────────────────────────────────────────────────────────────────

    def _hint_step(self) -> Step | None:
        """Return the next unsolved step relevant to current display."""
        if self.mode == "play":
            # Find the first step whose placement or elimination isn't yet filled in
            for step in self.steps:
                for r, c, d in step.placements:
                    pv = self.play_values[r][c] if self.play_values else 0
                    if pv != d:
                        return step
            return self.steps[0] if self.steps else None
        else:
            if self.step_idx < len(self.steps):
                return self.steps[self.step_idx]
            return None

    def _hint_texts(self, step: Step) -> list[str]:
        """Return 4 progressively detailed hint strings for a step."""
        house = ""
        if step.house_type and step.house_index >= 0:
            house = f"{step.house_type} {step.house_index+1}"
        area = (f"Look in {house}." if house else
                f"Check the cells near R{step.placements[0][0]+1}C{step.placements[0][1]+1}."
                if step.placements else "Look for a pattern.")

        if step.placements:
            digit_hint = f"Focus on digit {step.placements[0][2]}."
        elif step.eliminations:
            digit_hint = f"Focus on digit {step.eliminations[0][2]}."
        else:
            digit_hint = "Look carefully at the candidates."

        return [
            area,
            digit_hint,
            f"Strategy: {step.strategy} (Tier {STRATEGY_TIER.get(step.strategy,'?')}).",
            step.explanation,
        ]

    def _advance_hint(self):
        step = self._hint_step()
        if step is None:
            return
        self.hint_level = (self.hint_level % 4) + 1

    # ──────────────────────────────────────────────────────────────────────────
    # Brute force
    # ──────────────────────────────────────────────────────────────────────────

    def _offer_brute_force(self):
        ok = self._confirm_dialog(
            "Solver stuck",
            "No human strategy found.\n\nRun brute-force backtracking?\n"
            "(No step-by-step explanation.)")
        if ok:
            self._run_brute_force()

    def _run_brute_force(self):
        start = self.grid_states[-1].values
        iters = [0]
        result = _bt_solve([row[:] for row in start], iters)
        if result is None:
            self._confirm_dialog("No solution", "This puzzle has no solution.")
        else:
            self.brute_force_grid  = result
            self.brute_force_iters = iters[0]

    # ──────────────────────────────────────────────────────────────────────────
    # File I/O dialogs
    # ──────────────────────────────────────────────────────────────────────────

    def _text_dialog(self, title: str, default: str = "", masked: bool = False) -> str | None:
        DW, DH = 480, 130
        dx = (WIN_W - DW) // 2
        dy = (WIN_H - DH) // 2

        self.draw()
        background = self.screen.copy()
        dim = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 110))
        background.blit(dim, (0, 0))

        text      = default
        cursor_on = True
        cursor_ms = 0
        ok_r      = pygame.Rect(dx + DW - 92,  dy + DH - 40, 80, 28)
        cancel_r  = pygame.Rect(dx + DW - 182, dy + DH - 40, 80, 28)

        while True:
            dt = self.clock.tick(30)
            cursor_ms += dt
            if cursor_ms >= 500:
                cursor_ms = 0
                cursor_on = not cursor_on

            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    return None
                elif ev.type == pygame.KEYDOWN:
                    mods = pygame.key.get_mods()
                    paste = mods & (pygame.KMOD_CTRL | pygame.KMOD_META)
                    if ev.key == pygame.K_RETURN:
                        return text.strip() or None
                    elif ev.key == pygame.K_ESCAPE:
                        return None
                    elif ev.key == pygame.K_BACKSPACE:
                        text = text[:-1]
                    elif ev.key == pygame.K_v and paste:
                        clip = _get_clipboard()
                        if clip:
                            text += "".join(c for c in clip if c.isprintable())
                    elif ev.unicode and ev.unicode.isprintable():
                        text += ev.unicode
                elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                    if ok_r.collidepoint(ev.pos):
                        return text.strip() or None
                    elif cancel_r.collidepoint(ev.pos):
                        return None

            self.screen.blit(background, (0, 0))
            p = self.p
            box = pygame.Rect(dx, dy, DW, DH)
            pygame.draw.rect(self.screen, p["panel_bg"], box, border_radius=6)
            pygame.draw.rect(self.screen, p["grid_thick"], box, 2, border_radius=6)

            surf = self.fonts["panel_title"].render(title, True, p["given_fg"])
            self.screen.blit(surf, (dx + 14, dy + 10))

            fr = pygame.Rect(dx + 14, dy + 40, DW - 28, 30)
            pygame.draw.rect(self.screen, p["panel_bg"], fr)
            pygame.draw.rect(self.screen, p["grid_thin"], fr, 1)

            font  = self.fonts["panel_body"]
            disp  = "*" * len(text) if masked else text
            while disp and font.size(disp)[0] > fr.width - 10:
                disp = disp[1:]
            surf = font.render(disp, True, p["solved_fg"])
            self.screen.blit(surf, (fr.x + 5, fr.y + 7))
            if cursor_on:
                cx = fr.x + 5 + font.size(disp)[0]
                pygame.draw.line(self.screen, p["solved_fg"],
                                 (cx, fr.y + 5), (cx, fr.y + 25), 1)

            mouse = pygame.mouse.get_pos()
            for rect, label in ((ok_r, "OK"), (cancel_r, "Cancel")):
                bg = p["btn_hover"] if rect.collidepoint(mouse) else p["btn"]
                pygame.draw.rect(self.screen, bg, rect, border_radius=4)
                s = self.fonts["btn"].render(label, True, p["btn_text"])
                self.screen.blit(s, s.get_rect(center=rect.center))

            pygame.display.flip()

    def _confirm_dialog(self, title: str, message: str) -> bool:
        DW, DH = 460, 160
        dx = (WIN_W - DW) // 2
        dy = (WIN_H - DH) // 2

        self.draw()
        background = self.screen.copy()
        dim = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 110))
        background.blit(dim, (0, 0))

        yes_r = pygame.Rect(dx + DW - 94,  dy + DH - 40, 80, 28)
        no_r  = pygame.Rect(dx + DW - 184, dy + DH - 40, 80, 28)

        while True:
            self.clock.tick(30)
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    return False
                elif ev.type == pygame.KEYDOWN:
                    if ev.key in (pygame.K_RETURN, pygame.K_y):
                        return True
                    elif ev.key in (pygame.K_ESCAPE, pygame.K_n):
                        return False
                elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                    if yes_r.collidepoint(ev.pos):
                        return True
                    if no_r.collidepoint(ev.pos):
                        return False

            p = self.p
            self.screen.blit(background, (0, 0))
            box = pygame.Rect(dx, dy, DW, DH)
            pygame.draw.rect(self.screen, p["panel_bg"], box, border_radius=6)
            pygame.draw.rect(self.screen, p["grid_thick"], box, 2, border_radius=6)

            surf = self.fonts["panel_title"].render(title, True, p["given_fg"])
            self.screen.blit(surf, (dx + 14, dy + 10))
            self._wrapped(self.screen, message, dx + 14, dy + 38,
                          DW - 28, self.fonts["panel_body"], p["solved_fg"])

            mouse = pygame.mouse.get_pos()
            for rect, label, base in (
                (yes_r, "Yes", p["btn_on"]),
                (no_r,  "No",  p["btn"]),
            ):
                r, g, b = base
                bg = (min(r+20,255), min(g+20,255), min(b+20,255)) \
                     if rect.collidepoint(mouse) else base
                pygame.draw.rect(self.screen, bg, rect, border_radius=4)
                s = self.fonts["btn"].render(label, True, p["btn_text"])
                self.screen.blit(s, s.get_rect(center=rect.center))

            pygame.display.flip()

    @staticmethod
    def _ensure_txt(path: str) -> str:
        return path if os.path.splitext(path)[1] else path + ".txt"

    def _prompt_load_file(self):
        path = self._text_dialog("Load puzzle — enter file path:")
        if not path:
            return
        path = self._ensure_txt(path)
        vals = read_puzzle(path)
        if vals:
            if self.mode == "input":
                self.input_values = vals
                self._update_input_conflicts()
            else:
                self.load_puzzle(vals)
        else:
            self._text_dialog(f"Cannot read: {path}  (ESC to dismiss)")

    def _prompt_save_file(self):
        path = self._text_dialog("Save board — enter file path:", default="puzzle.txt")
        if not path:
            return
        path = self._ensure_txt(path)
        values = (self.input_values  if self.mode == "input"  and self.input_values
                  else self.create_values if self.mode == "create" and self.create_values
                  else self.grid_states[self.step_idx].values)
        try:
            with open(path, "w") as f:
                for row in values:
                    f.write("".join(str(d) for d in row) + "\n")
        except OSError as e:
            self._text_dialog(f"Save failed: {e}  (ESC to dismiss)")

    # ──────────────────────────────────────────────────────────────────────────
    # Puzzle library dialog
    # ──────────────────────────────────────────────────────────────────────────

    def _puzzle_library_dialog(self):
        """Modal dialog to pick a built-in puzzle or generate one."""
        p = self.p
        DW, DH = 480, 420
        dx = (WIN_W - DW) // 2
        dy = (WIN_H - DH) // 2

        self.draw()
        background = self.screen.copy()
        dim = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 110))
        background.blit(dim, (0, 0))

        tiers     = list(range(0, 6))
        cur_tier  = 0
        selected  = 0   # index within current tier's list
        scroll    = 0

        ITEM_H    = 22
        LIST_X    = dx + 14
        LIST_Y    = dy + 80
        LIST_H    = DH - 130
        ITEMS_VIS = LIST_H // ITEM_H

        def tier_puzzles(t: int):
            if t <= 4:
                return get_puzzles_by_tier(t) if HAS_PUZZLES else []
            return []   # tier 5 = generate

        def load_selected():
            plist = tier_puzzles(cur_tier)
            if cur_tier == 5:
                if HAS_GENERATOR:
                    # Close dialog, generate in background
                    return "generate"
                return None
            if not plist or selected >= len(plist):
                return None
            entry = plist[selected]
            vals  = [[int(ch) for ch in row] for row in entry["rows"]]
            return vals

        close_r  = pygame.Rect(dx + DW - 40, dy + 8, 30, 22)
        load_r   = pygame.Rect(dx + DW - 100, dy + DH - 36, 88, 26)
        gen_r    = pygame.Rect(dx + 14,       dy + DH - 36, 120, 26)

        tier_rects = []
        for i, t in enumerate(tiers):
            tier_rects.append(pygame.Rect(dx + 14 + i * 76, dy + 46, 68, 24))

        while True:
            self.clock.tick(30)
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    return
                elif ev.type == pygame.KEYDOWN:
                    if ev.key == pygame.K_ESCAPE:
                        return
                    elif ev.key == pygame.K_UP:
                        selected = max(0, selected - 1)
                        scroll   = min(scroll, selected)
                    elif ev.key == pygame.K_DOWN:
                        plist = tier_puzzles(cur_tier)
                        selected = min(len(plist) - 1, selected + 1)
                        if selected >= scroll + ITEMS_VIS:
                            scroll = selected - ITEMS_VIS + 1
                    elif ev.key in (pygame.K_RETURN, pygame.K_SPACE):
                        result = load_selected()
                        if result == "generate":
                            self._do_generate(cur_tier)
                            return
                        elif result:
                            self.load_puzzle(result)
                            return
                elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                    if close_r.collidepoint(ev.pos):
                        return
                    for i, tr in enumerate(tier_rects):
                        if tr.collidepoint(ev.pos):
                            cur_tier = tiers[i]
                            selected = 0
                            scroll   = 0
                    # List items
                    plist = tier_puzzles(cur_tier)
                    for i in range(ITEMS_VIS):
                        ir = pygame.Rect(LIST_X, LIST_Y + i * ITEM_H,
                                         DW - 28, ITEM_H)
                        if ir.collidepoint(ev.pos):
                            idx = scroll + i
                            if idx < len(plist):
                                if selected == idx:
                                    result = load_selected()
                                    if result and result != "generate":
                                        self.load_puzzle(result)
                                        return
                                selected = idx
                    if load_r.collidepoint(ev.pos):
                        result = load_selected()
                        if result == "generate":
                            self._do_generate(cur_tier)
                            return
                        elif result:
                            self.load_puzzle(result)
                            return
                    if gen_r.collidepoint(ev.pos) and HAS_GENERATOR:
                        self._do_generate(cur_tier)
                        return
                elif ev.type == pygame.MOUSEWHEEL:
                    plist = tier_puzzles(cur_tier)
                    scroll = max(0, min(len(plist) - ITEMS_VIS,
                                        scroll - ev.y))

            # Draw
            p2 = self.p
            self.screen.blit(background, (0, 0))
            box = pygame.Rect(dx, dy, DW, DH)
            pygame.draw.rect(self.screen, p2["panel_bg"], box, border_radius=8)
            pygame.draw.rect(self.screen, p2["grid_thick"], box, 2, border_radius=8)

            surf = self.fonts["panel_title"].render("Puzzle Library", True, p2["given_fg"])
            self.screen.blit(surf, (dx + 14, dy + 14))

            # Close button
            pygame.draw.rect(self.screen, p2["btn_danger"], close_r, border_radius=3)
            s = self.fonts["btn"].render("✕", True, p2["btn_text"])
            self.screen.blit(s, s.get_rect(center=close_r.center))

            # Tier tabs
            for i, (t, tr) in enumerate(zip(tiers, tier_rects)):
                is_cur = (t == cur_tier)
                bg = p2["btn_on"] if is_cur else p2["btn"]
                pygame.draw.rect(self.screen, bg, tr, border_radius=4)
                label = ("Tier 0 ★" if t == 0
                         else f"Tier {t}" if t <= 4
                         else "Generate")
                s = self.fonts["btn"].render(label, True, p2["btn_text"])
                self.screen.blit(s, s.get_rect(center=tr.center))

            # List
            plist = tier_puzzles(cur_tier)
            pygame.draw.rect(self.screen,
                             p2["bg"],
                             pygame.Rect(LIST_X - 2, LIST_Y - 2,
                                         DW - 24, LIST_H + 4),
                             border_radius=4)
            if not plist and cur_tier <= 4:
                s = self.fonts["panel_body"].render(
                    "No puzzles (puzzles.py not found)", True, p2["warn"])
                self.screen.blit(s, (LIST_X + 4, LIST_Y + 8))
            elif cur_tier == 5:
                msg = ("Click GENERATE to create a new puzzle."
                       if HAS_GENERATOR else
                       "sudoku_generator.py not found.")
                s = self.fonts["panel_body"].render(msg, True, p2["cand_fg"])
                self.screen.blit(s, (LIST_X + 4, LIST_Y + 8))
            else:
                for i in range(ITEMS_VIS):
                    idx = scroll + i
                    if idx >= len(plist):
                        break
                    entry = plist[idx]
                    ir = pygame.Rect(LIST_X, LIST_Y + i * ITEM_H, DW - 28, ITEM_H)
                    if idx == selected:
                        pygame.draw.rect(self.screen, p2["btn"], ir, border_radius=3)
                    s = self.fonts["panel_body"].render(
                        entry["name"], True,
                        p2["btn_text"] if idx == selected else p2["solved_fg"])
                    self.screen.blit(s, (ir.x + 6, ir.y + 3))

            # Buttons
            pygame.draw.rect(self.screen, p2["btn_on"], load_r, border_radius=4)
            s = self.fonts["btn"].render("Load", True, p2["btn_text"])
            self.screen.blit(s, s.get_rect(center=load_r.center))

            if HAS_GENERATOR:
                pygame.draw.rect(self.screen, p2["btn"], gen_r, border_radius=4)
                s = self.fonts["btn"].render("Generate", True, p2["btn_text"])
                self.screen.blit(s, s.get_rect(center=gen_r.center))

            pygame.display.flip()

    def _do_generate(self, target_tier: int):
        """Generate a puzzle of the given tier (blocks briefly)."""
        if not HAS_GENERATOR:
            return
        self._confirm_dialog("Generating…",
                             "Generating puzzle — this may take a few seconds.")
        vals = generate_puzzle(target_tier=min(target_tier, 4),
                               max_attempts=30)
        if vals is None:
            self._confirm_dialog("Failed",
                                 "Could not generate a puzzle of that tier.")
        else:
            self.load_puzzle(vals)

    # ──────────────────────────────────────────────────────────────────────────
    # Export
    # ──────────────────────────────────────────────────────────────────────────

    def _show_status(self, message: str):
        """Draw a transient status overlay (non-blocking, shows until next frame)."""
        dim = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 140))
        self.screen.blit(dim, (0, 0))
        surf = self.fonts["panel_title"].render(message, True, (255, 255, 255))
        self.screen.blit(surf, surf.get_rect(center=(WIN_W // 2, WIN_H // 2)))
        pygame.display.flip()

    # ──────────────────────────────────────────────────────────────────────────
    # Screenshot / image import
    # ──────────────────────────────────────────────────────────────────────────

    def _handle_dropped_file(self, path: str):
        """Accept a dropped image file and extract a sudoku puzzle via Claude API."""
        ext = os.path.splitext(path)[1].lower()
        if ext not in (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"):
            return
        if not HAS_PIL:
            self._confirm_dialog(
                "Missing library",
                "Pillow is required for image import.  pip install Pillow")
            return
        img = _PILImage.open(path).convert("RGB")
        self._extract_puzzle_from_pil(img)

    @staticmethod
    def _parse_puzzle_text(text: str) -> list[list[int]] | None:
        """Parse 9 lines of 9 digits into a 9×9 grid, or return None."""
        import re as _re
        lines = []
        for raw in text.splitlines():
            digits = _re.sub(r"[.\-_]", "0", raw)
            digits = _re.sub(r"[^0-9]", "", digits)
            if len(digits) == 9:
                lines.append([int(d) for d in digits])
        if len(lines) == 9:
            return lines
        return None

    def _paste_from_clipboard(self):
        """Ctrl+V: try text puzzle first, then image."""
        # ── Text paste ────────────────────────────────────────────────────────
        text = _get_clipboard()
        if text:
            vals = self._parse_puzzle_text(text)
            if vals is not None:
                self.mode          = "input"
                self.input_values  = vals
                self.input_history = []
                self.input_future  = []
                self.selected      = (0, 0)
                self.auto_play     = False
                self._update_input_conflicts()
                self._show_status("Puzzle pasted from text — verify and press Enter.")
                return

        # ── Image paste ───────────────────────────────────────────────────────
        if not HAS_PIL:
            self._confirm_dialog(
                "Missing library",
                "Pillow is required for image import.  pip install Pillow")
            return
        try:
            img = _ImageGrab.grabclipboard()
        except Exception as e:
            self._confirm_dialog("Clipboard error", str(e))
            return
        if img is None:
            self._confirm_dialog("Nothing to paste", "No image or puzzle text found in clipboard.")
            return
        self._extract_puzzle_from_pil(img.convert("RGB"))

    def _extract_puzzle_from_pil(self, img):
        """Send a PIL image to Claude and load the extracted sudoku into input mode."""
        if not HAS_ANTHROPIC:
            self._confirm_dialog(
                "Missing library",
                "anthropic is required for image import.  pip install anthropic")
            return
        if not self.anthropic_api_key:
            self._confirm_dialog(
                "API key required",
                "No Anthropic API key set. Click API KEY to enter one.")
            return

        self._show_status("Extracting puzzle from image via Claude…")
        pygame.event.pump()  # keep window responsive

        try:
            buf = _io.BytesIO()
            img.save(buf, format="PNG")
            b64 = _base64.b64encode(buf.getvalue()).decode()
            print(f"[image-import] image encoded ({len(b64)} bytes b64), sending to Claude…")

            client = _anthropic.Anthropic(api_key=self.anthropic_api_key)
            resp = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=512,
                temperature=0,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {"type": "base64", "media_type": "image/png", "data": b64},
                        },
                        {
                            "type": "text",
                            "text": (
                                "Transcribe this 9×9 sudoku grid into exactly 9 lines of 9 digits.\n\n"
                                "Rules:\n"
                                "- Digit 1-9 printed in a cell → that digit\n"
                                "- Empty / blank / shaded / dot cell → 0\n"
                                "- Each row has EXACTLY 9 cells. Count them. "
                                "An overlooked empty cell shifts all following digits and breaks the puzzle.\n\n"
                                "Method: for each row, count all 9 column positions explicitly "
                                "before writing the digits. Use spaces between digits to avoid "
                                "miscounting, e.g. '5 3 0 0 7 0 0 0 0'.\n\n"
                                "Output: 9 lines, one per row, digits separated by spaces. Nothing else."
                            ),
                        },
                    ],
                }],
            )
            print(f"[image-import] response received, stop_reason={resp.stop_reason}")
            # Extract the text block (skip thinking blocks)
            raw = next(b.text for b in resp.content if b.type == "text")
            print(f"[image-import] raw response:\n{raw}")
            # Robust parse: strip separators, treat . - _ as 0
            import re as _re
            vals = []
            for raw_line in raw.splitlines():
                digits = _re.sub(r"[.\-_]", "0", raw_line)
                digits = _re.sub(r"[^0-9]", "", digits)
                if len(digits) == 9:
                    vals.append([int(d) for d in digits])
            print(f"[image-import] parsed {len(vals)}/9 rows")
            if len(vals) != 9:
                self._confirm_dialog(
                    "Extraction failed",
                    f"Could not parse a 9×9 grid from the image. Got {len(vals)} valid row(s).")
                return
        except Exception as e:
            import traceback
            print(f"[image-import] ERROR: {e}")
            traceback.print_exc()
            self._confirm_dialog("Error", f"Image extraction failed: {e}")
            return

        # Validate: must have a unique solution without brute force
        print("[image-import] validating extracted grid…")
        from sudoku_tutor import Grid, ALL_STRATEGIES
        conflicts = validate_board(vals)
        if conflicts:
            print(f"[image-import] conflicts detected: {conflicts}")
            self._confirm_dialog(
                "Extraction may be wrong",
                "The extracted grid has duplicate digits in a row/column/box. "
                "Load anyway to correct manually?")
        else:
            test_grid = Grid(vals)
            steps_used = set()
            while not test_grid.is_solved():
                step = None
                for _, fn in ALL_STRATEGIES:
                    step = fn(test_grid)
                    if step:
                        break
                if step is None:
                    break
                steps_used.add(step.strategy)
                test_grid.apply_step(step)
            solved = test_grid.is_solved()
            if not solved:
                solution = _bt_solve([row[:] for row in vals])
                if solution is None:
                    print("[image-import] no solution found — likely extraction error")
                    ok = self._confirm_dialog(
                        "No solution found",
                        "This grid has no valid solution — extraction is probably wrong. "
                        "Load anyway to correct manually?")
                    if not ok:
                        return
                else:
                    print("[image-import] puzzle needs brute force — may be extraction error or hard puzzle")
                    self._confirm_dialog(
                        "Possibly wrong",
                        "Puzzle cannot be solved analytically — may be an extraction error "
                        "or a very hard puzzle. Check the board carefully.")
            else:
                print(f"[image-import] solved analytically, strategies: {steps_used}")

        # Load into input mode so the user can verify / edit before solving or playing
        self.enter_input_mode()
        self.input_values = [row[:] for row in vals]
        self._update_input_conflicts()

    def _prompt_api_key(self):
        title = "Anthropic API Key (already set — paste to replace):" \
            if self.anthropic_api_key else "Anthropic API Key:"
        key = self._text_dialog(title, default="", masked=True)
        if key is None:
            return
        self.anthropic_api_key = key
        cfg = load_config()
        cfg["anthropic_api_key"] = key
        save_config(cfg)
        self._show_status("API key saved." if key else "API key cleared.")

    def _export_png(self):
        path = self._text_dialog("Export PNG — enter file path:", default="sudoku.png")
        if not path:
            return
        if not os.path.splitext(path)[1]:
            path += ".png"
        try:
            self.draw()
            pygame.image.save(self.screen, path)
        except Exception as e:
            self._text_dialog(f"Export failed: {e}  (ESC to dismiss)")

    # ──────────────────────────────────────────────────────────────────────────
    # Text rendering helper
    # ──────────────────────────────────────────────────────────────────────────

    def _wrapped(self, target, text: str, x: int, y: int,
                 max_w: int, font, color) -> int:
        words = text.split()
        line  = ""
        for word in words:
            test = (line + " " + word).strip()
            if font.size(test)[0] <= max_w:
                line = test
            else:
                if line:
                    surf = font.render(line, True, color)
                    target.blit(surf, (x, y))
                    y += surf.get_height() + 1
                line = word
        if line:
            surf = font.render(line, True, color)
            target.blit(surf, (x, y))
            y += surf.get_height() + 1
        return y

    # ──────────────────────────────────────────────────────────────────────────
    # Main loop
    # ──────────────────────────────────────────────────────────────────────────

    def run(self):
        running = True
        while running:
            dt      = self.clock.tick(60)
            running = self.handle_events()
            self._check_compute_ready()

            if self.auto_play and self.mode == "solve":
                self.auto_timer += dt
                if self.auto_timer >= self.auto_interval:
                    self.auto_timer = 0
                    if self.step_idx < len(self.steps):
                        self.go_to_step(self.step_idx + 1)
                    else:
                        self.auto_play = False

            total = len(self.steps)
            if self._computing:
                state = "Computing…"
            elif self.mode == "play":
                state = "PLAY"
            elif self.brute_force_grid is not None:
                state = "BRUTE FORCED"
            elif self.conflict_cells and self.mode == "solve":
                state = "CONFLICT"
            elif self.stuck and self.step_idx == total:
                state = "STUCK"
            elif self.step_idx == total and not self.stuck:
                state = "SOLVED"
            else:
                state = f"Step {self.step_idx}/{total}"
            pygame.display.set_caption(f"Sudoku Tutor  —  {state}")

            self.draw()

        # Save config before quitting
        save_config({
            "dark_mode":         self.dark_mode,
            "show_candidates":   self.show_candidates,
            "auto_interval":     self.auto_interval,
            "anthropic_api_key": self.anthropic_api_key,
        })
        pygame.quit()


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main():
    puzzle_file = sys.argv[1] if len(sys.argv) > 1 else None
    app = SudokuApp(puzzle_file)
    app.run()


if __name__ == "__main__":
    main()
