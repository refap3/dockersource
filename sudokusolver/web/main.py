"""
main.py — FastAPI web application for the Sudoku Tutor.
"""

import asyncio
import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .solver_utils import validate_board, _bt_solve
from .serializers import compute_solve_result, step_to_dict, grid_to_dict
from .image_utils import extract_puzzle_from_bytes, ExtractionError

# ── Optional imports ───────────────────────────────────────────────────────────
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

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="Sudoku Tutor Web")

# ── Pydantic models ────────────────────────────────────────────────────────────

class GridPayload(BaseModel):
    values: list[list[int]]

class GeneratePayload(BaseModel):
    tier: int = 2


# ── API routes ─────────────────────────────────────────────────────────────────

@app.post("/api/solve")
async def api_solve(payload: GridPayload):
    try:
        result = await asyncio.to_thread(compute_solve_result, payload.values)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/validate")
async def api_validate(payload: GridPayload):
    conflicts = validate_board(payload.values)
    return {"conflict_cells": [{"r": r, "c": c} for r, c in conflicts]}


@app.post("/api/brute-force")
async def api_brute_force(payload: GridPayload):
    iters = [0]
    def _run():
        grid = [row[:] for row in payload.values]
        solution = _bt_solve(grid, iters)
        return solution, iters[0]

    solution, iterations = await asyncio.to_thread(_run)
    if solution is None:
        raise HTTPException(status_code=422, detail="No solution found")
    return {"solution": solution, "iterations": iterations}


@app.get("/api/puzzles")
async def api_puzzles():
    if not HAS_PUZZLES:
        return []
    result = []
    for i, p in enumerate(PUZZLES):
        rows = p["rows"]
        values = [[int(rows[r][c]) for c in range(9)] for r in range(9)]
        result.append({
            "id": i,
            "name": p["name"],
            "tier": p["tier"],
            "values": values,
        })
    return result


@app.get("/api/puzzles/{puzzle_id}")
async def api_puzzle(puzzle_id: int):
    if not HAS_PUZZLES or puzzle_id < 0 or puzzle_id >= len(PUZZLES):
        raise HTTPException(status_code=404, detail="Puzzle not found")
    p = PUZZLES[puzzle_id]
    rows = p["rows"]
    values = [[int(rows[r][c]) for c in range(9)] for r in range(9)]
    return {"id": puzzle_id, "name": p["name"], "tier": p["tier"], "values": values}


@app.post("/api/generate")
async def api_generate(payload: GeneratePayload):
    if not HAS_GENERATOR:
        raise HTTPException(status_code=501, detail="Generator not available")
    def _run():
        return generate_puzzle(tier=payload.tier)
    values = await asyncio.to_thread(_run)
    return {"values": values}


@app.post("/api/extract-image")
async def api_extract_image(request: Request, file: UploadFile = File(...)):
    # Key priority: request header > environment variable
    api_key = request.headers.get("X-Anthropic-Key", "").strip() or os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise HTTPException(status_code=400, detail="ANTHROPIC_API_KEY not configured")
    image_bytes = await file.read()
    try:
        values = await asyncio.to_thread(extract_puzzle_from_bytes, image_bytes, api_key)
    except ExtractionError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Extraction failed: {e}")
    return {"values": values}


@app.get("/api/config")
async def api_config():
    return {
        "has_anthropic_key": bool(os.environ.get("ANTHROPIC_API_KEY", "")),
        "has_generator": HAS_GENERATOR,
        "has_puzzles": HAS_PUZZLES,
    }


# ── Static files & SPA fallback ────────────────────────────────────────────────
app.mount("/static", StaticFiles(directory=str(STATIC_DIR), html=False), name="static")

@app.get("/")
async def index():
    return FileResponse(
        str(STATIC_DIR / "index.html"),
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )
