"""
Game constants read from the Empirica source, so the operations tooling cannot
drift from the running experiment.

`operations/session.py` needs a handful of values that the experiment already
defines: the three Prolific completion codes, the pay figures, the condition
names, and the exit reasons the server records when it removes a player. Those
used to be copied into Python by hand, which meant a reworded exit reason or a
regenerated completion code would change the experiment without changing the
tooling that pays people. This module parses them out of the JavaScript instead
and fails loudly when something it expects is missing.

The parsing is deliberately narrow: it understands the few literal declarations
it needs and nothing else, so an unexpected shape raises rather than guessing.
Line comments are stripped before matching, so a `// ... ]` or `// key: value`
remark beside a declaration cannot change what is read.
"""

from __future__ import annotations

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONSTANTS_JS = PROJECT_ROOT / "experiment" / "shared" / "constants.js"


class ConstantsError(RuntimeError):
    """The experiment source did not contain a value the tooling depends on."""


def _source(path: Path) -> str:
    if not path.exists():
        raise ConstantsError(f"No {path}; the operations tooling reads its constants from it.")
    return path.read_text()


# A string literal (double-, single- or backtick-quoted) or a line comment. The
# alternation keeps `//` inside a string ("https://...") from being read as the
# start of a comment.
_STRING_OR_COMMENT = re.compile(
    r'"(?:[^"\\\n]|\\.)*"'
    r"|'(?:[^'\\\n]|\\.)*'"
    r"|`(?:[^`\\]|\\.)*`"
    r"|//[^\n]*"
)


def _without_comments(source: str) -> str:
    """The source with every `//` line comment removed and strings left alone."""
    return _STRING_OR_COMMENT.sub(
        lambda match: "" if match.group(0).startswith("//") else match.group(0), source
    )


def _scalar(source: str, name: str) -> str:
    """The right-hand side of `export const NAME = ...;` as raw text."""
    match = re.search(
        rf"^export const {re.escape(name)}\s*=\s*([^;]+);", _without_comments(source), re.M
    )
    if not match:
        raise ConstantsError(f"Could not find `export const {name}` in {CONSTANTS_JS.name}.")
    return match.group(1).strip()


def _number(source: str, name: str) -> float:
    raw = _scalar(source, name)
    # Require a bare number: anything computed (a ternary on TEST_MODE, say) is
    # not safe to read this way.
    try:
        value = float(raw)
    except ValueError as error:
        raise ConstantsError(
            f"`{name}` in {CONSTANTS_JS.name} is {raw!r}, which is not a plain number. "
            "The operations tooling can only read literal values."
        ) from error
    return value


def _string_list(source: str, name: str) -> list[str]:
    """The elements of `export const NAME = [ "a", "b" ];`."""
    match = re.search(
        rf"^export const {re.escape(name)}\s*=\s*\[(.*?)\]\s*;",
        _without_comments(source),
        re.M | re.S,
    )
    if not match:
        raise ConstantsError(f"Could not find the array `{name}` in {CONSTANTS_JS.name}.")
    values = re.findall(r'"([^"]*)"', match.group(1))
    if not values:
        raise ConstantsError(f"`{name}` in {CONSTANTS_JS.name} has no string entries.")
    return values


def _string_object(source: str, name: str) -> dict[str, str]:
    """The entries of `export const NAME = { key: "value", ... };`."""
    match = re.search(
        rf"^export const {re.escape(name)}\s*=\s*\{{(.*?)\}}\s*;",
        _without_comments(source),
        re.M | re.S,
    )
    if not match:
        raise ConstantsError(f"Could not find the object `{name}` in {CONSTANTS_JS.name}.")
    entries = dict(re.findall(r'(\w+)\s*:\s*"([^"]*)"', match.group(1)))
    if not entries:
        raise ConstantsError(f"`{name}` in {CONSTANTS_JS.name} has no string entries.")
    return entries


def load():
    """Every constant the operations tooling needs, in one call."""
    source = _source(CONSTANTS_JS)
    codes = _string_object(source, "PROLIFIC_CODES")
    for key in ("completion", "lobbyTimeout", "partial"):
        if not codes.get(key):
            raise ConstantsError(
                f"PROLIFIC_CODES in {CONSTANTS_JS.name} has no {key!r} code; "
                "session.py needs all three to tell submissions apart."
            )
    group_size = int(_number(source, "GROUP_SIZE"))
    groups = _string_list(source, "GROUP_NAMES")
    return {
        "codes": codes,
        "players_per_game": group_size * len(groups),
        "base_pay": _number(source, "BASE_PAY"),
        "lobby_timeout_pay": _number(source, "LOBBY_TIMEOUT_PAY"),
        "max_bonus": _number(source, "MAX_BONUS"),
        "conditions": _string_list(source, "conditions"),
    }


def exit_reasons() -> set[str]:
    """Every `exitReason` string the server can record, from EXIT_REASONS in constants.js.

    callbacks.js writes `player.set("exitReason", EXIT_REASONS.<key>)` rather
    than a literal, so the object in shared/constants.js is the one list of
    reasons. `session.py` words each removed participant's message from this
    value, so a reason the tooling has never heard of is worth refusing rather
    than quietly sending the blame-neutral wording to someone whose group left.
    """
    source = _source(CONSTANTS_JS)
    try:
        reasons = _string_object(source, "EXIT_REASONS")
    except ConstantsError as error:
        raise ConstantsError(
            f"{error} session.py cannot word removal messages without EXIT_REASONS."
        ) from error
    return set(reasons.values())
