#!/usr/bin/env python3
"""
sudoku_tutor.py — Human-strategy Sudoku Solver & Tutor

Solves Sudoku puzzles using human-like strategies (no guessing/backtracking)
and explains every step in plain English.

Usage:
    python sudoku_tutor.py [puzzle_file] [--auto]

    puzzle_file : Path to puzzle file (default: sd0.txt)
                  Format: 9 lines of 9 digits, 0 = empty cell
    --auto      : Run without pausing (full log mode)

Strategies implemented (in order of application):
  Tier 1 — Beginner:    Full House, Naked Single, Hidden Single
  Tier 2 — Intermediate: Naked/Hidden Pairs/Triples/Quads,
                          Pointing Pairs/Triples, Box-Line Reduction
  Tier 3 — Advanced:    X-Wing, Swordfish, Jellyfish, Squirmbag, Y-Wing, XYZ-Wing, Simple Coloring
  Tier 4 — Expert:      Unique Rectangle, W-Wing, Skyscraper,
                          2-String Kite, BUG+1
  Tier 5 — Master:      Finned X-Wing, XY-Chain
"""

import sys
import argparse
from collections import deque
from dataclasses import dataclass, field
from itertools import combinations
from typing import Optional

# ─────────────────────────────────────────────────────────────────────────────
# ANSI Colors — graceful degradation on Windows
# ─────────────────────────────────────────────────────────────────────────────
if sys.platform == 'win32':
    RESET = BOLD = DIM = RED = GREEN = YELLOW = CYAN = MAGENTA = BG_RED = ""
else:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    RED     = "\033[91m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    CYAN    = "\033[96m"
    MAGENTA = "\033[95m"
    BG_RED  = "\033[41m"


# ─────────────────────────────────────────────────────────────────────────────
# Data Structures
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Step:
    """One solving step: a strategy application with explanation."""
    strategy:      str
    explanation:   str
    placements:    list = field(default_factory=list)   # [(row, col, digit)]
    eliminations:  list = field(default_factory=list)   # [(row, col, digit)]
    house_type:    str  = ""
    house_index:   int  = -1
    pattern_cells: list = field(default_factory=list)   # [(row, col)] strategy-defining cells


class Grid:
    """9×9 Sudoku grid with full candidate-set tracking."""

    def __init__(self, values: list):
        self.values   = [[values[r][c] for c in range(9)] for r in range(9)]
        self.givens   = [[values[r][c] != 0 for c in range(9)] for r in range(9)]
        self.candidates = [[set() for _ in range(9)] for _ in range(9)]
        self._init_candidates()

    def _init_candidates(self):
        for r in range(9):
            for c in range(9):
                if self.values[r][c] == 0:
                    self.candidates[r][c] = set(range(1, 10))
        for r in range(9):
            for c in range(9):
                if self.values[r][c] != 0:
                    self._remove_from_peers(r, c, self.values[r][c])

    def _remove_from_peers(self, r: int, c: int, d: int):
        for r2, c2 in self.all_peers(r, c):
            self.candidates[r2][c2].discard(d)

    def all_peers(self, r: int, c: int) -> list:
        peers = set()
        for c2 in range(9): peers.add((r, c2))
        for r2 in range(9): peers.add((r2, c))
        for cell in self.cells_of_box(self.box_of(r, c)): peers.add(cell)
        peers.discard((r, c))
        return list(peers)

    @staticmethod
    def box_of(r: int, c: int) -> int:
        return (r // 3) * 3 + (c // 3)

    @staticmethod
    def cells_of_box(box: int) -> list:
        br, bc = (box // 3) * 3, (box % 3) * 3
        return [(br + dr, bc + dc) for dr in range(3) for dc in range(3)]

    def get_houses(self) -> list:
        houses = []
        for r in range(9):
            houses.append(('row', r, [(r, c) for c in range(9)]))
        for c in range(9):
            houses.append(('col', c, [(r, c) for r in range(9)]))
        for b in range(9):
            houses.append(('box', b, self.cells_of_box(b)))
        return houses

    def cell_sees(self, r1: int, c1: int, r2: int, c2: int) -> bool:
        if (r1, c1) == (r2, c2):
            return False
        return r1 == r2 or c1 == c2 or self.box_of(r1, c1) == self.box_of(r2, c2)

    def is_solved(self) -> bool:
        return all(self.values[r][c] != 0 for r in range(9) for c in range(9))

    def apply_step(self, step: Step):
        for r, c, d in step.eliminations:
            self.candidates[r][c].discard(d)
        for r, c, d in step.placements:
            self.values[r][c] = d
            self.candidates[r][c] = set()
            self._remove_from_peers(r, c, d)

    def empty_cells(self) -> list:
        return [(r, c) for r in range(9) for c in range(9) if self.values[r][c] == 0]


# ─────────────────────────────────────────────────────────────────────────────
# Display Helpers
# ─────────────────────────────────────────────────────────────────────────────

def cell_name(r: int, c: int) -> str:
    return f"R{r+1}C{c+1}"

def cells_name(cells) -> str:
    return ", ".join(cell_name(r, c) for r, c in cells)

def digits_str(digits) -> str:
    return "{" + ",".join(str(d) for d in sorted(digits)) + "}"

def house_name(htype: str, hidx: int) -> str:
    if htype == 'row': return f"Row {hidx+1}"
    if htype == 'col': return f"Column {hidx+1}"
    names = [
        "Box 1 (top-left)",    "Box 2 (top-center)",    "Box 3 (top-right)",
        "Box 4 (middle-left)", "Box 5 (center)",         "Box 6 (middle-right)",
        "Box 7 (bottom-left)", "Box 8 (bottom-center)", "Box 9 (bottom-right)",
    ]
    return names[hidx]


def _cell_subrow(grid: Grid, r: int, c: int, sub: int, hi: set) -> str:
    """
    Return a 7-visible-char string for cell (r,c) at sub-row 0/1/2.
    Sub-row layout maps digit positions:
      sub 0 → digits 1 2 3
      sub 1 → digits 4 5 6  (also where placed digits appear centered)
      sub 2 → digits 7 8 9
    """
    v = grid.values[r][c]
    cell = (r, c)
    if v != 0:
        if sub == 1:
            ch = str(v)
            if cell in hi:
                return f"   {BG_RED}{BOLD}{ch}{RESET}   "
            elif grid.givens[r][c]:
                return f"   {CYAN}{BOLD}{ch}{RESET}   "
            else:
                return f"   {GREEN}{BOLD}{ch}{RESET}   "
        return "       "

    # Pencil marks: " d d d " (7 visible chars)
    d_start = sub * 3 + 1
    result = " "
    for i, d in enumerate([d_start, d_start + 1, d_start + 2]):
        if d in grid.candidates[r][c]:
            if cell in hi:
                result += f"{RED}{d}{RESET}"
            else:
                result += f"{DIM}{d}{RESET}"
        else:
            result += " "
        if i < 2:
            result += " "
    result += " "
    return result


def print_grid_with_candidates(grid: Grid, highlight: list = None):
    """Print 9×9 grid with 3×3 pencil-mark sub-grids per cell."""
    hi = set(highlight) if highlight else set()

    thick_top = "  ╔═══════╤═══════╤═══════╦═══════╤═══════╤═══════╦═══════╤═══════╤═══════╗"
    thick_sep = "  ╠═══════╪═══════╪═══════╬═══════╪═══════╪═══════╬═══════╪═══════╪═══════╣"
    thin_sep  = "  ╟───────┼───────┼───────╫───────┼───────┼───────╫───────┼───────┼───────╢"
    bottom    = "  ╚═══════╧═══════╧═══════╩═══════╧═══════╧═══════╩═══════╧═══════╧═══════╝"

    print()
    print(thick_top)
    for r in range(9):
        if r > 0:
            print(thick_sep if r % 3 == 0 else thin_sep)
        for sub in range(3):
            line = "  ║"
            for c in range(9):
                if c > 0:
                    line += "║" if c % 3 == 0 else "│"
                line += _cell_subrow(grid, r, c, sub, hi)
            line += "║"
            print(line)
    print(bottom)
    print()


def print_grid_clean(grid: Grid, highlight: list = None):
    """Print compact 9×9 grid with box separators."""
    hi = set(highlight) if highlight else set()
    print()
    for r in range(9):
        if r % 3 == 0:
            print("  +-------+-------+-------+")
        row = "  |"
        for c in range(9):
            if c > 0 and c % 3 == 0:
                row += " |"
            v = grid.values[r][c]
            if v == 0:
                row += " ."
            else:
                ch = str(v)
                if (r, c) in hi:
                    row += f" {BG_RED}{ch}{RESET}"
                elif grid.givens[r][c]:
                    row += f" {CYAN}{ch}{RESET}"
                else:
                    row += f" {GREEN}{BOLD}{ch}{RESET}"
        row += " |"
        print(row)
    print("  +-------+-------+-------+")
    print()


def format_step(step: Step) -> str:
    lines = [f"\n{YELLOW}{BOLD}[{step.strategy}]{RESET}"]
    if step.placements:
        placed = ", ".join(
            f"{CYAN}{cell_name(r,c)}{RESET} = {GREEN}{BOLD}{d}{RESET}"
            for r, c, d in step.placements
        )
        lines.append(f"  Placed:     {placed}")
    if step.eliminations:
        by_cell: dict = {}
        for r, c, d in step.eliminations:
            by_cell.setdefault((r, c), []).append(d)
        parts = [
            f"{CYAN}{cell_name(r,c)}{RESET} {RED}{digits_str(ds)}{RESET}"
            for (r, c), ds in by_cell.items()
        ]
        lines.append(f"  Eliminated: {', '.join(parts)}")
    lines.append(f"  {step.explanation}")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Strategies — Tier 1: Beginner
# ─────────────────────────────────────────────────────────────────────────────

def find_full_house(grid: Grid) -> Optional[Step]:
    """Full House: a house with exactly one empty cell remaining."""
    for htype, hidx, cells in grid.get_houses():
        empty = [(r, c) for r, c in cells if grid.values[r][c] == 0]
        if len(empty) == 1:
            r, c = empty[0]
            placed = {grid.values[r2][c2] for r2, c2 in cells if grid.values[r2][c2] != 0}
            d = (set(range(1, 10)) - placed).pop()
            return Step(
                strategy="Full House",
                placements=[(r, c, d)],
                explanation=(
                    f"{house_name(htype, hidx)} has only one empty cell: "
                    f"{cell_name(r, c)}. Every other digit 1-9 already appears "
                    f"in this house, so the missing digit {d} must go here."
                ),
                house_type=htype, house_index=hidx,
            )
    return None


def find_naked_single(grid: Grid) -> Optional[Step]:
    """Naked Single: a cell with exactly one candidate remaining."""
    for r in range(9):
        for c in range(9):
            if grid.values[r][c] == 0 and len(grid.candidates[r][c]) == 1:
                d = next(iter(grid.candidates[r][c]))
                return Step(
                    strategy="Naked Single",
                    placements=[(r, c, d)],
                    explanation=(
                        f"Cell {cell_name(r, c)} has only one candidate left: {d}. "
                        f"All other digits 1-9 are already present in the same "
                        f"row, column, or box — so {d} is the only possibility."
                    ),
                )
    return None


def find_hidden_single(grid: Grid) -> Optional[Step]:
    """Hidden Single: a digit that can only go in one cell within a house."""
    for htype, hidx, cells in grid.get_houses():
        for d in range(1, 10):
            positions = [
                (r, c) for r, c in cells
                if grid.values[r][c] == 0 and d in grid.candidates[r][c]
            ]
            if len(positions) == 1:
                r, c = positions[0]
                return Step(
                    strategy="Hidden Single",
                    placements=[(r, c, d)],
                    explanation=(
                        f"In {house_name(htype, hidx)}, digit {d} can only go in "
                        f"one place: {cell_name(r, c)}. Every other cell in this "
                        f"house has {d} ruled out (it appears in their row, column, "
                        f"or box). Even though {cell_name(r, c)} may have other "
                        f"candidates, {d} is hidden here as the only option for "
                        f"this house."
                    ),
                    house_type=htype, house_index=hidx,
                )
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Strategies — Tier 2: Intermediate
# ─────────────────────────────────────────────────────────────────────────────

_SET_NAMES = {2: "Pair", 3: "Triple", 4: "Quad"}


def find_naked_set(grid: Grid, size: int) -> Optional[Step]:
    """
    Naked Set (Pair/Triple/Quad): N cells in a house collectively contain
    only N candidates. Those candidates are confined to those cells and can
    be removed from all other cells in the house.
    """
    for htype, hidx, cells in grid.get_houses():
        empty = [
            (r, c) for r, c in cells
            if grid.values[r][c] == 0 and 1 < len(grid.candidates[r][c]) <= size
        ]
        for combo in combinations(empty, size):
            union = set()
            for r, c in combo:
                union |= grid.candidates[r][c]
            if len(union) == size:
                eliminations = [
                    (r, c, d)
                    for r, c in cells
                    if (r, c) not in combo and grid.values[r][c] == 0
                    for d in union
                    if d in grid.candidates[r][c]
                ]
                if eliminations:
                    name = _SET_NAMES[size]
                    combo_cells = list(combo)
                    return Step(
                        strategy=f"Naked {name}",
                        eliminations=eliminations,
                        explanation=(
                            f"In {house_name(htype, hidx)}, the {size} cells "
                            f"{cells_name(combo_cells)} together contain only the "
                            f"digits {digits_str(union)}. These digits must be "
                            f"distributed among exactly these {size} cells (we don't "
                            f"know the order yet), so no other cell in this house "
                            f"can contain them."
                        ),
                        house_type=htype, house_index=hidx,
                    )
    return None


def find_hidden_set(grid: Grid, size: int) -> Optional[Step]:
    """
    Hidden Set (Pair/Triple/Quad): N digits in a house each appear only
    within the same N cells. All other candidates in those cells can be removed.
    """
    for htype, hidx, cells in grid.get_houses():
        empty = [(r, c) for r, c in cells if grid.values[r][c] == 0]
        digit_cells: dict = {}
        for d in range(1, 10):
            positions = [(r, c) for r, c in empty if d in grid.candidates[r][c]]
            if 2 <= len(positions) <= size:
                digit_cells[d] = positions
        if len(digit_cells) < size:
            continue
        for digit_combo in combinations(digit_cells.keys(), size):
            cell_union: set = set()
            for d in digit_combo:
                cell_union |= set(map(tuple, digit_cells[d]))
            if len(cell_union) == size:
                eliminations = [
                    (r, c, d)
                    for r, c in cell_union
                    for d in grid.candidates[r][c]
                    if d not in digit_combo
                ]
                if eliminations:
                    name = _SET_NAMES[size]
                    return Step(
                        strategy=f"Hidden {name}",
                        eliminations=eliminations,
                        explanation=(
                            f"In {house_name(htype, hidx)}, digits "
                            f"{digits_str(digit_combo)} can only appear in the cells "
                            f"{cells_name(list(cell_union))}. Since these {size} "
                            f"digits are confined to exactly these {size} cells, "
                            f"those cells cannot hold any other digit — all other "
                            f"candidates in them are eliminated."
                        ),
                        house_type=htype, house_index=hidx,
                    )
    return None


def find_pointing_pairs(grid: Grid) -> Optional[Step]:
    """
    Pointing Pairs/Triples: Within a box, a candidate appears only in cells
    that all share the same row (or column). Since that digit must go somewhere
    in the box, it can be removed from the rest of that row/column outside the box.
    """
    for box in range(9):
        box_cells = grid.cells_of_box(box)
        for d in range(1, 10):
            positions = [
                (r, c) for r, c in box_cells
                if grid.values[r][c] == 0 and d in grid.candidates[r][c]
            ]
            if len(positions) < 2 or len(positions) > 3:
                continue
            rows_used = {r for r, c in positions}
            cols_used = {c for r, c in positions}

            if len(rows_used) == 1:
                row = next(iter(rows_used))
                eliminations = [
                    (row, col, d)
                    for col in range(9)
                    if grid.box_of(row, col) != box
                    and grid.values[row][col] == 0
                    and d in grid.candidates[row][col]
                ]
                if eliminations:
                    pname = "Pointing Pair" if len(positions) == 2 else "Pointing Triple"
                    return Step(
                        strategy=pname,
                        eliminations=eliminations,
                        explanation=(
                            f"In {house_name('box', box)}, digit {d} can only appear "
                            f"in cells {cells_name(positions)} — all of which lie in "
                            f"Row {row+1}. Since {d} must go somewhere in this box, "
                            f"and all its options are in Row {row+1}, digit {d} cannot "
                            f"appear anywhere else in Row {row+1} outside this box."
                        ),
                        house_type='box', house_index=box,
                    )

            if len(cols_used) == 1:
                col = next(iter(cols_used))
                eliminations = [
                    (rr, col, d)
                    for rr in range(9)
                    if grid.box_of(rr, col) != box
                    and grid.values[rr][col] == 0
                    and d in grid.candidates[rr][col]
                ]
                if eliminations:
                    pname = "Pointing Pair" if len(positions) == 2 else "Pointing Triple"
                    return Step(
                        strategy=pname,
                        eliminations=eliminations,
                        explanation=(
                            f"In {house_name('box', box)}, digit {d} can only appear "
                            f"in cells {cells_name(positions)} — all in Column {col+1}. "
                            f"Since {d} must go somewhere in this box and all its "
                            f"options are in Column {col+1}, digit {d} cannot appear "
                            f"anywhere else in Column {col+1} outside this box."
                        ),
                        house_type='box', house_index=box,
                    )
    return None


def find_box_line_reduction(grid: Grid) -> Optional[Step]:
    """
    Box-Line Reduction (Claiming): Within a row or column, a candidate appears
    only in cells that all lie within a single box. Since the digit must go
    somewhere in that row/column, and all options are inside one box, it cannot
    appear elsewhere in that box.
    """
    for htype, hidx, cells in grid.get_houses():
        if htype == 'box':
            continue
        for d in range(1, 10):
            positions = [
                (r, c) for r, c in cells
                if grid.values[r][c] == 0 and d in grid.candidates[r][c]
            ]
            if len(positions) < 2:
                continue
            boxes_used = {grid.box_of(r, c) for r, c in positions}
            if len(boxes_used) == 1:
                box = next(iter(boxes_used))
                eliminations = [
                    (r, c, d)
                    for r, c in grid.cells_of_box(box)
                    if (r, c) not in positions
                    and grid.values[r][c] == 0
                    and d in grid.candidates[r][c]
                ]
                if eliminations:
                    hname = house_name(htype, hidx)
                    bname = house_name('box', box)
                    return Step(
                        strategy="Box-Line Reduction",
                        eliminations=eliminations,
                        explanation=(
                            f"In {hname}, digit {d} can only appear within "
                            f"{bname} (at cells {cells_name(positions)}). "
                            f"Since {d} must be somewhere in {hname} and all those "
                            f"options fall inside {bname}, digit {d} is claimed by "
                            f"this {htype} and cannot appear elsewhere in {bname}."
                        ),
                        house_type=htype, house_index=hidx,
                    )
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Strategies — Tier 3: Advanced
# ─────────────────────────────────────────────────────────────────────────────

def find_x_wing(grid: Grid) -> Optional[Step]:
    """
    X-Wing: A digit appears in exactly 2 cells in each of 2 rows, and those
    4 cells form a rectangle (same 2 columns). The digit can be eliminated
    from all other cells in those 2 columns.
    """
    for d in range(1, 10):
        # Rows as base lines, columns as cover
        row_cols: dict = {}
        for r in range(9):
            cols = tuple(
                c for c in range(9)
                if grid.values[r][c] == 0 and d in grid.candidates[r][c]
            )
            if len(cols) == 2:
                row_cols[r] = cols

        for r1, r2 in combinations(row_cols, 2):
            if row_cols[r1] == row_cols[r2]:
                c1, c2 = row_cols[r1]
                eliminations = [
                    (r, col, d)
                    for col in (c1, c2)
                    for r in range(9)
                    if r not in (r1, r2)
                    and grid.values[r][col] == 0
                    and d in grid.candidates[r][col]
                ]
                if eliminations:
                    return Step(
                        strategy="X-Wing",
                        eliminations=eliminations,
                        pattern_cells=[(r1,c1),(r1,c2),(r2,c1),(r2,c2)],
                        explanation=(
                            f"Digit {d} forms an X-Wing: it appears in exactly 2 cells "
                            f"in Row {r1+1} (columns {c1+1} and {c2+1}) and exactly 2 "
                            f"cells in Row {r2+1} (the same columns). The four cells "
                            f"form a rectangle. No matter which diagonal pair holds {d}, "
                            f"columns {c1+1} and {c2+1} each get one instance. So {d} "
                            f"is impossible everywhere else in those two columns."
                        ),
                    )

        # Columns as base lines, rows as cover
        col_rows: dict = {}
        for c in range(9):
            rows = tuple(
                r for r in range(9)
                if grid.values[r][c] == 0 and d in grid.candidates[r][c]
            )
            if len(rows) == 2:
                col_rows[c] = rows

        for c1, c2 in combinations(col_rows, 2):
            if col_rows[c1] == col_rows[c2]:
                r1, r2 = col_rows[c1]
                eliminations = [
                    (row, col, d)
                    for row in (r1, r2)
                    for col in range(9)
                    if col not in (c1, c2)
                    and grid.values[row][col] == 0
                    and d in grid.candidates[row][col]
                ]
                if eliminations:
                    return Step(
                        strategy="X-Wing",
                        eliminations=eliminations,
                        pattern_cells=[(r1,c1),(r1,c2),(r2,c1),(r2,c2)],
                        explanation=(
                            f"Digit {d} forms an X-Wing: it appears in exactly 2 cells "
                            f"in Column {c1+1} (rows {r1+1} and {r2+1}) and exactly 2 "
                            f"cells in Column {c2+1} (the same rows). The rectangle "
                            f"means rows {r1+1} and {r2+1} each get one instance of {d} "
                            f"— so {d} is impossible elsewhere in those two rows."
                        ),
                    )
    return None


def find_swordfish(grid: Grid) -> Optional[Step]:
    """
    Swordfish: A digit appears in 2 or 3 cells in each of 3 rows, and all
    those cells are confined to the same 3 columns. Eliminates the digit
    from all other cells in those 3 columns.
    """
    for d in range(1, 10):
        # Rows as base
        row_cols: dict = {}
        for r in range(9):
            cols = set(
                c for c in range(9)
                if grid.values[r][c] == 0 and d in grid.candidates[r][c]
            )
            if 2 <= len(cols) <= 3:
                row_cols[r] = cols

        for r1, r2, r3 in combinations(row_cols, 3):
            cover = row_cols[r1] | row_cols[r2] | row_cols[r3]
            if len(cover) == 3:
                eliminations = [
                    (r, c, d)
                    for c in cover
                    for r in range(9)
                    if r not in (r1, r2, r3)
                    and grid.values[r][c] == 0
                    and d in grid.candidates[r][c]
                ]
                if eliminations:
                    rows_s = f"{r1+1},{r2+1},{r3+1}"
                    cols_s = ",".join(str(c+1) for c in sorted(cover))
                    return Step(
                        strategy="Swordfish",
                        eliminations=eliminations,
                        pattern_cells=[
                            (r, c) for r in (r1, r2, r3) for c in cover
                            if grid.values[r][c] == 0 and d in grid.candidates[r][c]
                        ],
                        explanation=(
                            f"Digit {d} forms a Swordfish across rows {rows_s}: in "
                            f"each of these rows, {d} only appears within columns "
                            f"{cols_s}. These 3 rows and 3 columns form a locked "
                            f"pattern where {d} must occupy one cell per row and one "
                            f"per column. Therefore {d} is impossible everywhere else "
                            f"in columns {cols_s}."
                        ),
                    )

        # Columns as base
        col_rows: dict = {}
        for c in range(9):
            rows = set(
                r for r in range(9)
                if grid.values[r][c] == 0 and d in grid.candidates[r][c]
            )
            if 2 <= len(rows) <= 3:
                col_rows[c] = rows

        for c1, c2, c3 in combinations(col_rows, 3):
            cover = col_rows[c1] | col_rows[c2] | col_rows[c3]
            if len(cover) == 3:
                eliminations = [
                    (r, c, d)
                    for r in cover
                    for c in range(9)
                    if c not in (c1, c2, c3)
                    and grid.values[r][c] == 0
                    and d in grid.candidates[r][c]
                ]
                if eliminations:
                    cols_s = f"{c1+1},{c2+1},{c3+1}"
                    rows_s = ",".join(str(r+1) for r in sorted(cover))
                    return Step(
                        strategy="Swordfish",
                        eliminations=eliminations,
                        pattern_cells=[
                            (r, c) for c in (c1, c2, c3) for r in cover
                            if grid.values[r][c] == 0 and d in grid.candidates[r][c]
                        ],
                        explanation=(
                            f"Digit {d} forms a Swordfish across columns {cols_s}: "
                            f"each column only has {d} within rows {rows_s}. So {d} "
                            f"is impossible everywhere else in those 3 rows."
                        ),
                    )
    return None


def find_jellyfish(grid: Grid) -> Optional[Step]:
    """
    Jellyfish: A digit appears in 2 to 4 cells in each of 4 rows, and all
    those cells are confined to the same 4 columns. Eliminates the digit
    from all other cells in those 4 columns.
    """
    for d in range(1, 10):
        # Rows as base
        row_cols: dict = {}
        for r in range(9):
            cols = set(
                c for c in range(9)
                if grid.values[r][c] == 0 and d in grid.candidates[r][c]
            )
            if 2 <= len(cols) <= 4:
                row_cols[r] = cols

        for r1, r2, r3, r4 in combinations(row_cols, 4):
            cover = row_cols[r1] | row_cols[r2] | row_cols[r3] | row_cols[r4]
            if len(cover) == 4:
                eliminations = [
                    (r, c, d)
                    for c in cover
                    for r in range(9)
                    if r not in (r1, r2, r3, r4)
                    and grid.values[r][c] == 0
                    and d in grid.candidates[r][c]
                ]
                if eliminations:
                    rows_s = f"{r1+1},{r2+1},{r3+1},{r4+1}"
                    cols_s = ",".join(str(c+1) for c in sorted(cover))
                    return Step(
                        strategy="Jellyfish",
                        eliminations=eliminations,
                        pattern_cells=[
                            (r, c) for r in (r1, r2, r3, r4) for c in cover
                            if grid.values[r][c] == 0 and d in grid.candidates[r][c]
                        ],
                        explanation=(
                            f"Digit {d} forms a Jellyfish across rows {rows_s}: in "
                            f"each of these rows, {d} only appears within columns "
                            f"{cols_s}. These 4 rows and 4 columns form a locked "
                            f"pattern where {d} must occupy one cell per row and one "
                            f"per column. Therefore {d} is impossible everywhere else "
                            f"in columns {cols_s}."
                        ),
                    )

        # Columns as base
        col_rows: dict = {}
        for c in range(9):
            rows = set(
                r for r in range(9)
                if grid.values[r][c] == 0 and d in grid.candidates[r][c]
            )
            if 2 <= len(rows) <= 4:
                col_rows[c] = rows

        for c1, c2, c3, c4 in combinations(col_rows, 4):
            cover = col_rows[c1] | col_rows[c2] | col_rows[c3] | col_rows[c4]
            if len(cover) == 4:
                eliminations = [
                    (r, c, d)
                    for r in cover
                    for c in range(9)
                    if c not in (c1, c2, c3, c4)
                    and grid.values[r][c] == 0
                    and d in grid.candidates[r][c]
                ]
                if eliminations:
                    cols_s = f"{c1+1},{c2+1},{c3+1},{c4+1}"
                    rows_s = ",".join(str(r+1) for r in sorted(cover))
                    return Step(
                        strategy="Jellyfish",
                        eliminations=eliminations,
                        pattern_cells=[
                            (r, c) for c in (c1, c2, c3, c4) for r in cover
                            if grid.values[r][c] == 0 and d in grid.candidates[r][c]
                        ],
                        explanation=(
                            f"Digit {d} forms a Jellyfish across columns {cols_s}: "
                            f"each column only has {d} within rows {rows_s}. So {d} "
                            f"is impossible everywhere else in those 4 rows."
                        ),
                    )
    return None


def find_squirmbag(grid: Grid) -> Optional[Step]:
    """
    Squirmbag: A digit appears in 2 to 5 cells in each of 5 rows, and all
    those cells are confined to the same 5 columns. Eliminates the digit
    from all other cells in those 5 columns.
    """
    for d in range(1, 10):
        # Rows as base
        row_cols: dict = {}
        for r in range(9):
            cols = set(
                c for c in range(9)
                if grid.values[r][c] == 0 and d in grid.candidates[r][c]
            )
            if 2 <= len(cols) <= 5:
                row_cols[r] = cols

        for r1, r2, r3, r4, r5 in combinations(row_cols, 5):
            cover = row_cols[r1] | row_cols[r2] | row_cols[r3] | row_cols[r4] | row_cols[r5]
            if len(cover) == 5:
                eliminations = [
                    (r, c, d)
                    for c in cover
                    for r in range(9)
                    if r not in (r1, r2, r3, r4, r5)
                    and grid.values[r][c] == 0
                    and d in grid.candidates[r][c]
                ]
                if eliminations:
                    rows_s = f"{r1+1},{r2+1},{r3+1},{r4+1},{r5+1}"
                    cols_s = ",".join(str(c+1) for c in sorted(cover))
                    return Step(
                        strategy="Squirmbag",
                        eliminations=eliminations,
                        pattern_cells=[
                            (r, c) for r in (r1, r2, r3, r4, r5) for c in cover
                            if grid.values[r][c] == 0 and d in grid.candidates[r][c]
                        ],
                        explanation=(
                            f"Digit {d} forms a Squirmbag across rows {rows_s}: in "
                            f"each of these rows, {d} only appears within columns "
                            f"{cols_s}. These 5 rows and 5 columns form a locked "
                            f"pattern where {d} must occupy one cell per row and one "
                            f"per column. Therefore {d} is impossible everywhere else "
                            f"in columns {cols_s}."
                        ),
                    )

        # Columns as base
        col_rows: dict = {}
        for c in range(9):
            rows = set(
                r for r in range(9)
                if grid.values[r][c] == 0 and d in grid.candidates[r][c]
            )
            if 2 <= len(rows) <= 5:
                col_rows[c] = rows

        for c1, c2, c3, c4, c5 in combinations(col_rows, 5):
            cover = col_rows[c1] | col_rows[c2] | col_rows[c3] | col_rows[c4] | col_rows[c5]
            if len(cover) == 5:
                eliminations = [
                    (r, c, d)
                    for r in cover
                    for c in range(9)
                    if c not in (c1, c2, c3, c4, c5)
                    and grid.values[r][c] == 0
                    and d in grid.candidates[r][c]
                ]
                if eliminations:
                    cols_s = f"{c1+1},{c2+1},{c3+1},{c4+1},{c5+1}"
                    rows_s = ",".join(str(r+1) for r in sorted(cover))
                    return Step(
                        strategy="Squirmbag",
                        eliminations=eliminations,
                        pattern_cells=[
                            (r, c) for c in (c1, c2, c3, c4, c5) for r in cover
                            if grid.values[r][c] == 0 and d in grid.candidates[r][c]
                        ],
                        explanation=(
                            f"Digit {d} forms a Squirmbag across columns {cols_s}: "
                            f"each column only has {d} within rows {rows_s}. So {d} "
                            f"is impossible everywhere else in those 5 rows."
                        ),
                    )
    return None


def find_y_wing(grid: Grid) -> Optional[Step]:
    """
    Y-Wing (XY-Wing): Three bi-value cells in a hinge arrangement.
    - Pivot: {A, B}
    - Wing 1: {A, C} — sees pivot
    - Wing 2: {B, C} — sees pivot
    Since one wing must hold C regardless of the pivot's value,
    any cell that sees BOTH wings cannot contain C.
    """
    bivs = [
        (r, c) for r in range(9) for c in range(9)
        if grid.values[r][c] == 0 and len(grid.candidates[r][c]) == 2
    ]
    for rp, cp in bivs:
        A, B = tuple(grid.candidates[rp][cp])
        # Candidate wings: bi-value cells seeing pivot, sharing exactly one digit with pivot
        wings = [
            (r, c) for r, c in bivs
            if (r, c) != (rp, cp)
            and grid.cell_sees(rp, cp, r, c)
            and len(grid.candidates[r][c] & {A, B}) == 1
        ]
        for (r1, c1), (r2, c2) in combinations(wings, 2):
            cands1 = grid.candidates[r1][c1]
            cands2 = grid.candidates[r2][c2]
            shared1 = cands1 & {A, B}
            shared2 = cands2 & {A, B}
            if shared1 == shared2:
                continue  # both wings share the same pivot digit — invalid
            # C is the digit shared by both wings but not the pivot
            C_set = (cands1 | cands2) - {A, B}
            if len(C_set) != 1:
                continue
            C = next(iter(C_set))
            if C not in cands1 or C not in cands2:
                continue
            eliminations = [
                (r, c, C)
                for r, c in grid.empty_cells()
                if (r, c) not in {(rp, cp), (r1, c1), (r2, c2)}
                and C in grid.candidates[r][c]
                and grid.cell_sees(r, c, r1, c1)
                and grid.cell_sees(r, c, r2, c2)
            ]
            if eliminations:
                return Step(
                    strategy="Y-Wing",
                    eliminations=eliminations,
                    pattern_cells=[(rp,cp),(r1,c1),(r2,c2)],
                    explanation=(
                        f"Y-Wing: Pivot {cell_name(rp,cp)} = {digits_str({A,B})}. "
                        f"Wing 1 at {cell_name(r1,c1)} = {digits_str(cands1)}, "
                        f"Wing 2 at {cell_name(r2,c2)} = {digits_str(cands2)}. "
                        f"The pivot must be {A} or {B}. If pivot={A}, Wing 1 is "
                        f"forced to {C}. If pivot={B}, Wing 2 is forced to {C}. "
                        f"Either way, one wing holds {C} — so any cell that sees "
                        f"both wings cannot contain {C}."
                    ),
                )
    return None


def find_xyz_wing(grid: Grid) -> Optional[Step]:
    """
    XYZ-Wing: Like Y-Wing but the pivot has 3 candidates.
    - Pivot: {A, B, C} (tri-value)
    - Wing 1: bi-value subset of pivot, e.g. {A, C}
    - Wing 2: bi-value subset of pivot, e.g. {B, C}
    C must go in pivot, Wing1, or Wing2. Cells seeing ALL THREE cannot hold C.
    """
    trivs = [
        (r, c) for r in range(9) for c in range(9)
        if grid.values[r][c] == 0 and len(grid.candidates[r][c]) == 3
    ]
    bivs = [
        (r, c) for r in range(9) for c in range(9)
        if grid.values[r][c] == 0 and len(grid.candidates[r][c]) == 2
    ]
    for rp, cp in trivs:
        pivot_cands = grid.candidates[rp][cp]
        wings = [
            (r, c) for r, c in bivs
            if grid.cell_sees(rp, cp, r, c)
            and grid.candidates[r][c].issubset(pivot_cands)
        ]
        for (r1, c1), (r2, c2) in combinations(wings, 2):
            cands1 = grid.candidates[r1][c1]
            cands2 = grid.candidates[r2][c2]
            if cands1 | cands2 != pivot_cands:
                continue
            shared = cands1 & cands2
            if len(shared) != 1:
                continue
            Z = next(iter(shared))
            eliminations = [
                (r, c, Z)
                for r, c in grid.empty_cells()
                if (r, c) not in {(rp, cp), (r1, c1), (r2, c2)}
                and Z in grid.candidates[r][c]
                and grid.cell_sees(r, c, rp, cp)
                and grid.cell_sees(r, c, r1, c1)
                and grid.cell_sees(r, c, r2, c2)
            ]
            if eliminations:
                return Step(
                    strategy="XYZ-Wing",
                    eliminations=eliminations,
                    pattern_cells=[(rp,cp),(r1,c1),(r2,c2)],
                    explanation=(
                        f"XYZ-Wing: Pivot {cell_name(rp,cp)} = {digits_str(pivot_cands)}. "
                        f"Wing 1 at {cell_name(r1,c1)} = {digits_str(cands1)}, "
                        f"Wing 2 at {cell_name(r2,c2)} = {digits_str(cands2)}. "
                        f"The shared digit {Z} must be placed in one of these three "
                        f"cells (unlike Y-Wing, the pivot also contains {Z}). "
                        f"Any cell seeing all three of them cannot contain {Z}."
                    ),
                )
    return None


def find_simple_coloring(grid: Grid) -> Optional[Step]:
    """
    Simple Coloring (Singles Chains): For one digit, build 'conjugate pair' chains
    where each link connects two cells that are the only candidates in a house.
    Alternating colors (blue/green) are assigned along the chain.
    Rule 1: If two same-colored cells share a house, that color is impossible.
    Rule 2: Any uncolored cell that sees BOTH colors cannot hold the digit.
    """
    for d in range(1, 10):
        # Build strong-link graph
        links: dict = {}
        for _, _, cells in grid.get_houses():
            positions = [
                (r, c) for r, c in cells
                if grid.values[r][c] == 0 and d in grid.candidates[r][c]
            ]
            if len(positions) == 2:
                (r1, c1), (r2, c2) = positions
                links.setdefault((r1, c1), set()).add((r2, c2))
                links.setdefault((r2, c2), set()).add((r1, c1))

        if len(links) < 4:
            continue

        visited: dict = {}
        for start in links:
            if start in visited:
                continue
            component: dict = {}
            queue = deque([(start, True)])
            while queue:
                cell, color = queue.popleft()
                if cell in component:
                    continue
                component[cell] = color
                for nb in links.get(cell, set()):
                    if nb not in component:
                        queue.append((nb, not color))
            visited.update(component)

            blue  = [c for c, col in component.items() if col]
            green = [c for c, col in component.items() if not col]

            # Rule 1: Same color in same house → that color is wrong
            for color_name, same_cells in [("blue", blue), ("green", green)]:
                for (r1, c1), (r2, c2) in combinations(same_cells, 2):
                    if grid.cell_sees(r1, c1, r2, c2):
                        wrong = same_cells
                        eliminations = [
                            (r, c, d) for r, c in wrong
                            if d in grid.candidates[r][c]
                        ]
                        if eliminations:
                            other = "green" if color_name == "blue" else "blue"
                            return Step(
                                strategy="Simple Coloring",
                                eliminations=eliminations,
                                pattern_cells=list(component.keys()),
                                explanation=(
                                    f"For digit {d}, a conjugate chain was built. "
                                    f"Two {color_name}-colored cells "
                                    f"({cell_name(r1,c1)} and {cell_name(r2,c2)}) "
                                    f"share the same house — a contradiction! "
                                    f"The {color_name} color cannot be the solution, "
                                    f"so {d} is eliminated from all {color_name} cells. "
                                    f"(The {other} cells are the solution.)"
                                ),
                            )

            # Rule 2: Uncolored cell sees both colors → eliminate
            eliminations = []
            for r, c in grid.empty_cells():
                if (r, c) in component or d not in grid.candidates[r][c]:
                    continue
                sees_blue  = any(grid.cell_sees(r, c, r2, c2) for r2, c2 in blue)
                sees_green = any(grid.cell_sees(r, c, r2, c2) for r2, c2 in green)
                if sees_blue and sees_green:
                    eliminations.append((r, c, d))
            if eliminations:
                return Step(
                    strategy="Simple Coloring",
                    eliminations=eliminations,
                    pattern_cells=list(component.keys()),
                    explanation=(
                        f"For digit {d}, conjugate pairs form a chain colored "
                        f"blue/green. Blue cells: {cells_name(blue)}; "
                        f"Green cells: {cells_name(green)}. "
                        f"One color must hold {d}, the other must not — but we don't "
                        f"know which yet. Any uncolored cell that sees BOTH a blue "
                        f"and a green cell is eliminated regardless of which color "
                        f"wins."
                    ),
                )
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Tier 4 — Expert Strategies
# ─────────────────────────────────────────────────────────────────────────────

def find_unique_rectangle(grid: Grid) -> Optional[Step]:
    """
    Unique Rectangle (UR): Assumes the puzzle has a unique solution.
    Four cells in a 2×2 rectangle spanning exactly 2 boxes cannot all contain
    only the same two candidates {A,B} — that would create a deadly pattern
    with multiple solutions.

    UR Type 1: Three corners have exactly {A,B}; the fourth has {A,B,...}.
               Eliminate A and B from the fourth cell.
    UR Type 2: Two corners have exactly {A,B}; the other two have {A,B,X}.
               X must go in one of the two "roof" cells — eliminate X from
               any cell seeing both roofs.
    """
    for d1, d2 in combinations(range(1, 10), 2):
        pair = frozenset({d1, d2})
        for r1, r2 in combinations(range(9), 2):
            for c1, c2 in combinations(range(9), 2):
                cells = [(r1, c1), (r1, c2), (r2, c1), (r2, c2)]
                # Rectangle must span exactly 2 boxes
                boxes = {Grid.box_of(r, c) for r, c in cells}
                if len(boxes) != 2:
                    continue
                # All 4 cells must be empty with {A,B} ⊆ candidates
                if not all(
                    grid.values[r][c] == 0 and pair.issubset(grid.candidates[r][c])
                    for r, c in cells
                ):
                    continue
                floors = [(r, c) for r, c in cells if grid.candidates[r][c] == pair]
                roofs  = [(r, c) for r, c in cells if grid.candidates[r][c] != pair]
                # UR Type 1: 3 floors, 1 roof
                if len(floors) == 3 and len(roofs) == 1:
                    rr, rc = roofs[0]
                    eliminations = [
                        (rr, rc, d) for d in (d1, d2)
                        if d in grid.candidates[rr][rc]
                    ]
                    if eliminations:
                        return Step(
                            strategy="Unique Rectangle",
                            eliminations=eliminations,
                            pattern_cells=cells,
                            explanation=(
                                f"Unique Rectangle (Type 1) with digits {d1},{d2} at "
                                f"{cell_name(r1,c1)},{cell_name(r1,c2)},"
                                f"{cell_name(r2,c1)},{cell_name(r2,c2)}. "
                                f"Three corners have exactly {{{d1},{d2}}}. "
                                f"If {cell_name(rr,rc)} also only contained {{{d1},{d2}}}, "
                                f"the puzzle would have multiple solutions (deadly pattern). "
                                f"Therefore {d1} and {d2} can be eliminated from {cell_name(rr,rc)}."
                            ),
                        )
                # UR Type 2: 2 floors, 2 roofs with same single extra digit X
                if len(floors) == 2 and len(roofs) == 2:
                    extras1 = grid.candidates[roofs[0][0]][roofs[0][1]] - pair
                    extras2 = grid.candidates[roofs[1][0]][roofs[1][1]] - pair
                    if extras1 == extras2 and len(extras1) == 1:
                        X = next(iter(extras1))
                        rr1, rc1 = roofs[0]
                        rr2, rc2 = roofs[1]
                        eliminations = [
                            (r, c, X)
                            for r in range(9) for c in range(9)
                            if (r, c) not in cells
                            and grid.values[r][c] == 0
                            and X in grid.candidates[r][c]
                            and grid.cell_sees(r, c, rr1, rc1)
                            and grid.cell_sees(r, c, rr2, rc2)
                        ]
                        if eliminations:
                            return Step(
                                strategy="Unique Rectangle",
                                eliminations=eliminations,
                                pattern_cells=cells,
                                explanation=(
                                    f"Unique Rectangle (Type 2) with digits {d1},{d2} at "
                                    f"{cell_name(r1,c1)},{cell_name(r1,c2)},"
                                    f"{cell_name(r2,c1)},{cell_name(r2,c2)}. "
                                    f"Two corners are exactly {{{d1},{d2}}}; the other two "
                                    f"also contain extra digit {X}. To avoid a deadly pattern, "
                                    f"{X} must occupy one of {cell_name(rr1,rc1)} or "
                                    f"{cell_name(rr2,rc2)}. Cells seeing both cannot hold {X}."
                                ),
                            )
    return None


def find_w_wing(grid: Grid) -> Optional[Step]:
    """
    W-Wing: Two bi-value cells P1={A,B} and P2={A,B} that don't see each other.
    If there is a strong link on A (a house where A appears in exactly 2 cells,
    one seeing P1 and the other seeing P2), then B can be eliminated from any
    cell seeing both P1 and P2.
    """
    bivs = [
        (r, c) for r in range(9) for c in range(9)
        if grid.values[r][c] == 0 and len(grid.candidates[r][c]) == 2
    ]
    for i, (r1, c1) in enumerate(bivs):
        for r2, c2 in bivs[i + 1:]:
            if grid.candidates[r1][c1] != grid.candidates[r2][c2]:
                continue
            if grid.cell_sees(r1, c1, r2, c2):
                continue   # would be a naked pair
            A, B = tuple(grid.candidates[r1][c1])
            for bridge_digit, elim_digit in ((A, B), (B, A)):
                for _, _, house_cells in grid.get_houses():
                    positions = [
                        (r, c) for r, c in house_cells
                        if grid.values[r][c] == 0
                        and bridge_digit in grid.candidates[r][c]
                    ]
                    if len(positions) != 2:
                        continue
                    (la, lb), (ra, rb) = positions
                    sees_p1_la = grid.cell_sees(la, lb, r1, c1)
                    sees_p2_la = grid.cell_sees(la, lb, r2, c2)
                    sees_p1_ra = grid.cell_sees(ra, rb, r1, c1)
                    sees_p2_ra = grid.cell_sees(ra, rb, r2, c2)
                    if not ((sees_p1_la and sees_p2_ra) or (sees_p2_la and sees_p1_ra)):
                        continue
                    eliminations = [
                        (r, c, elim_digit)
                        for r in range(9) for c in range(9)
                        if (r, c) not in {(r1, c1), (r2, c2)}
                        and grid.values[r][c] == 0
                        and elim_digit in grid.candidates[r][c]
                        and grid.cell_sees(r, c, r1, c1)
                        and grid.cell_sees(r, c, r2, c2)
                    ]
                    if eliminations:
                        return Step(
                            strategy="W-Wing",
                            eliminations=eliminations,
                            pattern_cells=[(la, lb), (ra, rb), (r1, c1), (r2, c2)],
                            explanation=(
                                f"W-Wing: Cells {cell_name(r1,c1)} and {cell_name(r2,c2)} "
                                f"both have candidates {{{A},{B}}} and don't see each other. "
                                f"A strong link on {bridge_digit} connects {cell_name(la,lb)} "
                                f"and {cell_name(ra,rb)} (the bridge). One bridge end sees P1, "
                                f"the other sees P2 — so one of P1 or P2 is forced to "
                                f"{elim_digit}. Any cell seeing both P1 and P2 cannot hold "
                                f"{elim_digit}."
                            ),
                        )
    return None


def find_skyscraper(grid: Grid) -> Optional[Step]:
    """
    Skyscraper: For digit D, two rows (or columns) each have D in exactly 2 cells.
    The rows share one column (the 'trunk'). The other two cells (the 'roofs') are
    connected by the trunk strong link: exactly one roof must contain D.
    Any cell seeing both roofs can eliminate D.
    """
    for d in range(1, 10):
        # Row-based
        row_two: dict = {}
        for r in range(9):
            cols = [c for c in range(9)
                    if grid.values[r][c] == 0 and d in grid.candidates[r][c]]
            if len(cols) == 2:
                row_two[r] = cols
        for ra, rb in combinations(row_two, 2):
            ca1, ca2 = row_two[ra]
            cb1, cb2 = row_two[rb]
            shared = {ca1, ca2} & {cb1, cb2}
            if len(shared) != 1:
                continue
            sc = next(iter(shared))
            roof_a = (ra, ca1 if ca2 == sc else ca2)
            roof_b = (rb, cb1 if cb2 == sc else cb2)
            # Roofs must be in different boxes for a real Skyscraper
            if Grid.box_of(*roof_a) == Grid.box_of(*roof_b):
                continue
            eliminations = [
                (r, c, d)
                for r in range(9) for c in range(9)
                if (r, c) not in {(ra, sc), (rb, sc), roof_a, roof_b}
                and grid.values[r][c] == 0
                and d in grid.candidates[r][c]
                and grid.cell_sees(r, c, *roof_a)
                and grid.cell_sees(r, c, *roof_b)
            ]
            if eliminations:
                return Step(
                    strategy="Skyscraper",
                    eliminations=eliminations,
                    pattern_cells=[(ra, sc), (rb, sc), roof_a, roof_b],
                    explanation=(
                        f"Skyscraper for digit {d}: rows {ra+1} and {rb+1} each have "
                        f"{d} in exactly 2 cells, sharing column {sc+1} as the trunk. "
                        f"The strong link in column {sc+1} means one trunk cell holds "
                        f"{d}, forcing the opposite roof to also hold {d} (via its row). "
                        f"One of {cell_name(*roof_a)} or {cell_name(*roof_b)} must be "
                        f"{d}, so any cell seeing both roofs can eliminate {d}."
                    ),
                )
        # Column-based
        col_two: dict = {}
        for c in range(9):
            rows = [r for r in range(9)
                    if grid.values[r][c] == 0 and d in grid.candidates[r][c]]
            if len(rows) == 2:
                col_two[c] = rows
        for ca, cb in combinations(col_two, 2):
            ra1, ra2 = col_two[ca]
            rb1, rb2 = col_two[cb]
            shared = {ra1, ra2} & {rb1, rb2}
            if len(shared) != 1:
                continue
            sr = next(iter(shared))
            roof_a = (ra1 if ra2 == sr else ra2, ca)
            roof_b = (rb1 if rb2 == sr else rb2, cb)
            if Grid.box_of(*roof_a) == Grid.box_of(*roof_b):
                continue
            eliminations = [
                (r, c, d)
                for r in range(9) for c in range(9)
                if (r, c) not in {(sr, ca), (sr, cb), roof_a, roof_b}
                and grid.values[r][c] == 0
                and d in grid.candidates[r][c]
                and grid.cell_sees(r, c, *roof_a)
                and grid.cell_sees(r, c, *roof_b)
            ]
            if eliminations:
                return Step(
                    strategy="Skyscraper",
                    eliminations=eliminations,
                    pattern_cells=[(sr, ca), (sr, cb), roof_a, roof_b],
                    explanation=(
                        f"Skyscraper for digit {d}: columns {ca+1} and {cb+1} each "
                        f"have {d} in exactly 2 cells, sharing row {sr+1} as the trunk. "
                        f"One of {cell_name(*roof_a)} or {cell_name(*roof_b)} must be "
                        f"{d}, so any cell seeing both roofs can eliminate {d}."
                    ),
                )
    return None


def find_2_string_kite(grid: Grid) -> Optional[Step]:
    """
    2-String Kite: For digit D, a row and a column each have D in exactly 2 cells.
    They share one cell (the pivot). The two non-pivot 'tail' cells each trace a
    string from the pivot — one along the row, one along the column.
    Exactly one tail must hold D; cells seeing both tails can eliminate D.
    """
    for d in range(1, 10):
        row_two: dict = {}
        for r in range(9):
            cols = [c for c in range(9)
                    if grid.values[r][c] == 0 and d in grid.candidates[r][c]]
            if len(cols) == 2:
                row_two[r] = cols
        col_two: dict = {}
        for c in range(9):
            rows = [r for r in range(9)
                    if grid.values[r][c] == 0 and d in grid.candidates[r][c]]
            if len(rows) == 2:
                col_two[c] = rows

        for r, row_cols in row_two.items():
            for pivot_c in row_cols:
                if pivot_c not in col_two:
                    continue
                col_rows = col_two[pivot_c]
                if r not in col_rows:
                    continue
                # Found: row r has D at (r, pivot_c) and (r, tail_c)
                #        col pivot_c has D at (r, pivot_c) and (tail_r, pivot_c)
                tail_c = row_cols[0] if row_cols[1] == pivot_c else row_cols[1]
                tail_r = col_rows[0] if col_rows[1] == r else col_rows[1]
                tail_row = (r, tail_c)
                tail_col = (tail_r, pivot_c)
                # Tails must be in different boxes
                if Grid.box_of(*tail_row) == Grid.box_of(*tail_col):
                    continue
                eliminations = [
                    (rr, cc, d)
                    for rr in range(9) for cc in range(9)
                    if (rr, cc) not in {(r, pivot_c), tail_row, tail_col}
                    and grid.values[rr][cc] == 0
                    and d in grid.candidates[rr][cc]
                    and grid.cell_sees(rr, cc, *tail_row)
                    and grid.cell_sees(rr, cc, *tail_col)
                ]
                if eliminations:
                    return Step(
                        strategy="2-String Kite",
                        eliminations=eliminations,
                        pattern_cells=[(r, pivot_c), tail_row, tail_col],
                        explanation=(
                            f"2-String Kite for digit {d}: pivot {cell_name(r,pivot_c)} "
                            f"is the only cell where row {r+1} and column {pivot_c+1} "
                            f"both have {d} in exactly 2 positions. "
                            f"String 1 (row): {cell_name(r,pivot_c)}→{cell_name(*tail_row)}. "
                            f"String 2 (col): {cell_name(r,pivot_c)}→{cell_name(*tail_col)}. "
                            f"One of the two tail cells must hold {d}; "
                            f"cells seeing both can eliminate {d}."
                        ),
                    )
    return None


def find_bug_plus_1(grid: Grid) -> Optional[Step]:
    """
    BUG+1 (Bivalue Universal Grave + 1):
    All empty cells have exactly 2 candidates except exactly one tri-value cell.
    The candidate that appears an odd number of times in all three houses (row,
    column, box) of the tri-value cell must be placed there — otherwise the
    puzzle would have multiple solutions (a Bivalue Universal Grave).
    """
    empty_cells = [
        (r, c) for r in range(9) for c in range(9)
        if grid.values[r][c] == 0
    ]
    trivalue = [(r, c) for r, c in empty_cells if len(grid.candidates[r][c]) == 3]
    if len(trivalue) != 1:
        return None
    if any(len(grid.candidates[r][c]) != 2
           for r, c in empty_cells if (r, c) != trivalue[0]):
        return None

    rp, cp = trivalue[0]
    box = Grid.box_of(rp, cp)
    row_cells = [(rp, c) for c in range(9) if grid.values[rp][c] == 0]
    col_cells = [(r, cp) for r in range(9) if grid.values[r][cp] == 0]
    box_cells = [(r, c) for r, c in Grid.cells_of_box(box) if grid.values[r][c] == 0]

    for d in grid.candidates[rp][cp]:
        rc = sum(1 for r, c in row_cells if d in grid.candidates[r][c])
        cc = sum(1 for r, c in col_cells if d in grid.candidates[r][c])
        bc = sum(1 for r, c in box_cells if d in grid.candidates[r][c])
        if rc % 2 == 1 and cc % 2 == 1 and bc % 2 == 1:
            return Step(
                strategy="BUG+1",
                placements=[(rp, cp, d)],
                explanation=(
                    f"BUG+1: Every empty cell has exactly 2 candidates except "
                    f"{cell_name(rp,cp)} which has 3: {digits_str(grid.candidates[rp][cp])}. "
                    f"Placing any digit other than {d} here would create a Bivalue "
                    f"Universal Grave — a configuration with multiple solutions. "
                    f"Therefore {d} must go at {cell_name(rp,cp)}."
                ),
            )
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Tier 5 — Master Strategies
# ─────────────────────────────────────────────────────────────────────────────

def find_finned_x_wing(grid: Grid) -> Optional[Step]:
    """
    Finned X-Wing: An X-Wing where one base line has extra 'fin' cells beyond
    the two defining cover-line positions. All fins must share a box with one
    of the base cells in the finned line.  Eliminations are restricted to cells
    in that same box AND in the cover line that the fins share with.
    """
    for d in range(1, 10):
        # ── Row-based ────────────────────────────────────────────────────────
        row_cands: dict = {}
        for r in range(9):
            cols = [c for c in range(9)
                    if grid.values[r][c] == 0 and d in grid.candidates[r][c]]
            if 2 <= len(cols) <= 4:
                row_cands[r] = cols

        for r1, r2 in combinations(row_cands, 2):
            for clean_r, fin_r in ((r1, r2), (r2, r1)):
                clean_cols = set(row_cands[clean_r])
                fin_cols   = set(row_cands[fin_r])
                if len(clean_cols) != 2:
                    continue
                if not clean_cols.issubset(fin_cols):
                    continue
                c1, c2 = tuple(clean_cols)
                fins = [c for c in fin_cols if c not in clean_cols]
                if not fins:
                    continue
                for base_c in (c1, c2):
                    fin_box = Grid.box_of(fin_r, base_c)
                    if not all(Grid.box_of(fin_r, fc) == fin_box for fc in fins):
                        continue
                    # Eliminate d from cells in fin_box, in column base_c, not in chain
                    elim_rows = [r for r, _ in Grid.cells_of_box(fin_box)
                                 if r not in (clean_r, fin_r)]
                    eliminations = [
                        (r, base_c, d) for r in elim_rows
                        if grid.values[r][base_c] == 0
                        and d in grid.candidates[r][base_c]
                    ]
                    if eliminations:
                        fin_names = ", ".join(cell_name(fin_r, fc) for fc in fins)
                        return Step(
                            strategy="Finned X-Wing",
                            eliminations=eliminations,
                            pattern_cells=(
                                [(clean_r, c1), (clean_r, c2),
                                 (fin_r,   c1), (fin_r,   c2)]
                                + [(fin_r, fc) for fc in fins]
                            ),
                            explanation=(
                                f"Finned X-Wing for digit {d}: rows {clean_r+1} and "
                                f"{fin_r+1} share an X-Wing base in columns {c1+1},{c2+1}. "
                                f"Row {fin_r+1} also has fin(s) at {fin_names} "
                                f"(all in box {fin_box+1}). The fins restrict eliminations "
                                f"to column {base_c+1} within box {fin_box+1}."
                            ),
                        )

        # ── Column-based ─────────────────────────────────────────────────────
        col_cands: dict = {}
        for c in range(9):
            rows = [r for r in range(9)
                    if grid.values[r][c] == 0 and d in grid.candidates[r][c]]
            if 2 <= len(rows) <= 4:
                col_cands[c] = rows

        for c1, c2 in combinations(col_cands, 2):
            for clean_c, fin_c in ((c1, c2), (c2, c1)):
                clean_rows = set(col_cands[clean_c])
                fin_rows   = set(col_cands[fin_c])
                if len(clean_rows) != 2:
                    continue
                if not clean_rows.issubset(fin_rows):
                    continue
                r1, r2 = tuple(clean_rows)
                fins = [r for r in fin_rows if r not in clean_rows]
                if not fins:
                    continue
                for base_r in (r1, r2):
                    fin_box = Grid.box_of(base_r, fin_c)
                    if not all(Grid.box_of(fr, fin_c) == fin_box for fr in fins):
                        continue
                    elim_cols = [c for _, c in Grid.cells_of_box(fin_box)
                                 if c not in (clean_c, fin_c)]
                    eliminations = [
                        (base_r, c, d) for c in elim_cols
                        if grid.values[base_r][c] == 0
                        and d in grid.candidates[base_r][c]
                    ]
                    if eliminations:
                        fin_names = ", ".join(cell_name(fr, fin_c) for fr in fins)
                        return Step(
                            strategy="Finned X-Wing",
                            eliminations=eliminations,
                            pattern_cells=(
                                [(r1, clean_c), (r1, fin_c),
                                 (r2, clean_c), (r2, fin_c)]
                                + [(fr, fin_c) for fr in fins]
                            ),
                            explanation=(
                                f"Finned X-Wing for digit {d}: columns {clean_c+1} and "
                                f"{fin_c+1} share an X-Wing base in rows {r1+1},{r2+1}. "
                                f"Column {fin_c+1} also has fin(s) at {fin_names}. "
                                f"Eliminations restricted to row {base_r+1} within "
                                f"box {fin_box+1}."
                            ),
                        )
    return None


def find_xy_chain(grid: Grid) -> Optional[Step]:
    """
    XY-Chain: A chain of bi-value cells C1–C2–…–Cn where:
    - Each consecutive pair sees each other and shares one candidate (the link).
    - The non-linked digit at C1 equals the non-linked digit at Cn (call it X).
    One of the two end-cells must hold X, so any cell seeing both ends can
    eliminate X.
    """
    bivs = [
        (r, c) for r in range(9) for c in range(9)
        if grid.values[r][c] == 0 and len(grid.candidates[r][c]) == 2
    ]
    MAX_LEN = 8

    for start in bivs:
        sr, sc = start
        cands_s = grid.candidates[sr][sc]

        for free_digit in cands_s:
            # DFS state: (current, link_in, path, visited)
            # link_in is the digit "used up" arriving at current from the left.
            # Setting link_in = free_digit for the start means current's free end = link_digit,
            # which is the digit going OUT to the first real cell in the chain.
            stack = [(start, free_digit, (start,), frozenset([start]))]
            while stack:
                cur, link_in, path, visited = stack.pop()
                cr, cc = cur
                cur_cands = grid.candidates[cr][cc]
                # free end of cur = the digit NOT = link_in
                cur_free = next(d for d in cur_cands if d != link_in)

                if len(path) >= 3 and cur_free == free_digit:
                    eliminations = [
                        (r, c, free_digit)
                        for r in range(9) for c in range(9)
                        if (r, c) not in visited
                        and grid.values[r][c] == 0
                        and free_digit in grid.candidates[r][c]
                        and grid.cell_sees(r, c, sr, sc)
                        and grid.cell_sees(r, c, cr, cc)
                    ]
                    if eliminations:
                        return Step(
                            strategy="XY-Chain",
                            eliminations=eliminations,
                            pattern_cells=list(path),
                            explanation=(
                                f"XY-Chain ({len(path)} cells): "
                                f"{cell_name(sr,sc)} → … → {cell_name(cr,cc)}. "
                                f"Both endpoints have {free_digit} as their free digit. "
                                f"One endpoint must hold {free_digit}, so any cell "
                                f"seeing both ends cannot contain {free_digit}."
                            ),
                        )

                if len(path) >= MAX_LEN:
                    continue

                # cur_free becomes the link_in to the next cell
                for nxt in bivs:
                    if nxt in visited:
                        continue
                    nr, nc = nxt
                    if not grid.cell_sees(cr, cc, nr, nc):
                        continue
                    if cur_free not in grid.candidates[nr][nc]:
                        continue
                    stack.append((nxt, cur_free, path + (nxt,),
                                  visited | {nxt}))
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Strategy Registry
# ─────────────────────────────────────────────────────────────────────────────

ALL_STRATEGIES = [
    ("Full House",         find_full_house),
    ("Naked Single",       find_naked_single),
    ("Hidden Single",      find_hidden_single),
    ("Naked Pair",         lambda g: find_naked_set(g, 2)),
    ("Hidden Pair",        lambda g: find_hidden_set(g, 2)),
    ("Naked Triple",       lambda g: find_naked_set(g, 3)),
    ("Hidden Triple",      lambda g: find_hidden_set(g, 3)),
    ("Naked Quad",         lambda g: find_naked_set(g, 4)),
    ("Hidden Quad",        lambda g: find_hidden_set(g, 4)),
    ("Pointing Pairs",     find_pointing_pairs),
    ("Box-Line Reduction", find_box_line_reduction),
    ("X-Wing",             find_x_wing),
    ("Swordfish",          find_swordfish),
    ("Jellyfish",          find_jellyfish),
    ("Squirmbag",          find_squirmbag),
    ("Y-Wing",             find_y_wing),
    ("XYZ-Wing",           find_xyz_wing),
    ("Simple Coloring",    find_simple_coloring),
    # Tier 4
    ("Unique Rectangle",   find_unique_rectangle),
    ("W-Wing",             find_w_wing),
    ("Skyscraper",         find_skyscraper),
    ("2-String Kite",      find_2_string_kite),
    ("BUG+1",              find_bug_plus_1),
    # Tier 5
    ("Finned X-Wing",      find_finned_x_wing),
    ("XY-Chain",           find_xy_chain),
]


# ─────────────────────────────────────────────────────────────────────────────
# Interactive Prompt
# ─────────────────────────────────────────────────────────────────────────────

def prompt_continue(show_cands: list) -> str:
    """Prompt user for next action. Returns '', 'c', or 'q'."""
    prompt = f"  {DIM}[Enter]=next  [c]=toggle candidates  [q]=quit{RESET} > "
    try:
        line = input(prompt).strip().lower()
    except (EOFError, KeyboardInterrupt):
        return 'q'
    if line == 'c':
        show_cands[0] = not show_cands[0]
        return 'c'
    if line == 'q':
        return 'q'
    return ''


# ─────────────────────────────────────────────────────────────────────────────
# Solver
# ─────────────────────────────────────────────────────────────────────────────

def solve(grid: Grid, auto_mode: bool):
    """Main solver loop with step-by-step tutor explanations."""
    show_cands = [True]
    step_count = 0
    strategies_used = []

    print(f"\n{BOLD}{'='*54}")
    print(f"  Sudoku Tutor — Human Strategy Solver")
    print(f"{'='*54}{RESET}")

    print("\nInitial puzzle:")
    if show_cands[0]:
        print_grid_with_candidates(grid)
    else:
        print_grid_clean(grid)

    if not auto_mode:
        try:
            input(f"  {DIM}Press Enter to begin solving...{RESET}")
        except (EOFError, KeyboardInterrupt):
            return

    while not grid.is_solved():
        step = None
        for _, fn in ALL_STRATEGIES:
            step = fn(grid)
            if step:
                break

        if step is None:
            print(f"\n{RED}{BOLD}No further progress possible.{RESET}")
            last = strategies_used[-1] if strategies_used else "none"
            print(f"  Last successful strategy: {CYAN}{last}{RESET}")
            print(
                f"  This puzzle requires techniques beyond the 16 implemented "
                f"strategies,\n  or requires bifurcation (trial-and-error). "
                f"The tutor cannot proceed further."
            )
            print(f"\nPartial solution after {step_count} steps:")
            if show_cands[0]:
                print_grid_with_candidates(grid)
            else:
                print_grid_clean(grid)
            return

        step_count += 1
        strategies_used.append(step.strategy)
        highlight = [(r, c) for r, c, _ in step.placements + step.eliminations]

        print(format_step(step))
        grid.apply_step(step)

        if show_cands[0]:
            print_grid_with_candidates(grid, highlight=highlight)
        else:
            print_grid_clean(grid, highlight=highlight)

        if not auto_mode:
            key = prompt_continue(show_cands)
            while key == 'c':
                if show_cands[0]:
                    print_grid_with_candidates(grid, highlight=highlight)
                else:
                    print_grid_clean(grid, highlight=highlight)
                key = prompt_continue(show_cands)
            if key == 'q':
                print(f"\n  Quit after {step_count} steps.")
                return

    unique_strategies = list(dict.fromkeys(strategies_used))
    print(f"\n{GREEN}{BOLD}Puzzle solved in {step_count} steps!{RESET}")
    print(f"  Strategies used: {', '.join(unique_strategies)}")
    print_grid_clean(grid)


# ─────────────────────────────────────────────────────────────────────────────
# Puzzle I/O
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_PUZZLE = [
    [5, 3, 0, 0, 7, 0, 0, 0, 0],
    [6, 0, 0, 1, 9, 5, 0, 0, 0],
    [0, 9, 8, 0, 0, 0, 0, 6, 0],
    [8, 0, 0, 0, 6, 0, 0, 0, 3],
    [4, 0, 0, 8, 0, 3, 0, 0, 1],
    [7, 0, 0, 0, 2, 0, 0, 0, 6],
    [0, 6, 0, 0, 0, 0, 2, 8, 0],
    [0, 0, 0, 4, 1, 9, 0, 0, 5],
    [0, 0, 0, 0, 8, 0, 0, 7, 9],
]


def read_puzzle(filename: str) -> Optional[list]:
    """Read puzzle from file: 9 lines of 9 digits, 0=empty."""
    try:
        board = []
        with open(filename, 'r') as f:
            for line in f:
                line = line.strip()
                if len(line) == 9 and line.isdigit():
                    board.append([int(d) for d in line])
        return board if len(board) == 9 else None
    except FileNotFoundError:
        return None
    except Exception as e:
        print(f"Error reading puzzle: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Sudoku Tutor — solves puzzles using human strategies "
            "and explains every step."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Strategies (applied in order):\n"
            "  Tier 1: Full House, Naked Single, Hidden Single\n"
            "  Tier 2: Naked/Hidden Pairs/Triples/Quads,\n"
            "          Pointing Pairs/Triples, Box-Line Reduction\n"
            "  Tier 3: X-Wing, Swordfish, Y-Wing, XYZ-Wing, Simple Coloring\n"
        ),
    )
    parser.add_argument(
        "puzzle_file", nargs="?", default=None,
        help="Puzzle file (9 lines of 9 digits, 0=empty). Default: sd0.txt",
    )
    parser.add_argument(
        "--auto", action="store_true",
        help="Auto mode: solve without pausing (full log output)",
    )
    args = parser.parse_args()

    if args.puzzle_file:
        values = read_puzzle(args.puzzle_file)
        if values is None:
            print(f"Error: could not read puzzle from '{args.puzzle_file}'")
            sys.exit(1)
        print(f"Loaded: {args.puzzle_file}")
    else:
        values = read_puzzle("sd0.txt")
        if values is not None:
            print("Loaded: sd0.txt")
        else:
            print("Using built-in default puzzle (classic example).")
            values = DEFAULT_PUZZLE

    grid = Grid(values)
    solve(grid, auto_mode=args.auto)


if __name__ == "__main__":
    main()
