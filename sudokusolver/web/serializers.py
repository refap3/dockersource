"""
serializers.py — Convert internal objects to JSON-serialisable dicts.
"""

from sudoku_tutor import Grid, Step, ALL_STRATEGIES
from .solver_utils import STRATEGY_TIER, validate_board, rate_puzzle


def grid_to_dict(grid: Grid) -> dict:
    return {
        "values": [row[:] for row in grid.values],
        "givens": [row[:] for row in grid.givens],
        "candidates": [
            [sorted(grid.candidates[r][c]) for c in range(9)]
            for r in range(9)
        ],
    }


def step_to_dict(step: Step, index: int) -> dict:
    return {
        "index": index,
        "strategy": step.strategy,
        "tier": STRATEGY_TIER.get(step.strategy, 0),
        "explanation": step.explanation,
        "placements": [
            {"r": r, "c": c, "d": d} for r, c, d in step.placements
        ],
        "eliminations": [
            {"r": r, "c": c, "d": d} for r, c, d in step.eliminations
        ],
        "house_type": step.house_type,
        "house_index": step.house_index,
        "pattern_cells": [
            {"r": r, "c": c} for r, c in step.pattern_cells
        ],
    }


def compute_solve_result(values: list[list[int]]) -> dict:
    """Run full human-strategy solve and return JSON-ready result dict."""
    conflicts = validate_board(values)
    if conflicts:
        return {
            "steps": [],
            "grid_states": [],
            "stuck": False,
            "difficulty": 0,
            "conflict_cells": [{"r": r, "c": c} for r, c in conflicts],
        }

    grid = Grid(values)
    grid_states = [grid_to_dict(grid)]
    steps = []

    while not grid.is_solved():
        step = None
        for _, fn in ALL_STRATEGIES:
            step = fn(grid)
            if step:
                break
        if step is None:
            break
        steps.append(step_to_dict(step, len(steps)))
        grid.apply_step(step)
        grid_states.append(grid_to_dict(grid))

    return {
        "steps": steps,
        "grid_states": grid_states,
        "stuck": not grid.is_solved(),
        "difficulty": rate_puzzle([
            Step(strategy=s["strategy"], explanation="", placements=[], eliminations=[])
            for s in steps
        ]),
        "conflict_cells": [],
    }
