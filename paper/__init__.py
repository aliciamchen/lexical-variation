"""The paper layer: the Python side of the article, from the estimates tables and the processed tables to the macros and the figures.

`inferential.py` formats the model estimates into the three inferential macro files, `descriptives.py` writes the
three descriptive ones, `figures/` holds one module per figure, `plot_style.py` is the one description of how the
figures look, `bootstrap.py` the one bootstrap over games and `stats_tex.py` the macro writer and its formatting
rules. The modules import the pipeline as a package, so run them from the repository root as modules, for example
`uv run python -m paper.inferential --dataset full`; `make paper` runs them all.
"""
