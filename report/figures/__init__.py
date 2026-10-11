"""
The article's figures, one module per figure.

Each figure is a module in this package named for what it shows
(group_specificity_by_window.py, not figure_two.py, because figure numbers
change while the article is written and the manuscript's \\includegraphics
maps the number to the name). A module defines two functions:

    def data(dirs) -> pd.DataFrame
        The table the figure plots, read from the model inputs in
        data/<dataset>/model_inputs/ and the estimates in
        results/estimates/. Nothing is aggregated or re-indexed
        here beyond what the figure needs to draw; an aggregate that a
        model also uses belongs in preprocessing, and a bootstrap interval
        over games comes from report.bootstrap.

    def plot(df: pd.DataFrame) -> matplotlib.figure.Figure
        The figure, drawn from that table alone with the palette, labels
        and sizes of report.plot_style and nothing of its own.

The runner (`uv run python -m report.figures --dataset full`, or `make
figures`) calls both for every module and saves the figure as
results/figures/<name>.pdf with the plotted table beside it as
<name>.csv, so every number in a figure can be read, checked and diffed
without the PDF. `make sync` copies the PDFs into the manuscript's project.

Tests: report/test_figures.py
"""

from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from report.plot_style import apply_style


def figure_names() -> list[str]:
    """The figure modules in this package, in name order (private modules excluded)."""
    package_dir = Path(__file__).parent
    return sorted(
        info.name for info in pkgutil.iter_modules([str(package_dir)]) if not info.name.startswith("_")
    )


def save_figure(fig, data: pd.DataFrame, name: str, figures_dir: Path) -> tuple[Path, Path]:
    """Save a figure as <name>.pdf and its plotted table as <name>.csv in figures_dir, and close it."""
    figures_dir = Path(figures_dir)
    figures_dir.mkdir(parents=True, exist_ok=True)
    pdf = figures_dir / f"{name}.pdf"
    csv = figures_dir / f"{name}.csv"
    fig.savefig(pdf)
    plt.close(fig)
    data.to_csv(csv, index=False)
    return pdf, csv


def run_figure(module, dirs) -> tuple[Path, Path]:
    """Build one figure module's table and figure for a dataset and save both."""
    name = module.__name__.rsplit(".", 1)[-1]
    df = module.data(dirs)
    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"{name}.data() must return a DataFrame, not {type(df).__name__}")
    fig = module.plot(df)
    return save_figure(fig, df, name, dirs.figures)


def run_figures(dirs, names: list[str] | None = None) -> list[tuple[Path, Path]]:
    """Run every figure module (or the named ones) for a dataset; returns the files written."""
    apply_style()
    selected = names or figure_names()
    unknown = sorted(set(selected) - set(figure_names()))
    if unknown:
        raise SystemExit(f"Error: no figure module named {', '.join(unknown)} in report/figures/")
    written = []
    for name in selected:
        module = importlib.import_module(f"report.figures.{name}")
        pdf, csv = run_figure(module, dirs)
        print(f"Wrote {pdf} and {csv.name}")
        written.append((pdf, csv))
    if not written:
        print("No figure modules in report/figures/ yet; nothing written.")
    return written
