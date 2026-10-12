"""
Which code produced a generated file.

Every results file records the git commit of the working tree that wrote it,
so a number in the manuscript can be traced to the code that computed it. The
commit is the short hash, with `-dirty` appended when tracked files had
uncommitted changes at the time, and `unknown` when git is unavailable. The
R side (stats/R/results.R) writes the same string into the estimates
manifest.

    from preprocessing.provenance import git_commit
    git_commit()   # "9c5d90d" or "9c5d90d-dirty"
"""

from __future__ import annotations

import subprocess

from preprocessing.dataset_paths import PROJECT_ROOT


def git_commit() -> str:
    """The short hash of HEAD, suffixed -dirty when tracked files have uncommitted changes."""
    try:
        head = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=PROJECT_ROOT, capture_output=True, text=True, check=True,
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            cwd=PROJECT_ROOT, capture_output=True, text=True, check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return f"{head}-dirty" if dirty else head
