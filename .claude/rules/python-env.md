# Python Environment

This project uses [uv](https://docs.astral.sh/uv/) for Python dependency management. Dependencies are defined in `pyproject.toml`.

```bash
# Install dependencies
uv sync

# Run a Python script
uv run python script.py

# Run Jupyter
uv run jupyter notebook

# Add a new dependency
uv add package-name

# Add a dev dependency
uv add --dev package-name

# In R: renv::restore()
```

Note: `rpy2` requires R to be installed. Cairo-based packages (`cairosvg`) may require: `brew install cairo pango`
