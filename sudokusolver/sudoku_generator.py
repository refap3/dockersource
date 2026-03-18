#!/usr/bin/env python3
"""
sudoku_generator.py — Sudoku Puzzle Generator

Generates valid Sudoku puzzles at a target difficulty tier using
randomised backtracking for solution generation and human-strategy
rating (via sudoku_tutor.py) for difficulty classification.

Difficulty tiers mirror those in sudoku_tutor.py:
  Tier 0 — Really Easy : Full House and Naked Single only
  Tier 1 — Beginner    : Full House, Naked Single, Hidden Single
  Tier 2 — Intermediate: Naked/Hidden Pairs/Triples/Quads,
                          Pointing Pairs, Box-Line Reduction
  Tier 3 — Advanced    : X-Wing, Swordfish, Y-Wing, XYZ-Wing, Simple Coloring
  Tier 4 — Expert      : Unique Rectangle, W-Wing, Skyscraper,
                          2-String Kite, BUG+1
"""

import random
from copy import deepcopy
from typing import Optional

from sudoku_tutor import Grid, Step, ALL_STRATEGIES

# ─────────────────────────────────────────────────────────────────────────────
# Tier mapping: strategy name → difficulty tier (1=easiest, 4=hardest)
# ─────────────────────────────────────────────────────────────────────────────

STRATEGY_TIER = {
    "Full House": 1, "Naked Single": 1, "Hidden Single": 1,
    "Naked Pair": 2, "Hidden Pair": 2, "Naked Triple": 2, "Hidden Triple": 2,
    "Naked Quad": 2, "Hidden Quad": 2, "Pointing Pairs": 2, "Box-Line Reduction": 2,
    "X-Wing": 3, "Swordfish": 3, "Y-Wing": 3, "XYZ-Wing": 3, "Simple Coloring": 3,
    "Unique Rectangle": 4, "W-Wing": 4, "Skyscraper": 4, "2-String Kite": 4, "BUG+1": 4,
}

# Target empty-cell ranges per tier.  These are tuned empirically and act as
# a soft guide; the uniqueness constraint is always the hard stop.
_EMPTY_RANGE = {
    0: (25, 36),   # Really Easy: very few holes, all naked/full-house solvable
    1: (45, 55),
    2: (55, 62),
    3: (60, 64),
    4: (64, 70),
}

# Strategy names that qualify as tier-0 (really easy)
_TIER0_STRATEGY_NAMES = {"Full House", "Naked Single"}


# ─────────────────────────────────────────────────────────────────────────────
# Solution Generator
# ─────────────────────────────────────────────────────────────────────────────

