"""
Tests for the figure runner (report/figures/): module discovery, and that a
figure module's table and figure land beside each other.

Run with:
    uv run pytest report/test_figures.py -v
"""

import types

import matplotlib
import pandas as pd
import pytest

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from report.figures import figure_names, run_figure, save_figure  # noqa: E402


def test_figure_names_lists_only_public_modules():
    names = figure_names()
    assert all(not n.startswith("_") for n in names)
    assert names == sorted(names)


def test_save_figure_writes_the_pdf_and_the_table_side_by_side(tmp_path):
    fig, ax = plt.subplots()
    ax.plot([1, 2], [3, 4])
    pdf, csv = save_figure(fig, pd.DataFrame({"x": [1, 2], "y": [3, 4]}), "example", tmp_path / "figures")
    assert pdf == tmp_path / "figures" / "example.pdf" and pdf.stat().st_size > 0
    assert csv.read_text().splitlines() == ["x,y", "1,3", "2,4"]


def test_run_figure_calls_data_then_plot_and_names_the_files_after_the_module(tmp_path):
    module = types.ModuleType("report.figures.block_means")

    def data(dirs):
        return pd.DataFrame({"block": [1, 2], "mean": [0.4, 0.5]})

    def plot(df):
        fig, ax = plt.subplots()
        ax.plot(df["block"], df["mean"])
        return fig

    module.data, module.plot = data, plot
    dirs = types.SimpleNamespace(figures=tmp_path / "figures")
    pdf, csv = run_figure(module, dirs)
    assert pdf.name == "block_means.pdf" and csv.name == "block_means.csv"
    assert pd.read_csv(csv)["mean"].tolist() == [0.4, 0.5]


def test_run_figure_refuses_a_module_whose_data_is_not_a_table(tmp_path):
    module = types.ModuleType("report.figures.bad")
    module.data = lambda dirs: [1, 2]
    module.plot = lambda df: plt.figure()
    with pytest.raises(TypeError, match="must return a DataFrame"):
        run_figure(module, types.SimpleNamespace(figures=tmp_path))
