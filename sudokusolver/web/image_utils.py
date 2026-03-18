"""
image_utils.py — Image-to-puzzle extraction via Claude Vision API (no pygame dependency).
"""

import io
import re
import base64
from .solver_utils import validate_board


class ExtractionError(Exception):
    pass


def extract_puzzle_from_bytes(image_bytes: bytes, api_key: str) -> list[list[int]]:
    """
    Send image bytes to Claude vision API and return a 9×9 grid of ints.
    Raises ExtractionError on any failure.
    """
    try:
        import anthropic
    except ImportError:
        raise ExtractionError("anthropic package not installed")

    try:
        from PIL import Image
    except ImportError:
        raise ExtractionError("Pillow package not installed")

    # Convert to PNG bytes (normalise format)
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()

    client = anthropic.Anthropic(api_key=api_key)
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

    raw = next(b.text for b in resp.content if b.type == "text")

    vals = []
    for raw_line in raw.splitlines():
        digits = re.sub(r"[.\-_]", "0", raw_line)
        digits = re.sub(r"[^0-9]", "", digits)
        if len(digits) == 9:
            vals.append([int(d) for d in digits])

    if len(vals) != 9:
        raise ExtractionError(
            f"Could not parse a 9×9 grid from the image. Got {len(vals)} valid row(s)."
        )

    return vals
