"""Draw the article's figures: `uv run python -m paper.figures --dataset full [name ...]`."""

from __future__ import annotations

import argparse

from pipeline.dataset_paths import add_dataset_argument, dataset_dirs
from paper.figures import figure_names, run_figures


def main():
    parser = argparse.ArgumentParser(description="Draw the article's figures for one dataset into results/<dataset>/figures/")
    add_dataset_argument(parser)
    parser.add_argument("names", nargs="*", help=f"figure modules to draw (default: all of {', '.join(figure_names()) or 'none yet'})")
    args = parser.parse_args()
    dirs = dataset_dirs(args.dataset)
    if not dirs.model_inputs.is_dir():
        raise SystemExit(f"Error: no model inputs for dataset '{dirs.name}' at {dirs.model_inputs}; run `make data` first")
    if dirs.name != "full":
        print(f"Dataset '{dirs.name}' is not the full sample: the figures written to {dirs.figures} are not results.")
    run_figures(dirs, args.names)


if __name__ == "__main__":
    main()
