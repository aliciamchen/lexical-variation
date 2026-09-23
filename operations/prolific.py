"""Read-only access to the Prolific API, shared by operations/payments.py.

The token comes from PROLIFIC_TOKEN in the repository-root .env and is never
printed. Completion codes and pay figures come from the experiment itself
(operations/game_constants.py reads experiment/shared/constants.js), so
regenerating a code or changing the base pay cannot leave the payment tooling
believing something the running study no longer does.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import requests
from dotenv import dotenv_values

from game_constants import ConstantsError
from game_constants import load as load_game_constants

API_ROOT = "https://api.prolific.com/api/v1"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
PAGE_SIZE = 100

try:
    GAME = load_game_constants()
except ConstantsError as error:
    sys.exit(f"Cannot read the experiment's constants: {error}")

PROLIFIC_CODES = GAME["codes"]
FINISHED_CODE = PROLIFIC_CODES["completion"]
LOBBY_TIMEOUT_CODE = PROLIFIC_CODES["lobbyTimeout"]
PARTIAL_CODE = PROLIFIC_CODES["partial"]
BASE_PAY = GAME["base_pay"]
LOBBY_TIMEOUT_PAY = GAME["lobby_timeout_pay"]
CONDITIONS = GAME["conditions"]
PLAYERS_PER_GAME = GAME["players_per_game"]

# Transient failures worth retrying: Prolific rate limiting, and its own 5xx.
RETRY_STATUSES = {429, 500, 502, 503, 504}


def env_value(name):
    """Read one value from the repo-root .env without printing anything else."""
    env_path = PROJECT_ROOT / ".env"
    return (dotenv_values(env_path).get(name) or "").strip() if env_path.exists() else ""


def load_token():
    """Read PROLIFIC_TOKEN from the repo-root .env without printing it."""
    if not (PROJECT_ROOT / ".env").exists():
        sys.exit(f"No .env at {PROJECT_ROOT / '.env'}. Copy .env.example and add PROLIFIC_TOKEN.")
    token = env_value("PROLIFIC_TOKEN")
    if not token:
        sys.exit("PROLIFIC_TOKEN is missing or empty in .env (see .env.example).")
    return token


def request_api(method, path, token, payload=None, params=None, retries=2):
    """One API call, retrying transient failures. Returns (ok, body, error)."""
    delay, attempt = 2, 0
    while True:
        attempt += 1
        try:
            response = requests.request(
                method,
                f"{API_ROOT}{path}",
                headers={"Authorization": f"Token {token}"},
                json=payload,
                params=params,
                timeout=30,
            )
        except requests.RequestException as error:
            reason = f"{type(error).__name__}: {error}"
            if attempt > retries:
                return False, None, reason
        else:
            if response.ok:
                if response.status_code == 204 or not response.content:
                    return True, None, None
                return True, response.json(), None
            # Surface Prolific's own error text; it names the offending field.
            reason = f"{response.status_code}: {response.text[:500]}"
            if response.status_code not in RETRY_STATUSES or attempt > retries:
                return False, None, reason
        print(f"  {method} {path} failed ({reason.split(chr(10))[0][:90]});"
              f" retrying in {delay}s [{attempt}/{retries}]", file=sys.stderr)
        time.sleep(delay)
        delay *= 2


def api(method, path, token, payload=None, params=None, retries=2):
    """Call the Prolific API and return the decoded body (None for 204s); a failure ends the command."""
    ok, body, error = request_api(method, path, token, payload, params, retries)
    if not ok:
        sys.exit(f"{method} {path} failed with {error}")
    return body


def paged(path, token, params=None):
    """Yield every result from a paginated endpoint.

    Submissions report `meta.count` and surveys `meta.total`, and paging stops
    when the offset reaches it. An endpoint that returns a bare list, or a page
    with no `meta` at all, is paged by length instead: a short page is the last
    one, a full page means ask for the next. What is never done is to stop
    quietly on a full page, which once left everyone after the first hundred
    submissions unlisted: a full page under a `meta` that carries neither key
    stops the command, and so does a page identical to the one before it (an
    endpoint ignoring `offset`).
    """
    offset = 0
    previous_ids = None
    while True:
        page = api("GET", path, token, params={**(params or {}), "offset": offset, "limit": PAGE_SIZE})
        if isinstance(page, dict):
            results, meta = page.get("results") or [], page.get("meta")
        else:
            results, meta = page or [], None
        yield from results
        offset += PAGE_SIZE
        if len(results) < PAGE_SIZE:
            return
        if isinstance(meta, dict):
            total = meta.get("total", meta.get("count"))
            if total is None:
                sys.exit(
                    f"GET {path} returned a full page of {PAGE_SIZE} results with a `meta` that "
                    "has neither `total` nor `count`, so it cannot be known whether more exist.\n"
                    "Prolific's pagination has changed shape; fix paged() in operations/prolific.py "
                    "before trusting this listing."
                )
            if offset >= total:
                return
        ids = [r.get("id") or r.get("_id") for r in results if isinstance(r, dict)]
        if ids and ids == previous_ids:
            sys.exit(
                f"GET {path} returned the same page twice at offset {offset - PAGE_SIZE} and "
                f"{offset}, so it is ignoring `offset`. Fix paged() in operations/prolific.py "
                "before trusting this listing."
            )
        previous_ids = ids


def norm_status(status):
    """One spelling for a submission status: "awaiting_review" -> "AWAITING REVIEW"."""
    return (status or "").strip().replace("_", " ").upper()


def submission_code(submission):
    """The completion code on a submission, without the stray trailing period some carry."""
    return (submission.get("study_code") or "").strip().rstrip(".")
