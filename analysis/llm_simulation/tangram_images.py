#!/usr/bin/env python3
"""Utility for loading tangram SVGs and converting to PNG bytes for the Gemini vision API."""

from pathlib import Path

import cairosvg


# Default path to tangram SVGs (relative to repo root)
DEFAULT_SVG_DIR = Path(__file__).parent.parent.parent / "experiment" / "client" / "public"


def load_tangram_pngs(
    tangram_ids: list[str],
    svg_dir: Path = DEFAULT_SVG_DIR,
    size: int = 400,
) -> dict[str, bytes]:
    """Load tangram SVGs and convert to PNG bytes.

    Args:
        tangram_ids: List of tangram IDs (e.g., ["page7-255", "page9-46", ...]).
        svg_dir: Directory containing tangram_*.svg files.
        size: Output PNG size in pixels (square).

    Returns:
        Dict mapping tangram_id -> PNG bytes.
    """
    images = {}
    for tid in tangram_ids:
        svg_path = svg_dir / f"tangram_{tid}.svg"
        if not svg_path.exists():
            raise FileNotFoundError(f"Tangram SVG not found: {svg_path}")
        png_bytes = cairosvg.svg2png(
            url=str(svg_path), output_width=size, output_height=size
        )
        images[tid] = png_bytes
    return images