def generate_solution(seed: int | None = None) -> list[list[int]]:
    """Generate a complete valid Sudoku solution using randomised backtracking.

    Parameters
    ----------
    seed:
        Optional RNG seed for reproducible puzzles.

    Returns
    -------
    A 9×9 list of ints (1–9), representing a fully-filled, valid Sudoku grid.
    """
    rng = random.Random(seed)
    grid = [[0] * 9 for _ in range(9)]

    def _is_valid(r: int, c: int, d: int) -> bool:
        # Check row
        if d in grid[r]:
            return False
        # Check column
        if any(grid[rr][c] == d for rr in range(9)):
            return False
        # Check 3×3 box
        br, bc = (r // 3) * 3, (c // 3) * 3
        for dr in range(3):
            for dc in range(3):
                if grid[br + dr][bc + dc] == d:
                    return False
        return True

    def _backtrack(pos: int) -> bool:
        if pos == 81:
            return True
        r, c = divmod(pos, 9)
        digits = list(range(1, 10))
        rng.shuffle(digits)
        for d in digits:
            if _is_valid(r, c, d):
                grid[r][c] = d
                if _backtrack(pos + 1):
                    return True
                grid[r][c] = 0
        return False

    _backtrack(0)
    return grid


# ─────────────────────────────────────────────────────────────────────────────
# Unique-Solution Check
# ─────────────────────────────────────────────────────────────────────────────

def _has_unique_solution(grid: list[list[int]]) -> bool:
    """Return True iff the puzzle has exactly one solution.

    Uses a lightweight backtracking solver that stops as soon as a second
    solution is discovered, keeping the check fast even for hard puzzles.
    """
    # Work on a mutable copy
    work = [row[:] for row in grid]
    count = [0]  # mutable counter accessible from nested function

    def _candidates(r: int, c: int) -> list[int]:
        used = set()
        used.update(work[r])
        used.update(work[rr][c] for rr in range(9))
        br, bc = (r // 3) * 3, (c // 3) * 3
        for dr in range(3):
            for dc in range(3):
                used.add(work[br + dr][bc + dc])
        return [d for d in range(1, 10) if d not in used]

    def _solve() -> bool:
        """Return True to signal early exit (second solution found)."""
        # Find the first empty cell (simple left-to-right, top-to-bottom scan)
        for pos in range(81):
            r, c = divmod(pos, 9)
            if work[r][c] == 0:
                for d in _candidates(r, c):
                    work[r][c] = d
                    if _solve():
                        return True
                    work[r][c] = 0
                return False  # dead end
        # All cells filled — one more solution found
        count[0] += 1
        return count[0] >= 2  # True stops recursion early

    _solve()
    return count[0] == 1


# ─────────────────────────────────────────────────────────────────────────────
# Difficulty Rater
# ─────────────────────────────────────────────────────────────────────────────

def _rate_difficulty(values: list[list[int]]) -> int:
    """Rate puzzle difficulty by simulating human-strategy solving.

    Applies ALL_STRATEGIES in order (hardest tried last only when easier ones
    are exhausted) until the puzzle is solved or no strategy fires.

    Returns
    -------
    int
        The highest tier of any strategy used, 1–4.
        Returns 0 if the puzzle cannot be solved by the implemented strategies
        (i.e. it requires bifurcation / trial-and-error).
    """
    grid = Grid(values)
    max_tier = 0

    while not grid.is_solved():
        found = False
        for name, fn in ALL_STRATEGIES:
            step = fn(grid)
            if step is not None:
                tier = STRATEGY_TIER.get(step.strategy, STRATEGY_TIER.get(name, 0))
                if tier > max_tier:
                    max_tier = tier
                grid.apply_step(step)
                found = True
                break  # restart strategy loop from the easiest strategy
        if not found:
            return 0  # stuck — unsolvable by human strategies

    return max_tier


def _is_tier0(values: list[list[int]]) -> bool:
    """Return True iff the puzzle is solvable using only Full House and Naked Single.

    These are the two simplest strategies: a cell either is the last empty in
    its house (Full House) or has exactly one remaining candidate (Naked Single).
    No candidate-elimination reasoning is required.
    """
    grid = Grid(values)
    tier0_fns = [(name, fn) for name, fn in ALL_STRATEGIES
                 if name in _TIER0_STRATEGY_NAMES]
    while not grid.is_solved():
        found = False
        for name, fn in tier0_fns:
            step = fn(grid)
            if step is not None:
                grid.apply_step(step)
                found = True
                break
        if not found:
            return False
    return True


# ─────────────────────────────────────────────────────────────────────────────
# Puzzle Generator
# ─────────────────────────────────────────────────────────────────────────────

def generate_puzzle(
    target_tier: int = 2,
    max_attempts: int = 100,
    seed: int | None = None,
) -> Optional[list[list[int]]]:
    """Generate a Sudoku puzzle at the requested difficulty tier.

    Algorithm
    ---------
    1. Generate a complete, random solution.
    2. Collect all 81 cells in a random order.
    3. Remove cells one by one; after each removal verify that the puzzle
       still has a unique solution.  Skip cells whose removal would create
       multiple solutions.
    4. Stop the removal loop when either:
         a. Every cell has been visited, or
         b. The number of empty cells reaches the upper bound for the tier.
    5. Rate the resulting puzzle.  Accept it when the rated tier is within
       ±1 of the target, or when target_tier >= 4 and the puzzle needs brute
       force (rated 0).
    6. Retry up to *max_attempts* times if no acceptable puzzle is found.

    Parameters
    ----------
    target_tier:
        Desired difficulty, 0–4.  Tier 0 produces really-easy puzzles
        solvable by Full House and Naked Single alone.
    max_attempts:
        Maximum number of generation attempts before giving up.
    seed:
        Optional RNG seed.  Each attempt uses a derived seed so results are
        reproducible while still varying across attempts.

    Returns
    -------
    A 9×9 list of ints (0 = empty cell), or None if generation failed.
    """
    rng = random.Random(seed)
    empty_min, empty_max = _EMPTY_RANGE.get(target_tier, (45, 55))

    for attempt in range(max_attempts):
        # Derive a per-attempt seed so each attempt explores a different space
        attempt_seed = rng.randint(0, 2**31 - 1)
        solution = generate_solution(seed=attempt_seed)

        # Start with the full solution; we will punch holes in it
        puzzle = [row[:] for row in solution]

        # Random cell removal order
        attempt_rng = random.Random(attempt_seed)
        cells = list(range(81))
        attempt_rng.shuffle(cells)

        empty_count = 0
        for pos in cells:
            r, c = divmod(pos, 9)
            saved = puzzle[r][c]
            puzzle[r][c] = 0

            if _has_unique_solution(puzzle):
                empty_count += 1
                if empty_count >= empty_max:
                    break  # hit the upper bound for this tier
            else:
                # Restore — removing this cell breaks uniqueness
                puzzle[r][c] = saved

        # Only proceed if we have at least the minimum number of empty cells
        if empty_count < empty_min:
            continue

        # Rate the puzzle
        if target_tier == 0:
            # Tier-0: must be solvable by Full House + Naked Single only
            acceptable = _is_tier0(puzzle)
        else:
            tier = _rate_difficulty(puzzle)
            # Accept criteria:
            #   - Exact tier match, or within ±1
            #   - For tier-4 target: also accept unsolvable-by-strategies (tier==0),
            #     which means the puzzle genuinely needs expert techniques or guessing
            acceptable = (
                abs(tier - target_tier) <= 1
                or (target_tier >= 4 and tier == 0)
            )

        if acceptable:
            return puzzle

    # All attempts exhausted
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Quick self-test
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    tier = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else None

    print(f"Generating tier-{tier} puzzle (seed={seed}) …")
    puzzle = generate_puzzle(target_tier=tier, max_attempts=100, seed=seed)

    if puzzle is None:
        print("Failed to generate a puzzle within 100 attempts.")
        sys.exit(1)

    empty = sum(1 for r in range(9) for c in range(9) if puzzle[r][c] == 0)
    if tier == 0:
        rated_str = "0 (Really Easy)" if _is_tier0(puzzle) else "1+ (not pure tier-0)"
    else:
        rated = _rate_difficulty(puzzle)
        rated_str = str(rated)
    print(f"  Empty cells : {empty}")
    print(f"  Rated tier  : {rated_str}")
    print()
    for row in puzzle:
        print(" ".join(str(d) if d else "." for d in row))
