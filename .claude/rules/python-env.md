---
paths:
  - "**/*.py"
  - "pyproject.toml"
---

# Python Environment

This project uses [uv](https://docs.astral.sh/uv/) for Python dependency management, with the dependencies declared in `pyproject.toml`. The R side is restored with `renv::restore()`.

`uv sync` is the whole Python setup. The heavy dependency is the sentence-transformer stack behind the derived metrics; everything else is small. Only packages the code imports directly are declared, so a new import needs a line in `pyproject.toml`.
