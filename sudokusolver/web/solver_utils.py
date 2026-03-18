"""
solver_utils.py — Pygame-free utility functions copied from sudoku_gui.py.
"""

from sudoku_tutor import Grid, Step

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


def rate_puzzle(steps: list[Step]) -> int:
    if not steps:
        return 0
    return max(STRATEGY_TIER.get(s.strategy, 0) for s in steps)
