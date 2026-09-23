---
paths:
  - "**/*.py"
  - "pyproject.toml"
---

# Python Environment

This project uses [uv](https://docs.astral.sh/uv/) for Python dependency management, with the dependencies declared in `pyproject.toml`. The R side is restored with `renv::restore()`.

Two dependencies need something beyond `uv sync`: `rpy2` requires R to be installed, and the Cairo-based packages (`cairosvg`) may need `brew install cairo pango`.
