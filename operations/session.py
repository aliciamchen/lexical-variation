"""
Run a Prolific data-collection session for the synchronous reference game.

The commands, in the order a session uses them:

    setup     create the screening survey and both study drafts
    open      publish the screening survey
    prepare   build the allowlist group from the survey; attach it to the game draft
    close     stop the screening survey, so late responses are neither paid for
              nor left expecting a study they cannot be sent
    message   send the reminder to that group
    publish   publish the game study (optionally at the announced time)
    approve   approve the finishers' submissions
    pay       pay bonuses, partial pay and lobby-timeout pay; send the explanatory notes

    tally                           games per (condition, tangram set) cell; the
                                    emptiest is the next session's treatment
    sessions / surveys / studies    look things up
    blocklist                       seed or repair the group of past players

Pass --session NAME to every step; `setup` saves the ids under that name and
the rest read them back. Every command that changes anything prints its plan
and asks before acting; --yes skips the prompt. The runbook is
operations/procedures.md. PROLIFIC_TOKEN and PROLIFIC_WORKSPACE come from the
repository-root .env and are never printed; `tally` and `sessions` read local
files only and need neither.
"""

import argparse
import copy
import csv
import json
import os
import re
import sys
import tempfile
import time
import uuid
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import requests
from dotenv import dotenv_values

from game_constants import ConstantsError, exit_reasons
from game_constants import load as load_game_constants

API_ROOT = "https://api.prolific.com/api/v1"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
MESSAGES_DIR = Path(__file__).resolve().parent / "messages"
# Per-session ids, so the four of them need not be pasted between commands.
SESSIONS_DIR = Path(__file__).resolve().parent / ".sessions"

# Prolific's paginated payloads echo an internal hostname in links.next
# ("http://survey-api/..."), so pagination walks offset/limit explicitly rather
# than following those URLs.
PAGE_SIZE = 100

# A respondent is eligible only if every screening question was answered "Yes".
# The screening surveys ask three single-select yes/no questions (availability,
# desktop + Chrome, and commitment to the full session).
ELIGIBLE_ANSWER = "Yes"
SCREENING_QUESTIONS = 3


def session_file(name):
    return SESSIONS_DIR / f"{name}.json"


def write_json_atomically(path, data):
    """Write JSON to `path` through a temp file and os.replace.

    The ledger and the session files are what stop a payment being made twice
    and what carry ids between commands; a crash mid-write must leave the
    previous version intact rather than a truncated file.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        "w", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False
    )
    try:
        with handle:
            handle.write(json.dumps(data, indent=2) + "\n")
        os.replace(handle.name, path)
    except BaseException:
        Path(handle.name).unlink(missing_ok=True)
        raise


def saved_sessions():
    """Every saved session as {name: data}, oldest name first."""
    if not SESSIONS_DIR.is_dir():
        return {}
    return {
        path.stem: json.loads(path.read_text()) for path in sorted(SESSIONS_DIR.glob("*.json"))
    }


def read_session(name):
    """Load a session's saved ids, or exit naming the sessions that do exist."""
    path = session_file(name)
    if not path.exists():
        listing = "\n".join(f"  {k}" for k in saved_sessions()) or "  (none yet)"
        sys.exit(f"No session {name!r}. Sessions on this machine:\n{listing}")
    return json.loads(path.read_text())


def write_session(name, **fields):
    """Merge ids into a session file, creating it if needed."""
    path = session_file(name)
    data = json.loads(path.read_text()) if path.exists() else {}
    data.update({k: v for k, v in fields.items() if v is not None})
    write_json_atomically(path, data)
    return path


def from_session(args, field, explicit):
    """Resolve an id from --session when it was not given explicitly."""
    if explicit:
        return explicit
    if not getattr(args, "session", None):
        return None
    value = read_session(args.session).get(field)
    if value:
        print(f"[{args.session}] {field} = {value}")
    return value


def confirm(question, args):
    """Ask before acting, unless --yes. Non-interactive runs must pass --yes."""
    if getattr(args, "yes", False):
        return True
    if not sys.stdin.isatty():
        sys.exit(f"{question.strip()}\nNot a terminal, so nothing was done. Pass --yes to proceed without a prompt.")
    answer = input(f"{question} [y/N] ").strip().lower()
    if answer not in ("y", "yes"):
        print("Nothing done.")
        return False
    return True


def env_value(name):
    """Read one value from the repo-root .env without printing anything else."""
    env_path = PROJECT_ROOT / ".env"
    return (dotenv_values(env_path).get(name) or "").strip() if env_path.exists() else ""


# The standing group of everyone who has played; the game study's completion
# codes add players to it automatically (see with_group_action).
BLOCKLIST_GROUP_NAME = "Played the game"

# Completion codes, pay figures and condition names come from the experiment
# itself (operations/game_constants.py reads experiment/shared/constants.js), so
# regenerating a code or changing the base pay cannot leave the tooling that
# pays people believing something the running study no longer does.
try:
    GAME = load_game_constants()
    SERVER_EXIT_REASONS = exit_reasons()
except ConstantsError as error:
    sys.exit(f"Cannot read the experiment's constants: {error}")

PROLIFIC_CODES = GAME["codes"]
FINISHED_CODE = PROLIFIC_CODES["completion"]
LOBBY_TIMEOUT_CODE = PROLIFIC_CODES["lobbyTimeout"]
PARTIAL_CODE = PROLIFIC_CODES["partial"]
# Someone who only ever timed out in the lobby never saw the task, so that code
# is deliberately absent here and those participants stay eligible for a later
# session.
PLAYED_CODES = {FINISHED_CODE, PARTIAL_CODE}
BASE_PAY = GAME["base_pay"]
LOBBY_TIMEOUT_PAY = GAME["lobby_timeout_pay"]
MAX_BONUS = GAME["max_bonus"]
CONDITIONS = GAME["conditions"]
PLAYERS_PER_GAME = GAME["players_per_game"]

# Prolific's fee on rewards and bonuses, used only for the up-front estimate
# `setup` prints. The real, exact figure comes back from Prolific at the pay
# set-up step, which is why that step exists and charges nothing.
PROLIFIC_FEE_RATE = 0.33

# No single bonus payment can exceed a whole game's pay: the largest partial
# payment is a full base pay plus the bonus cap. `pay --max-each` defaults to it.
MAX_EACH_DEFAULT = BASE_PAY + MAX_BONUS


def cmd_sessions(args, token=None):
    """List the sessions saved on this machine. Needs no token."""
    sessions = saved_sessions()
    if not sessions:
        sys.exit(f"No sessions saved yet in {SESSIONS_DIR}.")
    for name, data in sessions.items():
        print(name)
        for key in ("condition", "tangram_set", "time", "title_time", "budget_usd",
                    "survey_id", "screening_study_id", "game_study_id", "group_id", "run"):
            if data.get(key) is not None:
                print(f"  {key:20s} {data[key]}")
        for approval in data.get("approvals") or []:
            print(f"  {'approved':20s} {approval['count']} {approval['kind']} "
                  f"at ${approval['each_usd']:.2f} "
                  f"(~${approval['estimated_cost_usd']:.2f} with fee)")


def load_token():
    """Read PROLIFIC_TOKEN from the repo-root .env without printing it."""
    if not (PROJECT_ROOT / ".env").exists():
        sys.exit(f"No .env at {PROJECT_ROOT / '.env'}. Copy .env.example and add PROLIFIC_TOKEN.")
    token = env_value("PROLIFIC_TOKEN")
    if not token:
        sys.exit("PROLIFIC_TOKEN is missing or empty in .env (see .env.example).")
    return token


# Transient failures worth retrying: Prolific rate limiting, and its own 5xx.
RETRY_STATUSES = {429, 500, 502, 503, 504}


def request_api(method, path, token, payload=None, params=None, retries=0):
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
            # Without this, a dropped connection is a traceback rather than a
            # message, which is a poor thing to read with a session waiting.
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


def api(method, path, token, payload=None, params=None, retries=0):
    """Call the Prolific API and return the decoded body (None for 204s).

    A failure ends the command. For nearly everything here that is right: a
    half-finished step is worse than a stopped one, and a stray draft is cheap.
    `retries` is for the handful of calls where it is not -- publishing a study
    at an announced minute, where a transient 502 means the people who were told
    to be there at 9pm see nothing at all.
    """
    ok, body, error = request_api(method, path, token, payload, params, retries)
    if not ok:
        sys.exit(f"{method} {path} failed with {error}")
    return body


def paged(path, token, params=None):
    """Yield every result from a paginated endpoint.

    Surveys report `meta.total` and submissions `meta.count`, and paging stops
    when the offset reaches it. An endpoint that returns a bare list, or a page
    with no `meta` at all, is paged by length instead: a short page is the last
    one, a full page means ask for the next. What is never done is to stop
    quietly on a full page: this used to return after the first hundred
    submissions whenever the count was missing, and everyone after them was
    left unpaid without a word. So a full page under a `meta` that carries
    neither key stops the command and names the endpoint, and a page identical
    to the one before it (an endpoint ignoring `offset`) does the same.
    """
    offset = 0
    previous_ids = None
    while True:
        page = api(
            "GET", path, token, params={**(params or {}), "offset": offset, "limit": PAGE_SIZE}
        )
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
                    "Prolific's pagination has changed shape; fix paged() in operations/session.py "
                    "before trusting this listing."
                )
            if offset >= total:
                return
        ids = [r.get("id") or r.get("_id") for r in results if isinstance(r, dict)]
        if ids and ids == previous_ids:
            sys.exit(
                f"GET {path} returned the same page twice at offset {offset - PAGE_SIZE} and "
                f"{offset}, so it is ignoring `offset`. Fix paged() in operations/session.py "
                "before trusting this listing."
            )
        previous_ids = ids


def researcher_id(token):
    return api("GET", "/users/me/", token)["id"]


def workspace_id(token, override=None):
    """Resolve the workspace that new participant groups belong to.

    The account has several workspaces, so this never guesses: with more than
    one it asks for --workspace rather than risk creating the group in the
    wrong place.
    """
    if override:
        return override
    from_env = env_value("PROLIFIC_WORKSPACE")
    if from_env:
        return from_env
    workspaces = list(paged("/workspaces/", token))
    if not workspaces:
        sys.exit("No workspaces found; pass --workspace with a workspace id.")
    if len(workspaces) == 1:
        return workspaces[0]["id"]
    listing = "\n".join(f"  {w['id']}  {w.get('title')}" for w in workspaces)
    sys.exit(
        "Several workspaces exist. Set PROLIFIC_WORKSPACE=<id> in .env (see .env.example),\n"
        f"or pass --workspace <id>:\n{listing}"
    )


def survey_answers(response):
    """Flatten one survey response into [(question_title, [answer values])].

    A list rather than a dict: two questions that happen to share a title must
    stay two questions, because the count is what tells a complete response from
    a partial one.
    """
    answers = []
    sections = response.get("sections") or []
    questions = list(response.get("questions") or [])
    for section in sections:
        questions.extend(section.get("questions") or [])
    for question in questions:
        values = [a.get("value") for a in (question.get("answers") or [])]
        title = question.get("question_title") or question.get("title") or "?"
        answers.append((title, values))
    return answers


def response_time(response):
    """Whatever Prolific calls the response's timestamp, for ordering."""
    for key in ("date_submitted", "submitted_at", "date_created", "created_at"):
        value = response.get(key)
        if value:
            return str(value)
    return ""


def screen_responses(responses, expected_questions):
    """Sort survey responses into eligible, ineligible and malformed.

    Eligibility is "answered 'Yes' to every question", but that has to mean
    every *expected* question. A response that comes back with no questions at
    all -- a partial submission, or a payload shape this code does not
    understand -- has no failing answers, and so would otherwise be counted as
    eligible and invited to a paid session. Anything that does not carry exactly
    the expected number of questions is set aside instead of being guessed at.
    """
    eligible, rejected_by_question, malformed = [], {}, []
    seen, counts = set(), {}
    # Newest response per participant: someone who answered twice meant the
    # second one.
    for response in sorted(responses, key=response_time, reverse=True):
        participant = response.get("participant_id")
        if not participant or participant in seen:
            continue
        seen.add(participant)
        answers = survey_answers(response)
        counts[len(answers)] = counts.get(len(answers), 0) + 1
        if len(answers) != expected_questions:
            malformed.append((participant, len(answers)))
            continue
        failures = [title for title, values in answers if values != [ELIGIBLE_ANSWER]]
        for question in failures:
            rejected_by_question[question] = rejected_by_question.get(question, 0) + 1
        if not failures:
            eligible.append(participant)
    return {
        "eligible": eligible,
        "rejected_by_question": rejected_by_question,
        "malformed": malformed,
        "counts": counts,
        "seen": len(seen),
    }


def survey_response_count(token, survey_id):
    """How many responses one survey has, in a single request."""
    page = api("GET", f"/surveys/{survey_id}/responses/", token, params={"limit": 1})
    return ((page or {}).get("meta") or {}).get("total", 0)


def cmd_surveys(args, token):
    """Watch this session's survey fill, or list surveys to find an id.

    With --session this is one request. Without it, --counts costs a request per
    survey listed, and surveys accumulate at one per session -- which is why the
    listing is capped: the runbook has you running this repeatedly in the minutes
    before a session, and Prolific rate-limits.
    """
    if getattr(args, "session", None) and not args.all:
        survey_id = from_session(args, "survey_id", None)
        if survey_id:
            survey = api("GET", f"/surveys/{survey_id}", token)
            count = survey_response_count(token, survey_id)
            print(f"\n{survey.get('title')}")
            print(f"{count} responses")
            return
        print("That session has no survey id saved; listing surveys instead.\n")

    surveys = list(paged("/surveys/", token, params={"researcher_id": researcher_id(token)}))
    surveys.sort(key=lambda s: s.get("date_created") or "", reverse=True)
    shown = surveys[: args.limit]
    print(f"{len(surveys)} surveys, showing {len(shown)} (--limit to change)\n")
    for survey in shown:
        survey_id = survey["_id"]
        created = (survey.get("date_created") or "")[:16].replace("T", " ")
        title = survey.get("title") or "(untitled)"
        suffix = ""
        if args.counts:
            suffix = f"  [{survey_response_count(token, survey_id)} responses]"
        # Duplicated surveys keep a "Copy" suffix and are usually the empty ones.
        warning = "  <- looks like a duplicate" if title.rstrip().endswith("Copy") else ""
        print(f"{survey_id}  {created}  {title}{suffix}{warning}")


def cmd_studies(args, token):
    """List studies newest first, so you can find the ids the other commands want."""
    studies = newest_first([s for s in paged("/studies/", token)])
    needle = (args.match or "").lower()
    rows = [s for s in studies if needle in (s.get("name") or "").lower()][: args.limit]
    if not rows:
        sys.exit(f"No studies matching {args.match!r}. Try --match '' to list everything.")
    print(f"{len(rows)} studies (newest first)\n")
    print(f"{'id':26s} {'created':11s} {'status':12s} {'places':>6s}  name / internal name")
    for study in rows:
        created = (study.get("date_created") or "")[:10]
        label = study.get("internal_name") or ""
        name = (study.get("name") or "")[:38]
        combined = f"{name}  [{label}]" if label else name
        marker = " <- draft" if study.get("status") == "UNPUBLISHED" else ""
        print(
            f"{study['id']:26s} {created:11s} {study.get('status',''):12s} "
            f"{str(study.get('total_available_places') or ''):>6s}  {combined}{marker}"
        )
    print(f"\nThe game study is named '{GAME_STUDY_NAME}'; the screening one starts")
    print("'Screening survey:'. Survey ids (for `prepare`) come from `surveys --counts`.")


def set_study_allowlist(token, study_id, group_id):
    """Point a draft study's eligibility at a participant group.

    Prolific only allows `filters` to be changed while a study is still
    UNPUBLISHED -- after publishing, only internal_name, places, access_details
    and submissions_config are updatable -- so this refuses anything else. A
    study that already allowlists the group is left alone, whatever its status,
    which is what lets `prepare` be re-run after `publish`.
    """
    study = api("GET", f"/studies/{study_id}/", token)
    existing = study.get("filters") or []
    current = next(
        (f for f in existing if f.get("filter_id") == "participant_group_allowlist"), None
    )
    if current and list(current.get("selected_values") or []) == [group_id]:
        print(f"  already allowlisted: study {study_id} points at group {group_id}")
        return
    status = study.get("status")
    if status != "UNPUBLISHED":
        sys.exit(
            f"Study {study_id} is {status}; Prolific only allows filters to be changed while\n"
            f"a study is UNPUBLISHED. Set the allowlist in the UI, or use a fresh draft."
        )

    dropped = [f for f in existing if (f.get("filter_id") or "").endswith("allowlist")]
    filters = [f for f in existing if not (f.get("filter_id") or "").endswith("allowlist")]
    filters.append({"filter_id": "participant_group_allowlist", "selected_values": [group_id]})

    for f in dropped:
        print(f"  replacing {f['filter_id']} ({len(f.get('selected_values') or [])} values)")
    api("PATCH", f"/studies/{study_id}/", token, payload={"filters": filters})
    print(f"  study {study_id} now allowlists group {group_id}")
    kept = [f["filter_id"] for f in filters]
    print(f"  filters now: {', '.join(kept)}")


def cmd_prepare(args, token):
    """Read a survey's responses and optionally build the allowlist group."""
    args.survey_id = from_session(args, "survey_id", args.survey_id)
    args.study = from_session(args, "game_study_id", args.study)
    if not args.survey_id:
        sys.exit("Give a survey id, or --session NAME to take it from a saved session.")
    survey = api("GET", f"/surveys/{args.survey_id}", token)
    print(f"Survey: {survey.get('title')}\n")

    responses = list(paged(f"/surveys/{args.survey_id}/responses/", token))
    print(f"{len(responses)} responses\n")
    if not responses:
        sys.exit("No responses yet, nothing to do.")

    screened = screen_responses(responses, args.expect_questions)
    eligible = screened["eligible"]

    print(f"Eligible (answered '{ELIGIBLE_ANSWER}' to all "
          f"{args.expect_questions} questions): {len(eligible)}")
    print(f"Excluded: {screened['seen'] - len(eligible)}")
    for question, count in sorted(screened["rejected_by_question"].items(), key=lambda kv: -kv[1]):
        print(f"  {count:3d} did not answer '{ELIGIBLE_ANSWER}' to: {question[:80]}")
    if screened["malformed"]:
        print(f"  {len(screened['malformed']):3d} did not carry "
              f"{args.expect_questions} questions and were set aside:")
        for participant, found in screened["malformed"][:10]:
            print(f"        {participant}  ({found} question(s))")
        if len(screened["malformed"]) > 10:
            print(f"        ... and {len(screened['malformed']) - 10} more")
        modal = max(screened["counts"], key=lambda k: screened["counts"][k])
        if modal != args.expect_questions:
            print(f"\n  WARNING: most responses carry {modal} questions, not "
                  f"{args.expect_questions}. If the survey has changed, re-run with "
                  f"--expect-questions {modal}; otherwise something is wrong with the survey.")
    # At the pilots' ~75% show-up rate, this is the expected turnout.
    expected_turnout = round(len(eligible) * 0.75)
    print(f"\nExpected to show up at 75%: about {expected_turnout}")
    if expected_turnout < PLAYERS_PER_GAME:
        print(f"  WARNING: that is fewer than the {PLAYERS_PER_GAME} players one game needs. "
              "Consider waiting for more responses before building the group.")
    if args.show_ids:
        print("\n" + "\n".join(eligible))

    args.name = args.name or getattr(args, "session", None)
    if not args.name:
        sys.exit("Give --name for the group, or --session so the session name is used.")
    if not eligible:
        sys.exit("No eligible participants, so there is no group to build.")

    # Re-running `prepare` because more responses arrived must top up the group
    # the study already points at, not build a second one beside it: a new group
    # would orphan the first, and anyone in it who is not in the new one would
    # lose their eligibility part-way through the session.
    workspace = workspace_id(token, args.workspace)
    existing = find_group_by_name(token, args.name, workspace)
    if existing:
        verb = f"Add these {len(eligible)} people to the existing group '{args.name}'"
        verb += f" ({existing.get('participant_count')} members already)"
    else:
        verb = f"Create group '{args.name}' with these {len(eligible)} people"
    if args.study:
        verb += f" and allowlist it on study {args.study}"
    if not confirm(f"\n{verb}?", args):
        return

    group = existing or api(
        "POST",
        "/participant-groups/",
        token,
        payload={
            "workspace_id": workspace,
            "name": args.name,
            "description": f"Eligible respondents to survey {args.survey_id}",
        },
    )
    # Members already in the group are ignored by Prolific, so topping up is safe.
    added = api(
        "POST",
        f"/participant-groups/{group['id']}/participants/",
        token,
        payload={"participant_ids": eligible},
    )
    print(f"\n{'Using existing' if existing else 'Created'} group {group['id']} ({args.name})")
    print(f"Submitted {len(eligible)} ids; {len(added.get('results', []))} were newly added")
    if args.session:
        write_session(args.session, group_id=group["id"])
    if args.study:
        set_study_allowlist(token, args.study, group["id"])
    else:
        print("Use this group id as the allowlist filter on the game study,")
        print("or pass --study <game_study_id> next time to have it set for you.")


def cmd_message(args, token):
    """Show the reminder with the session time filled in, then send it to the group."""
    args.group_id = from_session(args, "group_id", args.group_id)
    args.study = from_session(args, "screening_study_id", args.study)
    args.time = args.time or (read_session(args.session).get("time") if args.session else None)
    if not args.group_id:
        sys.exit("Give a group id, or --session NAME once `prepare` has built the group.")
    body_path = Path(args.body_file) if args.body_file else MESSAGES_DIR / "reminder.txt"
    if not body_path.exists():
        sys.exit(f"No message template at {body_path}.")
    template = body_path.read_text()
    if "{time}" in template and not args.time:
        sys.exit(f"{body_path.name} contains {{time}}, so --time is required.")
    body = template.replace("{time}", args.time or "")

    group = api("GET", f"/participant-groups/{args.group_id}/", token)
    print(f"Group: {group.get('name')} ({group.get('participant_count')} participants)")
    print(f"Template: {body_path}")
    print(f"\n--- message ---\n{body}\n--- end ---\n")

    if not confirm(f"Send this to {group.get('participant_count')} people?", args):
        return

    payload = {"participant_group_id": args.group_id, "body": body}
    if args.study:
        payload["study_id"] = args.study
    api("POST", "/messages/participant-group/", token, payload=payload)
    print(f"Sent to {group.get('participant_count')} participants.")


def cmd_publish(args, token):
    """Show a study's status and publish it, optionally at a set clock time."""
    args.study_id = from_session(args, "game_study_id", args.study_id)
    if not args.study_id:
        sys.exit("Give a study id, or --session NAME to take it from a saved session.")
    study = api("GET", f"/studies/{args.study_id}/", token)
    print(f"Study:  {study.get('name')}")
    print(f"Status: {study.get('status')}")
    print(f"Places: {study.get('total_available_places')}")
    print(f"Reward: {study.get('reward')} ({study.get('currency_code')})")

    # A game study draft is created without eligibility filters, since the
    # session's allowlist group does not exist until `prepare` has run. Publishing
    # in that state would open the study to the whole Prolific pool at full
    # reward, so it is refused by default.
    allowlists = [
        f.get("filter_id")
        for f in (study.get("filters") or [])
        if (f.get("filter_id") or "").endswith("allowlist")
    ]
    print(f"Allowlist: {', '.join(allowlists) if allowlists else 'NONE'}")

    if study.get("status") != "UNPUBLISHED":
        sys.exit(f"\nRefusing to publish a study whose status is {study.get('status')}.")
    if not allowlists and not args.allow_open:
        sys.exit(
            "Refusing to publish: this study has no allowlist filter, so it would be open to\n"
            "the whole Prolific pool. Set participant_group_allowlist to the group `prepare`\n"
            "built, or pass --allow-open if an open study is genuinely what you want."
        )
    session_time = read_session(args.session).get("time") if args.session else None
    target, lines = resolve_publish_time(args.at, session_time, args.force_time)
    if lines:
        print()
        for line in lines:
            print(line)

    when = f"at {target:%H:%M %Z}" if target else "now"
    if not confirm(f"\nPublish this game study {when}?", args):
        return

    if target:
        print(f"\nWaiting until {target:%H:%M %Z}. Ctrl-C cancels.")
        while True:
            remaining = (target - datetime.now().astimezone()).total_seconds()
            if remaining <= 0:
                break
            print(f"  {int(remaining) // 60:3d}m {int(remaining) % 60:02d}s to go", end="\r")
            time.sleep(min(15, max(1, remaining)))
        print()

    # The one call in this file worth retrying: it fires after a countdown that
    # cannot be repeated, with the participants already waiting.
    ok, error = transition_study(token, args.study_id, "PUBLISH", retries=4)
    if not ok:
        sys.exit(f"Publishing failed with {error}\nThe study is still unpublished; publish it in "
                 "the Prolific UI now, the participants are waiting.")
    print(f"Published at {datetime.now().astimezone():%H:%M:%S %Z}.")


# What a study's status can be once each transition has gone through, so a
# refused retry can be checked against the study itself.
TRANSITION_OUTCOMES = {
    "PUBLISH": {"ACTIVE", "PUBLISHING", "SCHEDULED", "AWAITING REVIEW", "COMPLETED"},
    "STOP": {"COMPLETED", "AWAITING REVIEW"},
    "PAUSE": {"PAUSED"},
}


def transition_study(token, study_id, action, retries=0):
    """POST a study transition; when it is refused, believe the study over the error.

    A transition is retried through transient failures, and a retry can be
    answered with a 4xx because the attempt before it already went through --
    Prolific refuses to publish a study that is ACTIVE. So a refusal is checked
    against the study's current status before it is reported as a failure.
    Returns (ok, error).
    """
    ok, _, error = request_api(
        "POST", f"/studies/{study_id}/transition/", token,
        payload={"action": action}, retries=retries,
    )
    if ok:
        return True, None
    study = api("GET", f"/studies/{study_id}/", token)
    status = norm_status(study.get("status"))
    if status in TRANSITION_OUTCOMES.get(action, set()):
        print(f"  {action} was refused ({error.split(chr(10))[0][:90]}), but the study is "
              f"already {status}, so an earlier attempt went through.")
        return True, None
    return False, error


# Timezone abbreviations as they appear in the participant-facing session time
# ("6pm PT / 9pm ET"), mapped to IANA zones so an announced time can be turned
# into an actual instant.
TZ_ALIASES = {
    "ET": "America/New_York", "EST": "America/New_York", "EDT": "America/New_York",
    "CT": "America/Chicago", "CST": "America/Chicago", "CDT": "America/Chicago",
    "MT": "America/Denver", "MST": "America/Denver", "MDT": "America/Denver",
    "PT": "America/Los_Angeles", "PST": "America/Los_Angeles", "PDT": "America/Los_Angeles",
}

ANNOUNCED_TIME_RE = re.compile(r"(\d{1,2})(?::(\d{2}))?\s*([ap])\.?m\.?\s*([A-Za-z]{2,3})\b", re.I)


def parse_announced_times(text):
    """Every "9pm ET"-style time in a session's announced time string."""
    found = []
    for match in ANNOUNCED_TIME_RE.finditer(text or ""):
        hour = int(match.group(1)) % 12
        if match.group(3).lower() == "p":
            hour += 12
        zone = TZ_ALIASES.get(match.group(4).upper())
        if zone:
            found.append((hour, int(match.group(2) or 0), zone, match.group(0).strip()))
    return found


def announced_instants(session_time, now=None):
    """The instants a session's announced time refers to, today, in each zone named.

    "6pm PT / 9pm ET" is one instant written twice. Returning both lets the
    caller check they agree -- if they do not, the wording participants were
    given is itself wrong, which is worth knowing before publishing to it.
    """
    now = now or datetime.now().astimezone()
    out = []
    for hour, minute, zone, label in parse_announced_times(session_time):
        local = now.astimezone(ZoneInfo(zone)).replace(
            hour=hour, minute=minute, second=0, microsecond=0
        )
        out.append((local, label, zone))
    return out


def parse_clock(at):
    """--at as (hour, minute, iana_zone_or_None). Accepts "21:00" and "21:00 ET"."""
    match = re.fullmatch(r"(\d{1,2}):(\d{2})(?:[\s,]+(\S+))?", (at or "").strip())
    if not match:
        sys.exit(
            '--at wants a 24-hour clock time, optionally with a timezone:\n'
            '  --at 21:00        (interpreted in the session\'s announced timezone)\n'
            '  --at "21:00 ET"   (explicit)'
        )
    hour, minute = int(match.group(1)), int(match.group(2))
    if not (0 <= hour < 24 and 0 <= minute < 60):
        sys.exit(f"--at {at!r} is not a valid time of day.")
    zone = None
    if match.group(3):
        zone = TZ_ALIASES.get(match.group(3).upper(), match.group(3))
        try:
            ZoneInfo(zone)
        except (ZoneInfoNotFoundError, ValueError):
            sys.exit(
                f"--at names timezone {match.group(3)!r}, which is neither an IANA zone "
                f"nor one of {', '.join(sorted(TZ_ALIASES))}."
            )
    return hour, minute, zone


def resolve_publish_time(at, session_time, force=False, now=None):
    """Work out when to publish, and check it against what participants were told.

    `--at` used to be read as a naive local clock time while every
    participant-facing string is in PT/ET, so running this from a machine that
    is not on Eastern time published hours after the announced minute with
    nothing to catch it. Now the announced time decides the timezone unless one
    is given, and a disagreement between the two stops the command.

    Returns (target_or_None, [lines to show]).
    """
    now = now or datetime.now().astimezone()
    announced = announced_instants(session_time, now=now)
    lines = []

    if announced:
        instants = {a[0].astimezone(ZoneInfo("UTC")) for a in announced}
        labels = " / ".join(a[1] for a in announced)
        if len(instants) > 1:
            lines.append(
                f"WARNING: the announced time {session_time!r} names instants that disagree "
                f"({labels}). Fix the session time, or pass --at with an explicit timezone."
            )
            announced = []
        else:
            lines.append(f"Announced to participants: {labels}")

    if not at:
        if announced:
            target = announced[0][0]
            if target > now:
                minutes = round((target - now).total_seconds() / 60)
                lines.append(
                    f"No --at given, so this publishes NOW -- {minutes} min before the "
                    f"announced {announced[0][1]}. Pass --at to wait for it."
                )
        return None, lines

    def at_clock(tzinfo):
        return now.astimezone(tzinfo).replace(hour=hour, minute=minute, second=0, microsecond=0)

    hour, minute, zone = parse_clock(at)
    if zone is not None:
        target = at_clock(ZoneInfo(zone))
    elif announced:
        # "6pm PT / 9pm ET" is one instant named twice, so --at 18:00 and
        # --at 21:00 are both right -- they just pick different halves of the
        # wording. Accept whichever announced zone makes --at land on the
        # announced instant, and only complain when none of them does.
        wanted = announced[0][0]
        matches = [(at_clock(ZoneInfo(z)), z) for _, _, z in announced]
        agreeing = [(t, z) for t, z in matches if t == wanted]
        if agreeing:
            target, zone = agreeing[0]
            lines.append(f"--at {at} read in {zone}, which matches the announced time.")
        else:
            target, zone = matches[0]
            lines.append(f"--at {at} read in {zone} (the first zone in the announced time).")
    else:
        target = at_clock(now.tzinfo)
        lines.append(
            f"--at {at} read in this machine's local timezone -- the session has no announced "
            "time to take one from. Pass an explicit zone if that is not what you meant."
        )

    if announced and target != announced[0][0]:
        drift = (target - announced[0][0]).total_seconds() / 60
        message = (
            f"--at resolves to {target:%H:%M %Z}, but participants were told "
            f"{announced[0][1]} ({announced[0][0]:%H:%M %Z}) -- a gap of {drift:+.0f} minutes."
        )
        if not force:
            sys.exit(
                f"{message}\nNothing published. Fix --at, or pass --force-time if the gap "
                "is deliberate."
            )
        lines.append(f"WARNING: {message} (--force-time given)")

    if target <= now:
        sys.exit(f"{target:%H:%M %Z} is already past (it is {now:%H:%M %Z}). Nothing published.")
    lines.append(f"Publishing at {target:%H:%M:%S %Z} ({round((target - now).total_seconds() / 60)} min away).")
    return target, lines


def run_dir(timestamp):
    path = PROJECT_ROOT / "data" / "runs" / timestamp
    if not path.is_dir():
        sys.exit(f"No run directory at {path}. Run analysis/extract_run.py first.")
    return path


def read_payment_csv(path, amount_column):
    """Read a bonuses/early-ended CSV into [{id, amount, exit_reason}] rows.

    Rows with a non-positive amount are dropped: a $0.00 partial pay is a row
    Prolific would reject, not a payment worth making. `exit_reason` is empty
    for bonuses.csv and for early_ended.csv written before that column existed.
    """
    rows, skipped = [], 0
    with open(path, newline="") as handle:
        for row in csv.DictReader(handle):
            participant = (row.get("prolific_id") or "").strip()
            try:
                amount = round(float(row.get(amount_column) or 0), 2)
            except ValueError:
                sys.exit(f"{path.name}: could not read {amount_column} for one row.")
            if not participant:
                continue
            if amount <= 0:
                skipped += 1
                continue
            rows.append(
                {
                    "id": participant,
                    "amount": amount,
                    "exit_reason": (row.get("exit_reason") or "").strip(),
                }
            )
    return rows, skipped


# Fields copied verbatim from the template study when creating a new one. Kept as
# an explicit list so a new field Prolific adds to the study object does not get
# forwarded into a create call by accident.
STUDY_TEMPLATE_FIELDS = [
    "name",
    "description",
    "external_study_url",
    "prolific_id_option",
    "reward",
    "estimated_completion_time",
    "maximum_allowed_time",
    "device_compatibility",
    "peripheral_requirements",
    "completion_codes",
    "project",
]

# The game study's name on Prolific; `setup` copies the newest study with this
# name and `blocklist --from-prolific` reads every study with it.
GAME_STUDY_NAME = "Group communication game"
SCREENING_TITLE = f"Screening survey: {GAME_STUDY_NAME} [starts {{time}}]"

# What each completion code must, and must not, do on Prolific. The finished
# code is reviewed by `approve` against the game data, so it must not approve
# itself; removals and lobby timeouts are paid by bonus and asked to return, or
# Prolific approves them and pays the full base reward too; and everyone who saw
# the task joins the blocklist group (see with_group_action).
REQUIRED_CODE_ACTIONS = {
    "completion": {"ADD_TO_PARTICIPANT_GROUP"},
    "partial": {"REQUEST_RETURN", "ADD_TO_PARTICIPANT_GROUP"},
    "lobbyTimeout": {"REQUEST_RETURN"},
}
FORBIDDEN_CODE_ACTIONS = {"completion": {"AUTOMATICALLY_APPROVE"}}
CODE_ACTION_REASONS = {
    "REQUEST_RETURN": "these participants are paid by bonus and must be asked to return, or "
                      "Prolific approves the submission and pays the full base reward as well",
    "ADD_TO_PARTICIPANT_GROUP": "players who saw the task would not join the blocklist group",
    "AUTOMATICALLY_APPROVE": "finishers must be approved by `approve`, after the cross-check "
                             "against the game data",
}


def check_game_template(game_payload, allow_mismatch):
    """Refuse a game study whose pay, codes or code actions have drifted from the experiment.

    `setup` copies the newest matching study, which is the previous session's,
    which copied the one before it. Nothing else checks that chain, so a one-off
    change -- a make-up session at a different reward, a regenerated code --
    propagates to every session after it. These values are the ones that would
    do real damage: the reward is what the app promises participants and what
    partial pay is prorated from, the codes are how anyone is identified as
    having finished at all, and the actions on them are what asks removed
    players to return and adds every player to the blocklist.
    """
    problems = []
    reward, expected_reward = game_payload.get("reward"), round(BASE_PAY * 100)
    if reward != expected_reward:
        problems.append(
            f"reward is {reward} cents, but the experiment promises ${BASE_PAY:.2f} "
            f"({expected_reward} cents) on the consent page, in the instructions and on the "
            "exit screen, and prorates every removed player's partial pay from it."
        )
    codes = {(c.get("code") or "").strip() for c in (game_payload.get("completion_codes") or [])}
    expected_codes = set(PROLIFIC_CODES.values())
    if codes != expected_codes:
        detail = []
        if expected_codes - codes:
            detail.append(f"missing {', '.join(sorted(expected_codes - codes))}")
        if codes - expected_codes:
            detail.append(f"unexpected {', '.join(sorted(codes - expected_codes))}")
        problems.append(
            f"completion codes do not match shared/constants.js ({'; '.join(detail)}). "
            "Participants are shown the codes the experiment defines, so a study carrying "
            "different ones cannot tell finishers from removals."
        )
    actions_by_code = {
        (c.get("code") or "").strip(): {a.get("action") for a in (c.get("actions") or [])}
        for c in (game_payload.get("completion_codes") or [])
    }
    for key, required in REQUIRED_CODE_ACTIONS.items():
        code = PROLIFIC_CODES[key]
        have = actions_by_code.get(code)
        if have is None:
            continue  # already reported as a missing code
        for action in sorted(required - have):
            problems.append(f"code {code} ({key}) lacks {action}: {CODE_ACTION_REASONS[action]}.")
        for action in sorted(have & FORBIDDEN_CODE_ACTIONS.get(key, set())):
            problems.append(f"code {code} ({key}) carries {action}: {CODE_ACTION_REASONS[action]}.")
    if not problems:
        return
    listing = "\n".join(f"  - {problem}" for problem in problems)
    if allow_mismatch:
        print(f"\nWARNING: template drift accepted with --allow-template-mismatch:\n{listing}")
        return
    sys.exit(
        f"\nThe template game study has drifted from the experiment:\n{listing}\n\n"
        "Nothing was created. Fix the template study in Prolific, pin a good one with "
        "--template-study or PROLIFIC_TEMPLATE_STUDY in .env, or pass "
        "--allow-template-mismatch if the difference is deliberate."
    )


def print_cost_estimate(screening_reward_cents, survey_places, game_reward_cents, places):
    """What this session could cost, before anything is created.

    A ceiling rather than a forecast: the screening survey is charged per
    response up to its ceiling, and bonuses are uncapped in the code but hold
    near MAX_BONUS in practice. Prolific's exact fee comes back at the pay
    set-up step, which is why that step charges nothing.
    """
    screening = survey_places * screening_reward_cents / 100
    base = places * game_reward_cents / 100
    bonus = places * MAX_BONUS
    fee = (screening + base + bonus) * PROLIFIC_FEE_RATE
    def row(label, detail, amount, note=""):
        print(f"  {label:11s}{detail:26s}${amount:8.2f}{note}")

    total = round(screening + base + bonus + fee, 2)
    print("\nCost ceiling for this session (Prolific's fee is approximate):")
    row("screening", f"{survey_places} responses x ${screening_reward_cents / 100:.2f}", screening)
    row("base pay", f"{places} places x ${game_reward_cents / 100:.2f}", base)
    row("bonuses", f"{places} players x ${MAX_BONUS:.2f}", bonus, "   at the cap")
    row("fee", f"~{PROLIFIC_FEE_RATE:.0%} of the above", fee)
    print(f"  {'-' * 45}")
    row("total", "", total)
    print("  Only responses actually collected and players actually placed are charged;")
    print("  `close` after `prepare` stops the screening half of this from running on.")
    return total


def newest_first(items):
    return sorted(items, key=lambda d: d.get("date_created") or "", reverse=True)


def pick_template_survey(token, override):
    """The survey whose questions a new screening survey is copied from."""
    surveys = newest_first(
        list(paged("/surveys/", token, params={"researcher_id": researcher_id(token)}))
    )
    if override:
        match = next((s for s in surveys if s["_id"] == override), None)
        if not match:
            sys.exit(f"No survey {override} for this researcher.")
        return match
    # Duplicates keep a "Copy" suffix and are usually the empty ones.
    for survey in surveys:
        title = (survey.get("title") or "").rstrip()
        if title.startswith("Screening survey") and not title.endswith("Copy"):
            return survey
    sys.exit("No screening survey to copy. Pass --template-survey.")


def pick_template_study(token, name, override):
    """The game study whose settings a new draft is copied from."""
    studies = newest_first([s for s in paged("/studies/", token)])
    if override:
        match = next((s for s in studies if s["id"] == override), None)
        if not match:
            sys.exit(f"No study {override}.")
        return api("GET", f"/studies/{match['id']}/", token)
    for study in studies:
        if (study.get("name") or "").strip() == name:
            return api("GET", f"/studies/{study['id']}/", token)
    sys.exit(f"No study named '{name}' to copy. Pass --template-study.")


def find_survey_study(token, survey_id):
    """The study that delivers a given survey, used as the screening template."""
    for study in newest_first([s for s in paged("/studies/", token)]):
        detail = None
        if survey_id in (study.get("external_study_url") or ""):
            detail = api("GET", f"/studies/{study['id']}/", token)
        if detail:
            return detail
    return None


AVAILABILITY_RE = re.compile(r"available at (.*?) to participate", re.I)
# Any "9pm"/"6:30 PM" left in a participant-facing string after retiming.
CLOCK_RE = re.compile(r"\d{1,2}(?::\d{2})?\s*[ap]\.?m\.?", re.I)


def retime_sections(sections, time_text):
    """Copy a survey's sections, substituting the session time and fresh ids.

    Returns (sections, changed_titles, old_time). `old_time` used to be stashed
    on a function attribute and read back by the caller, which meant a template
    whose wording had drifted could leave the caller holding a stale value -- or
    none -- and silently ship the previous session's start time to participants
    in the study descriptions. It is a return value now, and the one regex that
    finds it is the same one that does the substitution.
    """
    sections = copy.deepcopy(sections)
    changed, old_time = [], None
    for section in sections:
        section["id"] = str(uuid.uuid4())
        for question in section.get("questions") or []:
            question["id"] = str(uuid.uuid4())
            for answer in question.get("answers") or []:
                answer["id"] = str(uuid.uuid4())
            title = question.get("title") or ""
            # Only the availability question names a time.
            found = AVAILABILITY_RE.search(title)
            if not found:
                continue
            old_time = found.group(1).strip()
            new_title = AVAILABILITY_RE.sub(
                f"available at {time_text} to participate", title
            )
            if new_title != title:
                question["title"] = new_title
                changed.append(new_title)
    if not changed:
        sys.exit(
            "Could not find an availability question to retime in the template survey.\n"
            "Check the template, or edit the new survey's time by hand after creating it."
        )
    return sections, changed, old_time


def leftover_times(text, new_time):
    """Clock times in a participant-facing string that the retiming did not set.

    The descriptions are copied from the previous session, so a mention the
    substitution missed is the previous session's start time being told to this
    session's participants.
    """
    allowed = {m.group(0).lower().replace(".", "").replace(" ", "")
               for m in CLOCK_RE.finditer(new_time or "")}
    stale = []
    for match in CLOCK_RE.finditer(text or ""):
        token = match.group(0).lower().replace(".", "").replace(" ", "")
        if token not in allowed:
            stale.append(match.group(0))
    return stale


def with_group_action(completion_codes, group_id):
    """Make the game study add its own players to the blocklist group.

    Attaching `ADD_TO_PARTICIPANT_GROUP` to the codes that mean "saw the task"
    means Prolific maintains the blocklist itself: each player joins the group
    the moment they submit, so no post-session command is needed. The
    lobby-timeout code is deliberately left alone, so participants who never
    reached a game stay eligible for a later session.
    """
    codes = copy.deepcopy(completion_codes or [])
    for code in codes:
        if code.get("code") not in PLAYED_CODES:
            continue
        actions = code.setdefault("actions", [])
        already = [
            a for a in actions
            if a.get("action") == "ADD_TO_PARTICIPANT_GROUP"
        ]
        for action in already:
            action["participant_group"] = group_id
        if not already:
            actions.append(
                {"action": "ADD_TO_PARTICIPANT_GROUP", "participant_group": group_id}
            )
    return codes


def retime_text(text, old_time, new_time):
    """Replace the template session's time wherever it appears in participant-facing text.

    The screening study's description names the start time twice; copying it
    verbatim would tell participants the previous session's time.
    """
    if not text or not old_time or old_time == new_time:
        return text, 0
    count = text.count(old_time)
    return text.replace(old_time, new_time), count


def cmd_setup(args, token):
    """Create the screening survey, its study, and the game study draft."""
    # The design wants the eight (condition, tangram set) cells filled evenly,
    # so the tally comes first: it says whether this session's treatment is
    # the one to run before anything is created.
    tally = print_tally()
    chosen = (args.condition, tangram_set_label(args.set))
    if tally:
        counts, emptiest = tally
        so_far = counts.get(chosen, {}).get("games", 0)
        verdict = ("the emptiest cell" if chosen == emptiest else
                   f"NOTE: the emptiest cell is {emptiest[0]} set {emptiest[1]} "
                   f"({counts[emptiest]['games']} games)")
        print(f"This session: {chosen[0]} set {chosen[1]} ({so_far} complete games so far) -- {verdict}.\n")
    else:
        print(f"This session: {chosen[0]} set {chosen[1]}.\n")

    # Pinning a template in .env stops the copy-the-newest chain drifting.
    args.template_survey = args.template_survey or env_value("PROLIFIC_TEMPLATE_SURVEY") or None
    args.template_study = args.template_study or env_value("PROLIFIC_TEMPLATE_STUDY") or None
    if args.rehearsal:
        # A rehearsal is invisible to real participants by construction: both
        # studies are allowlisted to the one test participant and hold one place.
        args.places = 1
        args.survey_places = 1
        args.internal_name = args.internal_name or f"REHEARSAL {datetime.now():%Y-%m-%d %H:%M}"
        print(f"REHEARSAL: both studies will be visible only to participant {args.rehearsal}, 1 place each.\n")
    template_survey = pick_template_survey(token, args.template_survey)
    detail = api("GET", f"/surveys/{template_survey['_id']}", token)
    sections, retimed, old_time = retime_sections(detail.get("sections") or [], args.time)
    title = SCREENING_TITLE.format(time=args.title_time or args.time)

    screening_template = find_survey_study(token, template_survey["_id"])
    game_template = pick_template_study(token, args.study_name, args.template_study)

    # Participant-facing descriptions are copied from the templates, so any
    # mention of the previous session's time has to be swapped for the new one.
    screening_description, n_screen = retime_text(
        (screening_template or {}).get("description"), old_time, args.time)
    game_description, n_game = retime_text(game_template.get("description"), old_time, args.time)
    if screening_template is not None:
        screening_template = {**screening_template, "description": screening_description}
    game_template = {**game_template, "description": game_description}
    print(f"Retimed descriptions: {n_screen} mention(s) in the screening study, {n_game} in the game study"
          + (f" ('{old_time}' -> '{args.time}')" if old_time else ""))
    if not old_time:
        sys.exit(
            "Could not read the template survey's existing session time, so the study\n"
            "descriptions cannot be retimed -- they would tell participants the previous\n"
            "session's start time. Check the availability question's wording in the template."
        )
    stale = leftover_times(screening_description, args.time) + leftover_times(game_description, args.time)
    if stale:
        print(f"\nWARNING: after retiming, the descriptions still mention "
              f"{', '.join(sorted(set(stale)))}, which is not part of '{args.time}'.")
        print("Check both descriptions in the Prolific UI before opening the survey.")

    print(f"Template survey:  {template_survey.get('title')}  ({template_survey['_id']})")
    print(f"Template study:   {game_template.get('internal_name') or game_template.get('name')}"
          f"  ({game_template['id']})")
    print(f"\nNew survey title: {title}")
    print("Retimed question:")
    for question in retimed:
        print(f"  {question}")

    if not args.blocklist_group:
        found = find_group_by_name(token, BLOCKLIST_GROUP_NAME, workspace_id(token, args.workspace))
        if found:
            args.blocklist_group = found["id"]
            print(f"Blocklist group: '{BLOCKLIST_GROUP_NAME}' ({found.get('participant_count')} members, {found['id']})")
        else:
            print(f"Blocklist group: none -- no group named '{BLOCKLIST_GROUP_NAME}'. Run `blocklist` first.")

    game_payload = {field: game_template.get(field) for field in STUDY_TEMPLATE_FIELDS}
    if args.blocklist_group:
        game_payload["completion_codes"] = with_group_action(
            game_payload.get("completion_codes"), args.blocklist_group
        )
    game_payload["internal_name"] = args.internal_name or (
        f"{args.condition} set {args.set} {datetime.now():%Y-%m-%d}"
    )
    game_payload["total_available_places"] = args.places
    if args.rehearsal:
        game_payload["filters"] = [{"filter_id": "custom_allowlist", "selected_values": [args.rehearsal]}]
    print(f"\nGame study draft: {game_payload['internal_name']}")
    for field in ("reward", "estimated_completion_time", "device_compatibility",
                  "prolific_id_option", "total_available_places"):
        print(f"  {field:26s} {game_payload.get(field)!r}")
    for code in game_payload.get("completion_codes") or []:
        actions = ", ".join(a.get("action", "?") for a in (code.get("actions") or [])) or "none"
        print(f"  code {code.get('code'):12s} {actions}")
    if not args.blocklist_group:
        print("  (no --blocklist-group, so players will NOT be auto-added to the blocklist)")

    if screening_template:
        filters = [
            f for f in (screening_template.get("filters") or [])
            if f.get("filter_id") != "previous_studies_blocklist"
        ]
        if args.blocklist_group:
            filters.append(
                {
                    "filter_id": "participant_group_blocklist",
                    "selected_values": [args.blocklist_group],
                }
            )
        if args.rehearsal:
            filters.append({"filter_id": "custom_allowlist", "selected_values": [args.rehearsal]})
        print("\nScreening study filters:")
        for f in filters:
            print(f"  {f['filter_id']:32s} {f.get('selected_values')}")
        if not args.blocklist_group:
            print("  (no --blocklist-group given, so nobody is blocked -- past players could sign up)")
    else:
        filters = []
        print("\nCould not find the template survey's study; screening filters must be set by hand.")

    # Checked before anything is created: the survey is created first, so a later
    # failure would otherwise leave an orphaned survey behind.
    privacy_notice = (screening_template or {}).get("privacy_notice")
    print(f"\nPrivacy notice: {'present' if privacy_notice else 'MISSING'}")
    if not privacy_notice:
        sys.exit(
            "Prolific rejects a survey-backed study without a privacy notice\n"
            '("A survey must have a privacy notice."). Copy one from a previous\n'
            "screening study, or pass --template-survey for a survey whose study has one."
        )

    check_game_template(game_payload, args.allow_template_mismatch)
    ceiling = print_cost_estimate(
        (screening_template or {}).get("reward", 30) or 30,
        args.survey_places,
        game_payload.get("reward") or 0,
        args.places,
    )
    budget = args.budget if args.budget is not None else ceiling
    print(f"  Session budget: ${budget:,.2f}"
          + (" (--budget)" if args.budget is not None else " (the ceiling; --budget to change)")
          + "; `pay` refuses to take the session past it.")

    if not confirm("\nCreate the survey and both study drafts? Nothing is published.", args):
        return

    # The session file is written after each created object, so a failure
    # between creations leaves the ids made so far on disk rather than only on
    # the screen.
    name = args.session or f"{args.condition}-set{args.set}-{datetime.now():%Y%m%d-%H%M}"
    write_session(
        name,
        condition=args.condition,
        tangram_set=args.set,
        # Both forms, and deliberately not one. `--title-time` is the short
        # spelling that fits a study title ("9pm ET"); `--time` is the full
        # announcement ("6pm PT / 9pm ET"). Storing only the short one made
        # every later reader see one timezone: `publish --at 18:00` was
        # refused as a three-hour drift from "9pm ET" although 18:00 PT is
        # exactly the announced instant, and the reminder told PT
        # participants a time they had to convert themselves.
        time=args.time,
        title_time=args.title_time,
        budget_usd=budget,
    )
    survey = api(
        "POST",
        "/surveys/",
        token,
        payload={"researcher_id": researcher_id(token), "title": title, "sections": sections},
    )
    print(f"\nCreated survey {survey['_id']}")
    write_session(name, survey_id=survey["_id"])

    screening_payload = {
        "name": title,
        "description": (screening_template or {}).get("description") or title,
        "external_study_url": f"https://prolific.com/surveys/{survey['_id']}",
        "reward": (screening_template or {}).get("reward", 30),
        "estimated_completion_time": (screening_template or {}).get("estimated_completion_time", 1),
        "total_available_places": args.survey_places,
        "device_compatibility": ["desktop"],
        "filters": filters,
        "completion_codes": (screening_template or {}).get("completion_codes") or [],
        "project": game_template.get("project"),
        # Prolific rejects a survey-backed study without one:
        # "A survey must have a privacy notice."
        "privacy_notice": privacy_notice,
    }
    screening = api("POST", "/studies/", token, payload=screening_payload)
    print(f"Created screening study {screening['id']} ({screening.get('status')})")
    write_session(name, screening_study_id=screening["id"])

    game = api("POST", "/studies/", token, payload=game_payload)
    print(f"Created game study draft {game['id']} ({game.get('status')})")
    print("\nNeither is published. Next: `session.py open --session <name>` when you are ready for responses.")
    print("\n--- ids for the rest of this session (keep these) ---")
    print(f"  SURVEY_ID={survey['_id']}          # prepare")
    print(f"  SCREENING_STUDY_ID={screening['id']}  # message --study")
    print(f"  GAME_STUDY_ID={game['id']}       # prepare, publish, approve, pay")
    print("`session.py sessions` shows them again; you should not need them with --session.")

    path = write_session(name, game_study_id=game["id"])
    print(f"\nSaved to {path}. From here on you can use --session {name}")


def played_participant_ids():
    """Every participant who was actually placed in a game, across all runs.

    bonuses.csv and early_ended.csv are written only for players with a real
    gameID (see analysis/extract_run.py), so together they are exactly the set
    of people who saw the task. Participants who timed out in the lobby never
    reach either file and so stay eligible for later sessions. Amounts are
    ignored here -- a $0.00 partial pay still means they played.
    """
    runs_dir = PROJECT_ROOT / "data" / "runs"
    if not runs_dir.is_dir():
        sys.exit(f"No {runs_dir}. Run analysis/extract_run.py first.")
    found, per_run = {}, []
    for run_path in sorted(p for p in runs_dir.iterdir() if p.is_dir()):
        run_ids = set()
        for filename in ("bonuses.csv", "early_ended.csv"):
            path = run_path / filename
            if not path.exists():
                continue
            with open(path, newline="") as handle:
                for row in csv.DictReader(handle):
                    participant = (row.get("prolific_id") or "").strip()
                    if participant:
                        run_ids.add(participant)
        if run_ids:
            per_run.append((run_path.name, len(run_ids)))
            for participant in run_ids:
                found.setdefault(participant, run_path.name)
    return found, per_run


def played_from_prolific(token, study_name, include_unknown):
    """Derive who played from Prolific submissions, for runs not extracted locally."""
    studies = [
        s
        for s in paged("/studies/", token)
        if (s.get("name") or "").strip() == study_name
    ]
    if not studies:
        sys.exit(f"No studies named '{study_name}' found.")
    played, buckets = {}, {"played": 0, "lobby timeout": 0, "no code": 0}
    for study in studies:
        for submission in paged(f"/studies/{study['id']}/submissions/", token):
            participant = submission.get("participant_id")
            code = (submission.get("study_code") or "").strip().rstrip(".")
            if not participant:
                continue
            if code in PLAYED_CODES:
                buckets["played"] += 1
                played.setdefault(participant, study["id"])
            elif code == LOBBY_TIMEOUT_CODE:
                buckets["lobby timeout"] += 1
            else:
                buckets["no code"] += 1
                if include_unknown:
                    played.setdefault(participant, study["id"])
    print(f"{len(studies)} studies named '{study_name}':")
    for label, count in buckets.items():
        note = ""
        if label == "lobby timeout":
            note = "  (stay eligible)"
        elif label == "no code":
            note = "  (blocked)" if include_unknown else "  (stay eligible; --include-unknown to block)"
        print(f"  {count:4d} {label}{note}")
    return played


def find_group_by_name(token, name, workspace):
    """Find a live group by name.

    Deleted groups keep their name and membership in the listing with
    `is_deleted: true`, so they have to be skipped or a new group would silently
    reuse a deleted one.
    """
    for group in paged("/participant-groups/", token, params={"workspace_id": workspace}):
        if (group.get("name") or "") == name and not group.get("is_deleted"):
            return group
    return None


def cmd_blocklist(args, token):
    """Keep a participant group of everyone who has played, for blocklisting."""
    if args.from_prolific:
        played = played_from_prolific(token, args.study_name, args.include_unknown)
    else:
        played, per_run = played_participant_ids()
        if not played:
            sys.exit("No bonuses.csv or early_ended.csv found under data/runs/.")
        print(f"{len(played)} distinct participants have played, across {len(per_run)} runs:")
        for run_name, count in per_run:
            print(f"  {run_name}  {count}")
        print("Only extracted runs count here; use --from-prolific to include every session.")
    print(f"\n{len(played)} distinct participants to block.")

    workspace = workspace_id(token, args.workspace)
    group = find_group_by_name(token, args.name, workspace)
    if group:
        print(f"\nGroup '{args.name}' exists ({group.get('participant_count')} members).")
    else:
        print(f"\nGroup '{args.name}' does not exist yet and would be created.")

    if not confirm("\nCreate or update the group with these participants?", args):
        return

    if not group:
        group = api(
            "POST",
            "/participant-groups/",
            token,
            payload={
                "workspace_id": workspace,
                "name": args.name,
                "description": "Participants who have played a game; blocklist for new screening surveys",
            },
        )
        print(f"Created group {group['id']}")
    # Members already in the group are ignored by Prolific, so this is safe to
    # re-run after every session.
    added = api(
        "POST",
        f"/participant-groups/{group['id']}/participants/",
        token,
        payload={"participant_ids": sorted(played)},
    )
    print(f"Submitted {len(played)} ids; {len(added.get('results', []))} were newly added.")
    print(f"\nGroup id: {group['id']}")
    print("Set this as participant_group_blocklist on the screening survey, and remove")
    print("previous_studies_blocklist -- that one also blocks lobby timeouts.")


def ledger_path(run_path):
    return run_path / "prolific_payments.json"


def read_ledger(run_path):
    path = ledger_path(run_path)
    return json.loads(path.read_text()) if path.exists() else {}


def write_ledger(run_path, ledger):
    write_json_atomically(ledger_path(run_path), ledger)


# Ledger keys that record the explanatory notes rather than a bulk payment.
NOTE_LEDGER_KEYS = {"notes_sent", "notes_sent_at"}


def ledger_entries(ledger):
    """The bulk-payment entries of a ledger, skipping the note bookkeeping keys."""
    return {
        population: entry
        for population, entry in ledger.items()
        if isinstance(entry, dict) and population not in NOTE_LEDGER_KEYS
    }


def already_paid_elsewhere(current_run):
    """Everyone another run's ledger records as paid, as {participant: run name}.

    A safety net under the batch scoping in extract_run.py. Exports are
    cumulative, so a bonus file built without a batch filter -- an older one, or
    one made with --all-batches -- can contain people an earlier session already
    paid. The ledger is per run directory and so cannot see that on its own.
    """
    paid = {}
    runs_root = PROJECT_ROOT / "data" / "runs"
    if not runs_root.is_dir():
        return paid
    for other in sorted(x for x in runs_root.iterdir() if x.is_dir()):
        if other.name == current_run:
            continue
        for population, entry in ledger_entries(read_ledger(other)).items():
            if not entry.get("paid_at"):
                continue
            for participant in entry.get("participants_paid") or []:
                paid.setdefault(participant, f"{other.name}/{population}")
    return paid



# ============ wording for removed participants ============

# Of the reasons the server records (EXIT_REASONS in shared/constants.js), these
# are not the participant's doing -- other players left, too few groups
# remained, or the researcher stopped the batch -- so those participants can be
# told plainly that nothing went wrong on their end. Checked against
# constants.js at startup by check_exit_reasons().
OTHERS_LEFT_REASONS = {
    "group disbanded",
    "insufficient groups",
    "insufficient groups after accuracy check",
}

# The researcher stopped the batch (Empirica's "game terminated"). Also not the
# participant's doing, but "the other players left" would be untrue, so it has
# its own note; the pay is the same as for a disbanded group.
STOPPED_REASON = "game terminated"

NEUTRAL_RETURN_REASON = "The study session ended before it could be completed."

# Not a server exitReason: lobby timeouts never reach a game, so the only record
# of them is their Prolific submission. See lobby_timeout_rows().
LOBBY_TIMEOUT_REASON = "lobby timeout"


def check_exit_reasons():
    """Refuse to word removal messages from a stale idea of why players are removed.

    `wording_for` sorts each removed participant into "your group left" or
    blame-neutral wording using the strings above. If the server starts
    recording a reason this file has never seen, the fallback is the neutral
    message -- which would be the wrong thing to send to someone whose group
    disbanded. Better to stop and have a person decide.
    """
    unknown = SERVER_EXIT_REASONS - KNOWN_EXIT_REASONS
    if unknown:
        listing = ", ".join(sorted(repr(r) for r in unknown))
        sys.exit(
            f"EXIT_REASONS in shared/constants.js has reason(s) this tooling does not know: "
            f"{listing}.\nAdd them to OTHERS_LEFT_REASONS or NEUTRAL_EXIT_REASONS in "
            "operations/session.py so removed participants get the right wording."
        )
    missing = KNOWN_EXIT_REASONS - SERVER_EXIT_REASONS
    if missing:
        listing = ", ".join(sorted(repr(r) for r in missing))
        print(f"Note: exit reason(s) {listing} are no longer in EXIT_REASONS in constants.js.",
              file=sys.stderr)


# Reasons that get the blame-neutral note: spelling out "low accuracy" would be
# unkind.
NEUTRAL_EXIT_REASONS = {"low accuracy"}
# Removed for idling: paid base pay prorated to time spent, no bonus. Gets its
# own plain note that says so without blaming anyone.
INACTIVE_REASON = "player timeout"
# Recorded by the client before a game exists, so these players never reach
# early_ended.csv; known here so the startup check does not refuse the reason,
# and skipped by `pay` if a row ever carries it, since it is paid nothing.
UNPAID_EXIT_REASONS = {"quiz failed"}
KNOWN_EXIT_REASONS = (
    OTHERS_LEFT_REASONS | NEUTRAL_EXIT_REASONS | {INACTIVE_REASON, STOPPED_REASON} | UNPAID_EXIT_REASONS
)


def wording_for(exit_reason, args):
    """Pick the return reason and note template for one removed participant.

    The server records one of the EXIT_REASONS in shared/constants.js
    (callbacks.js writes them). "group disbanded", "insufficient groups",
    "insufficient groups after accuracy check" and "game terminated" are not
    the participant's doing -- other players left, too few viable groups
    remained, or the researcher stopped the batch -- so those participants are
    told plainly that nothing went wrong on their end. "low accuracy" gets the
    blame-neutral wording, since spelling it out would be unkind; "player
    timeout" is in the participant's own hands and gets its own plain,
    non-blaming note. "quiz failed" never reaches here: those players are not
    paid, so extract_run.py writes them no row.
    """
    cleaned = exit_reason.strip().lower()
    if cleaned == LOBBY_TIMEOUT_REASON:
        name, default_reason = "lobby", "No game could be formed for this session."
        default_note = "lobby_payment.txt"
    elif cleaned in OTHERS_LEFT_REASONS:
        name = "others-left"
        default_reason = "Other players left, so the session could not be completed."
        default_note = "partial_payment_others_left.txt"
    elif cleaned == STOPPED_REASON:
        name = "stopped"
        default_reason = "The researcher stopped the session before it could be completed."
        default_note = "partial_payment_stopped.txt"
    elif cleaned == INACTIVE_REASON:
        name = "inactive"
        default_reason = ("The game removes players after several rounds without a response, "
                          "so the study could not be completed.")
        default_note = "partial_payment_inactive.txt"
    else:
        name, default_reason = "neutral", NEUTRAL_RETURN_REASON
        default_note = "partial_payment.txt"
    reason = args.reason or default_reason
    note_file = args.note_file or MESSAGES_DIR / default_note
    note_path = Path(note_file)
    if not note_path.exists():
        sys.exit(f"No note template at {note_path}.")
    return {"name": name, "reason": reason, "note": note_path.read_text()}


# ============ open: publish the screening survey ============


def cmd_open(args, token):
    """Publish the screening survey so responses start arriving."""
    study_id = from_session(args, "screening_study_id", args.study_id)
    if not study_id:
        sys.exit("Give the screening study id, or --session NAME.")
    study = api("GET", f"/studies/{study_id}/", token)
    filters = [f.get("filter_id") for f in (study.get("filters") or [])]
    print(f"Survey study: {study.get('name')}")
    print(f"Status:       {study.get('status')}")
    print(f"Places:       {study.get('total_available_places')}  (a ceiling; you pay per response)")
    print(f"Reward:       ${(study.get('reward') or 0) / 100:.2f} per response")
    print(f"Filters:      {', '.join(filters) or 'NONE'}")
    if study.get("status") != "UNPUBLISHED":
        sys.exit(f"\nThis study is {study.get('status')}, so there is nothing to publish.")
    if "participant_group_blocklist" not in filters:
        print("\nWARNING: no participant_group_blocklist -- people who have already played could sign up.")
    if not confirm("\nPublish this screening survey now?", args):
        return
    ok, error = transition_study(token, study_id, "PUBLISH", retries=3)
    if not ok:
        sys.exit(f"Publishing failed with {error}\nThe screening study is still unpublished.")
    print(f"Published at {datetime.now().astimezone():%H:%M:%S %Z}.")
    if args.session:
        print(f"Watch it fill with `session.py surveys --session {args.session}`,")
        print(f"then close it with `session.py close --session {args.session}` once `prepare` has run.")


# ============ close: stop paying for screening responses ============


def cmd_close(args, token):
    """Stop the screening survey once the allowlist is built.

    Nothing used to take the screening study down, so it kept collecting -- and
    paying for -- responses through the session and after it. Every response
    that arrives once `prepare` has frozen the allowlist costs its reward and
    tells someone they are expected at a session they will never be sent.
    """
    study_id = from_session(args, "screening_study_id", args.study_id)
    if not study_id:
        sys.exit("Give the screening study id, or --session NAME.")
    study = api("GET", f"/studies/{study_id}/", token)
    reward = (study.get("reward") or 0) / 100
    status = norm_status(study.get("status"))
    print(f"Survey study: {study.get('name')}")
    print(f"Status:       {status}")
    print(f"Places:       {study.get('total_available_places')} at ${reward:.2f} per response")
    if status == "UNPUBLISHED":
        sys.exit("\nThis study is UNPUBLISHED; there is nothing to stop and nobody to pay.")
    if status in ("COMPLETED", "AWAITING REVIEW"):
        print(f"\nAlready {status}; nothing to stop.")
    else:
        if not confirm("\nStop this screening survey? No further responses will be collected.", args):
            return
        # Prolific has named this action differently across API versions, so try
        # the ones it accepts rather than failing on the first.
        for action in ("STOP", "PAUSE"):
            ok, error = transition_study(token, study_id, action, retries=2)
            if ok:
                print(f"Stopped ({action}) at {datetime.now().astimezone():%H:%M:%S %Z}.")
                break
            print(f"  {action} was refused ({error.split(chr(10))[0][:120]})", file=sys.stderr)
        else:
            sys.exit("Could not stop the study through the API; stop it in the Prolific UI.")
    approve_screening_submissions(token, study_id, reward, args)


def approve_screening_submissions(token, study_id, reward, args):
    """Approve the screening survey's AWAITING REVIEW submissions, so respondents are paid.

    The survey study has one completion code and nothing to review: everyone
    who answered is owed the response reward, however they answered. Approving
    here pays them the same day instead of when Prolific's automatic approval
    gets to it. Approved and returned submissions are left alone, so this is
    safe to re-run.
    """
    submissions = list(paged(f"/studies/{study_id}/submissions/", token))
    by_status = {}
    for s in submissions:
        by_status[norm_status(s.get("status"))] = by_status.get(norm_status(s.get("status")), 0) + 1
    print(f"\n{len(submissions)} screening submissions:")
    for status, n in sorted(by_status.items()):
        print(f"  {n:3d} {status}")
    awaiting = [s for s in submissions if norm_status(s.get("status")) == "AWAITING REVIEW"]
    if not awaiting:
        print("No screening submissions awaiting review; nothing to approve.")
        return
    if not confirm(f"\nApprove {len(awaiting)} screening submission(s) awaiting review? "
                   f"Each pays the ${reward:.2f} response reward.", args):
        return
    for s in awaiting:
        api("POST", f"/submissions/{s['id']}/transition/", token, payload={"action": "APPROVE"})
    print(f"Approved {len(awaiting)}.")
    record_session_approval(
        getattr(args, "session", None), "screening", len(awaiting), reward
    )


# ============ approve: approve the finishers ============


def run_participant_ids(run):
    """Prolific ids in a run's bonuses.csv, or None if the run has none to read.

    `approve` pays the base reward on the strength of a completion code alone,
    which nothing used to check against the game data.
    """
    path = PROJECT_ROOT / "data" / "runs" / run / "bonuses.csv"
    if not path.exists():
        return None
    rows, _ = read_payment_csv(path, "bonus")
    print(f"Cross-checking against run {run} ({len(rows)} finishers in bonuses.csv)")
    return {row["id"] for row in rows}


def cmd_approve(args, token):
    """Approve every AWAITING REVIEW submission that carries the finished code."""
    study_id = from_session(args, "game_study_id", args.study_id)
    if not study_id:
        sys.exit("Give the game study id, or --session NAME.")
    submissions = list(paged(f"/studies/{study_id}/submissions/", token))

    by_status = {}
    for s in submissions:
        by_status[norm_status(s.get("status"))] = by_status.get(norm_status(s.get("status")), 0) + 1
    print(f"{len(submissions)} submissions:")
    for status, n in sorted(by_status.items()):
        print(f"  {n:3d} {status}")

    awaiting = [s for s in submissions if norm_status(s.get("status")) == "AWAITING REVIEW"]
    finishers = [s for s in awaiting if submission_code(s) == FINISHED_CODE]
    others = [s for s in awaiting if s not in finishers]
    if others:
        print(f"\n{len(others)} awaiting review WITHOUT the finished code -- these need a human:")
        for s in others:
            print(f"  {s.get('participant_id')}  submission {s.get('id')}  "
                  f"code {submission_code(s) or '(none)'}")

    # Removed and lobby-timeout players are paid by bonus and asked to return.
    # If they never do, Prolific eventually approves the submission anyway and
    # pays the full base reward on top of the partial payment they already had.
    at_risk = [s for s in awaiting if submission_code(s) in (PARTIAL_CODE, LOBBY_TIMEOUT_CODE)]
    if at_risk:
        print(f"\n{len(at_risk)} partial/lobby submission(s) are awaiting review rather than "
              "returned.\nIf they are left, Prolific will auto-approve them and pay the full "
              "base reward\non top of the partial payment already sent:")
        for s in at_risk:
            print(f"  {s.get('participant_id')}  submission {s.get('id')}  code {submission_code(s)}"
                  f"  return requested: {bool(s.get('return_requested'))}")

    # Cross-check against who the game data says actually played.
    run = args.run or (
        read_session(args.session).get("run") if getattr(args, "session", None) else None
    ) or newest_run()
    if not run:
        print(f"\nno run to cross-check against (no data/{active_dataset()}/runs.txt yet)")
        played = None
    else:
        played = run_participant_ids(run)
        if played is None:
            print(f"\nno bonuses.csv in data/runs/{run}, so nothing to cross-check against")
    if played is not None:
        claimed = {s.get("participant_id") for s in finishers}
        approved = {s.get("participant_id") for s in submissions
                    if norm_status(s.get("status")) == "APPROVED"}
        unbacked = sorted(claimed - played)
        if unbacked:
            print(f"\nWARNING: {len(unbacked)} submission(s) carry the finished code but do not "
                  "appear\nin this run's bonuses.csv, so the game data has no completed game "
                  "for them:")
            for participant in unbacked:
                print(f"  {participant}")
            print("Check these by hand before approving.")
        missing = sorted(played - claimed - approved)
        if missing:
            print(f"\nNote: {len(missing)} player(s) in bonuses.csv have no approved or "
                  "awaiting-review\nsubmission on this study -- they finished but never "
                  "submitted the code:")
            for participant in missing:
                print(f"  {participant}")

    if not finishers:
        print("\nNo finishers awaiting review. Nothing to approve.")
        return
    if not confirm(f"\nApprove {len(finishers)} finisher submission(s)? Payment of the base reward follows.", args):
        return
    for s in finishers:
        api("POST", f"/submissions/{s['id']}/transition/", token, payload={"action": "APPROVE"})
    print(f"Approved {len(finishers)}.")
    # Base pay for these finishers is the session's largest single cost, so
    # the budget `pay` enforces has to know it went out.
    study = api("GET", f"/studies/{study_id}/", token) or {}
    reward = (study.get("reward") or 0) / 100 or BASE_PAY
    record_session_approval(
        getattr(args, "session", None), "game", len(finishers), reward
    )


# ============ pay: bonuses, partial pay, and the notes that explain them ============


def active_dataset():
    """The dataset the data commands read: DATASET, defaulting to `full`.

    Never the frozen pilot: the analysis scripts default to `pilots`, but here
    a wrong default would pay or tally the pilot instead of the full sample.
    """
    return os.environ.get("DATASET") or "full"


def newest_run():
    """The most recent run registered in the active dataset's runs.txt.

    Deliberately not the newest directory under data/runs/: a stale re-export
    of an old server can sit there, and paying against it would pay past
    participants a second time.
    """
    runs_file = PROJECT_ROOT / "data" / active_dataset() / "runs.txt"
    if not runs_file.exists():
        return None
    runs = [
        line.split("#", 1)[0].strip()
        for line in runs_file.read_text().splitlines()
    ]
    runs = sorted(r for r in runs if r)
    return runs[-1] if runs else None


# What one person in each population can plausibly be owed. Used to derive a
# default --max-total, so a scoring bug that inflates everyone is caught even
# though no single amount trips --max-each.
def per_person_ceiling(population):
    if population == "bonuses":
        return MAX_BONUS * 2
    if population == "early":
        return BASE_PAY + MAX_BONUS * 2
    if population == "lobby":
        return LOBBY_TIMEOUT_PAY
    return MAX_BONUS * 2


def setup_payment(token, run_path, population, study_id, rows, ledger, max_each, max_total):
    """Create (but do not pay) one bulk bonus payment and record it in the ledger."""
    total = round(sum(r["amount"] for r in rows), 2)
    largest = max(r["amount"] for r in rows)
    if largest > max_each:
        sys.exit(f"{population}: largest amount ${largest:.2f} exceeds --max-each ${max_each:.2f}.")
    # --max-total used to default to nothing, so only a single outlier was ever
    # caught. The derived default scales with the number of people being paid.
    ceiling = max_total if max_total else round(len(rows) * per_person_ceiling(population), 2)
    if total > ceiling:
        source = "--max-total" if max_total else (
            f"the derived ceiling ({len(rows)} x ${per_person_ceiling(population):.2f})"
        )
        sys.exit(
            f"{population}: total ${total:.2f} exceeds {source} ${ceiling:.2f}.\n"
            "Nothing was set up. Check the amounts, or raise --max-total deliberately."
        )
    created = api(
        "POST",
        "/submissions/bonus-payments/",
        token,
        payload={
            "study_id": study_id,
            "csv_bonuses": "\n".join(f"{r['id']},{r['amount']:.2f}" for r in rows),
        },
    )
    ledger[population] = {
        "bulk_id": created.get("id"),
        "study_id": study_id,
        "participants": len(rows),
        # Recorded so a later run can tell whether these people were already
        # paid; see already_paid_elsewhere().
        "participants_paid": [r["id"] for r in rows],
        # Per person, so a later `pay` can prove the rows it is about to pay are
        # the rows this bulk payment was set up from; see check_rows_match_ledger().
        "amounts": {r["id"]: r["amount"] for r in rows},
        "requested_total": total,
        "response": {k: created.get(k) for k in ("amount", "fees", "vat", "total_amount")},
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "attempted_at": None,
        "paid_at": None,
    }
    # Written before the amount check: the bulk payment now exists at Prolific,
    # and the ledger must say so even if the check stops the command.
    write_ledger(run_path, ledger)
    check_setup_amount(population, ledger[population])
    return ledger[population]


def check_setup_amount(population, entry):
    """Stop if Prolific's bulk payment is not for the amount that was requested."""
    requested_total = float(entry.get("requested_total") or 0)
    requested_cents = round(requested_total * 100)
    amount = (entry.get("response") or {}).get("amount")
    try:
        amount = int(amount)
    except (TypeError, ValueError):
        amount = None
    if amount == requested_cents:
        return
    have = "no readable amount" if amount is None else f"{amount} cents"
    sys.exit(
        f"{population}: Prolific set up bulk payment {entry.get('bulk_id')} for {have}, "
        f"but {requested_cents} cents (${requested_total:.2f}) was requested.\n"
        "Nothing was paid. Check that bulk payment in the Prolific UI; if it is wrong, cancel\n"
        f"it there, remove the '{population}' entry from the run's prolific_payments.json, and\n"
        "re-run pay to set it up again."
    )


def check_rows_match_ledger(population, entry, rows):
    """Refuse to pay a set-up bulk payment whose rows no longer match what was set up.

    Prolific pays the amounts the bulk payment was created with, not the ones in
    the CSV today. If the CSV was re-extracted, or someone's submission was
    approved in the meantime and dropped out of the payable rows, the payment
    that is about to go out is not the one on the screen.
    """
    current = {row["id"]: round(row["amount"], 2) for row in rows}
    recorded_ids = set(entry.get("participants_paid") or [])
    problems = []
    added = sorted(set(current) - recorded_ids)
    removed = sorted(recorded_ids - set(current))
    if added:
        problems.append(f"now to be paid but not in the bulk payment: {', '.join(added)}")
    if removed:
        problems.append(f"in the bulk payment but no longer to be paid: {', '.join(removed)}")
    recorded_amounts = entry.get("amounts")
    if recorded_amounts is not None:
        for participant in sorted(set(current) & set(recorded_amounts)):
            if round(float(recorded_amounts[participant]), 2) != current[participant]:
                problems.append(
                    f"{participant}: ${float(recorded_amounts[participant]):.2f} set up, "
                    f"${current[participant]:.2f} now"
                )
    else:
        # Ledgers written before per-person amounts were recorded: the total is
        # the only amount there is to compare.
        total = round(sum(current.values()), 2)
        recorded_total = round(float(entry.get("requested_total") or 0), 2)
        if recorded_total != total:
            problems.append(f"total ${recorded_total:.2f} set up, ${total:.2f} now")
    if not problems:
        return
    listing = "\n".join(f"  - {problem}" for problem in problems)
    sys.exit(
        f"{population}: the rows to pay have changed since bulk payment {entry.get('bulk_id')} "
        f"was set up:\n{listing}\n\n"
        "Nothing was paid: paying it would send the amounts set up then, not these. Cancel\n"
        f"that bulk payment in the Prolific UI, remove the '{population}' entry from the run's\n"
        "prolific_payments.json, and re-run pay to set it up from the current rows."
    )


def ledger_cost(entry):
    """What one bulk payment costs in dollars: Prolific's fee-inclusive total when known."""
    total_amount = (entry.get("response") or {}).get("total_amount")
    if total_amount is not None:
        return total_amount / 100
    return float(entry.get("requested_total") or 0)


def paid_so_far(ledgers):
    """Dollars of bulk bonus payments already made across the given ledgers."""
    return round(
        sum(
            ledger_cost(entry)
            for ledger in ledgers
            for entry in ledger_entries(ledger).values()
            if entry.get("paid_at")
        ),
        2,
    )


def record_session_approval(session_name, kind, count, each):
    """Record what an `approve` or `close` run committed, so the budget can see it.

    Approvals are the session's largest line -- base pay for every finisher --
    and they leave no ledger, because Prolific pays them against the study
    rather than through a bulk payment. Until they were recorded here the
    budget check compared bonuses alone against a ceiling that was mostly base
    pay, so it could not trip however wrong the figures were.

    The cost is an estimate: Prolific reports no total for an approval, so the
    standard fee is applied to the reward, where a bulk payment's entry
    carries the exact figure Prolific charged.
    """
    if not session_name or count <= 0:
        return
    data = read_session(session_name)
    approvals = list(data.get("approvals") or [])
    approvals.append({
        "kind": kind,
        "count": count,
        "each_usd": round(each, 2),
        "estimated_cost_usd": round(count * each * (1 + PROLIFIC_FEE_RATE), 2),
        "at": datetime.now().isoformat(timespec="seconds"),
    })
    write_session(session_name, approvals=approvals)


def approvals_cost(saved):
    """Estimated dollars committed by this session's recorded approvals."""
    return round(
        sum(float(a.get("estimated_cost_usd") or 0) for a in (saved.get("approvals") or [])),
        2,
    )


def session_spend(saved, ledgers):
    """Everything this session has committed: bulk bonus payments plus approvals."""
    return round(paid_so_far(ledgers) + approvals_cost(saved), 2)


def check_session_budget(budget, spent, about_to_pay, args):
    """Refuse to take a session past the budget `setup` recorded. Returns whether to go on."""
    if budget is None:
        return True
    after = round(spent + about_to_pay, 2)
    if after <= budget:
        print(f"Session budget: ${after:,.2f} of ${budget:,.2f} after this payment "
              f"(${spent:,.2f} already committed, approvals included).")
        return True
    message = (
        f"Paying ${about_to_pay:,.2f} would take this session's Prolific spend to ${after:,.2f} "
        f"(${spent:,.2f} already committed in approvals and bonuses), over its budget of "
        f"${budget:,.2f}"
    )
    if not getattr(args, "force_budget", False):
        sys.exit(
            f"{message}.\nNothing was paid. The budget was set by `setup` (its cost ceiling, or "
            "--budget); check the amounts, or pass --force-budget if the overrun is deliberate."
        )
    print(f"\nWARNING: {message} (--force-budget given).")
    return confirm("Pay over the session budget anyway?", args)


def pay_bulk(token, run_path, population, entry, ledger):
    """Pay one bulk payment, recording the attempt before making it.

    The pay endpoint is not idempotent, and `paid_at` used to be written only
    after the call returned. A request that timed out after Prolific had already
    processed it therefore left the ledger reading "unpaid", and the runbook
    invites a re-run -- which would have paid everyone twice. The attempt is
    recorded first, and an attempt without a completion is never retried blindly.
    """
    entry["attempted_at"] = datetime.now().isoformat(timespec="seconds")
    write_ledger(run_path, ledger)
    ok, _, error = request_api("POST", f"/bulk-bonus-payments/{entry['bulk_id']}/pay/", token)
    if not ok:
        entry["last_error"] = error
        write_ledger(run_path, ledger)
        sys.exit(
            f"{population}: the pay call failed with {error}\n\n"
            "The attempt is recorded in the ledger. Prolific may or may not have processed\n"
            f"it, so DO NOT simply re-run: check bulk payment {entry['bulk_id']} in the\n"
            "Prolific UI first, and set its paid_at in the ledger by hand if it went through."
        )
    entry["paid_at"] = datetime.now().isoformat(timespec="seconds")
    write_ledger(run_path, ledger)


def check_unfinished_attempt(population, entry):
    """Stop if a previous pay attempt was recorded but never completed."""
    if entry.get("attempted_at") and not entry.get("paid_at"):
        sys.exit(
            f"{population}: a pay call was attempted at {entry['attempted_at']} and never\n"
            "recorded as finished, so it is not known whether Prolific processed it.\n\n"
            f"Check bulk payment {entry.get('bulk_id')} in the Prolific UI. If it was paid,\n"
            f"add a \"paid_at\" to {population} in the run's prolific_payments.json; if it was\n"
            "not, clear \"attempted_at\" there. Re-running blindly would risk paying twice."
        )


def norm_status(status):
    """One spelling for a submission status: "awaiting_review" -> "AWAITING REVIEW"."""
    return (status or "").strip().replace("_", " ").upper()


def submission_code(submission):
    """The completion code on a submission, without the stray trailing period some carry."""
    return (submission.get("study_code") or "").strip().rstrip(".")


# Only these submissions are paid a partial or lobby-timeout bonus. An APPROVED
# one has already been paid the full base reward, so a bonus on top would pay
# the person twice; a REJECTED one was refused on purpose.
PAYABLE_STATUSES = {"RETURNED", "AWAITING REVIEW"}


def payable_rows(rows, submissions_by_participant):
    """Split partial and lobby rows into those to pay and those to skip, with the reason.

    Returns (payable, skipped), where skipped is [(row, why)].
    """
    payable, skipped = [], []
    for row in rows:
        if (row.get("exit_reason") or "").strip().lower() in UNPAID_EXIT_REASONS:
            skipped.append((row, f"exit reason {row['exit_reason']!r} is paid nothing by design"))
            continue
        submission = submissions_by_participant.get(row["id"])
        if submission is None:
            skipped.append((row, "no submission on this study"))
            continue
        status = norm_status(submission.get("status"))
        if status == "APPROVED":
            skipped.append((row, "APPROVED: already paid the full base reward, so a partial "
                                 "payment on top would pay twice"))
        elif status == "REJECTED":
            skipped.append((row, "REJECTED: pay by hand if the rejection was a mistake"))
        elif status not in PAYABLE_STATUSES:
            skipped.append((row, f"{status or 'no status'}: only RETURNED or AWAITING REVIEW "
                                 "submissions are paid"))
        else:
            payable.append(row)
    return payable, skipped


def lobby_timeout_rows(token, study_id, submissions=None):
    """Participants owed the lobby-timeout payment, read from Prolific.

    These people are invisible to the whole data pipeline: Empirica only creates
    a player record once someone is placed in a game, so anyone who waited out
    the lobby appears in neither bonuses.csv nor early_ended.csv. The Sorry page
    promises them LOBBY_TIMEOUT_PAY for their time, and until this existed
    nothing in the tooling ever paid it -- their submission's only trace is the
    completion code, which requests a return and nothing more. Pass the study's
    submissions if they are already fetched.
    """
    if submissions is None:
        submissions = paged(f"/studies/{study_id}/submissions/", token)
    seen, rows = set(), []
    for submission in submissions:
        code = submission_code(submission)
        participant = submission.get("participant_id")
        if code != LOBBY_TIMEOUT_CODE or not participant or participant in seen:
            continue
        seen.add(participant)
        rows.append({
            "id": participant,
            "amount": round(LOBBY_TIMEOUT_PAY, 2),
            "exit_reason": LOBBY_TIMEOUT_REASON,
        })
    return rows


def cmd_pay(args, token):
    """Pay everyone a session owes, then send the notes that explain why.

    Three populations: the finishers' bonuses and the removed players' partial
    pay, both from the run's CSVs, and the lobby timeouts, who are read from
    Prolific because they never reach a game and so appear in no export at all.
    Every partial and lobby row is joined to its submission, and only RETURNED
    or AWAITING REVIEW submissions are paid: an APPROVED one already received
    the full base reward.

    Three confirmations, one per irreversible step: set up (charges nothing, but
    reveals Prolific's fee-inclusive total), pay, and message. A ledger under
    the run directory records each bulk payment id, the people and amounts in
    it, when it was paid, and who has had a note, so re-running never pays or
    messages twice -- the pay endpoint is not idempotent. The ledger also
    guards across runs, because exports are cumulative and a bonus file that
    was not scoped to one batch would otherwise pay an earlier session again.
    """
    saved = read_session(args.session) if args.session else {}
    study_id = from_session(args, "game_study_id", args.study)
    if not study_id:
        sys.exit("Give --study, or --session NAME.")
    run = args.run or saved.get("run") or newest_run()
    if not run:
        sys.exit("No run registered in the active dataset. Run analysis/extract_run.py --dataset full first, or pass --run.")
    run_path = run_dir(run)
    if args.session:
        write_session(args.session, run=run)
    print(f"Run:   {run}   (pass --run to choose another)")
    print(f"Study: {study_id}")

    meta_path = run_path / "run_meta.json"
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else None
    if meta is not None:
        batch = meta.get("batch")
        print(f"Batch: {batch or 'ALL batches in the export -- check this is what you want'}"
              f"   ({meta.get('finishers', '?')} finishers, {meta.get('early_ended', '?')} removed)")
    else:
        print("Batch: unknown -- this run was extracted before bonus files were scoped to a\n"
              "       batch, so it may contain players from earlier sessions. Re-extract it.")
    check_run_treatment(run_path, meta, saved)
    print()

    # Fetched once: the status filter, the lobby rows and the notes all read it.
    submissions = list(paged(f"/studies/{study_id}/submissions/", token))
    by_participant = {s.get("participant_id"): s for s in submissions if s.get("participant_id")}

    populations = {}
    for pop, filename, column in (
        ("bonuses", "bonuses.csv", "bonus"),
        ("early", "early_ended.csv", "partial_pay"),
    ):
        path = run_path / filename
        if path.exists():
            rows, skipped = read_payment_csv(path, column)
            if rows:
                populations[pop] = (rows, skipped)
    if not args.skip_lobby:
        lobby = lobby_timeout_rows(token, study_id, submissions=submissions)
        if lobby:
            populations["lobby"] = (lobby, 0)

    label = {"bonuses": "finishers", "early": "removed early", "lobby": "lobby timeouts"}
    for pop in ("early", "lobby"):
        if pop not in populations:
            continue
        rows, zero_rows = populations[pop]
        payable, skipped = payable_rows(rows, by_participant)
        if skipped:
            print(f"{label[pop]}: {len(skipped)} of {len(rows)} not paid:")
            for row, why in skipped:
                print(f"  {row['id']}  ${row['amount']:6.2f}  "
                      f"{row['exit_reason'] or 'reason not recorded'}  -- {why}")
        if payable:
            populations[pop] = (payable, zero_rows)
        else:
            del populations[pop]
    if not populations:
        sys.exit("Nothing to pay: no payable rows in bonuses.csv or early_ended.csv, "
                 "and no payable lobby-timeout submissions on this study.")

    ledger = read_ledger(run_path)

    # A pay call that was started and never confirmed has to be resolved by a
    # person before anything else happens on this run.
    for pop in populations:
        if ledger.get(pop):
            check_unfinished_attempt(pop, ledger[pop])

    # Cross-run guard: catches a bonus file that was not scoped to one batch.
    elsewhere = already_paid_elsewhere(run)
    clashes = [
        (row["id"], pop, elsewhere[row["id"]])
        for pop, (rows, _) in populations.items()
        for row in rows
        if row["id"] in elsewhere and not (ledger.get(pop) or {}).get("paid_at")
    ]
    if clashes:
        listing = "\n".join(f"  {pid}  in this run's {pop}, already paid by {where}"
                            for pid, pop, where in clashes[:15])
        more = f"\n  ... and {len(clashes) - 15} more" if len(clashes) > 15 else ""
        sys.exit(
            f"{len(clashes)} participant(s) in this run were already paid by another run:\n"
            f"{listing}{more}\n\n"
            "Exports are cumulative. Either this run's bonus files were not scoped to one\n"
            "batch, or this is a second export of a session that was already paid. Check\n"
            "which, re-extract with `analysis/extract_run.py --batch <id>` if it is the\n"
            "first, and pass --run to pay the right one. Nothing was paid."
        )

    for pop, (rows, skipped) in populations.items():
        total = sum(r["amount"] for r in rows)
        entry = ledger.get(pop)
        state = "paid" if entry and entry.get("paid_at") else "set up, not paid" if entry else "not set up"
        note = f"  ({skipped} zero rows skipped)" if skipped else ""
        print(f"{label[pop]:14s} {len(rows):3d} people  ${total:8.2f}{note}  -- {state}")

    # Phase 1: set up whatever is not set up yet.
    to_setup = [pop for pop in populations if not ledger.get(pop)]
    if to_setup:
        if not confirm("\nSet these up with Prolific? This charges nothing yet.", args):
            return
        for pop in to_setup:
            setup_payment(token, run_path, pop, study_id, populations[pop][0], ledger,
                          args.max_each, args.max_total)
            print(f"  {label[pop]}: set up, bulk id {ledger[pop]['bulk_id']}")

    # Prolific's own totals, fees included.
    grand = 0.0
    print("\nProlific's totals (fees and VAT included):")
    for pop in populations:
        entry = ledger.get(pop) or {}
        total_amount = (entry.get("response") or {}).get("total_amount")
        paid = entry.get("paid_at")
        if total_amount is not None:
            print(f"  {label[pop]:14s} ${total_amount / 100:8.2f}  {'paid ' + paid if paid else 'unpaid'}")
            if not paid:
                grand += total_amount / 100

    # Phase 2: pay whatever is unpaid.
    unpaid = [pop for pop in populations if ledger.get(pop) and not ledger[pop].get("paid_at")]
    if unpaid:
        # A bulk payment set up on an earlier run of this command pays what it
        # was set up with, so the rows must still be those rows, and Prolific
        # must have understood the amount.
        for pop in unpaid:
            check_rows_match_ledger(pop, ledger[pop], populations[pop][0])
            check_setup_amount(pop, ledger[pop])
        budget = saved.get("budget_usd") if args.session else None
        if args.session and budget is None:
            print("\n(This session has no budget_usd; it was set up before budgets existed.)")
        if not check_session_budget(
            budget, session_spend(saved, session_ledgers(saved, run, ledger)), grand, args
        ):
            return
        if not confirm(f"\nPay ${grand:,.2f} now? This cannot be undone.", args):
            return
        for pop in unpaid:
            pay_bulk(token, run_path, pop, ledger[pop], ledger)
            print(f"  {label[pop]}: paid")
    else:
        print("\nEverything is already paid.")

    # Phase 3: notes to the people who were not simply finishers, one each.
    rows = [row for pop in ("early", "lobby") if pop in populations
            for row in populations[pop][0]]
    if not rows:
        return
    if ledger.get("notes_sent_at"):
        print(f"\nExplanatory notes were already sent at {ledger['notes_sent_at']} "
              "(this ledger predates per-participant note records).")
        return
    noted = ledger.get("notes_sent") or {}
    pending = [row for row in rows if row["id"] not in noted]
    if not pending:
        print(f"\nExplanatory notes were already sent to all {len(rows)} people.")
        return
    if len(pending) < len(rows):
        print(f"\n{len(rows) - len(pending)} of {len(rows)} notes were already sent; "
              f"{len(pending)} remain.")
    actionable = []
    print(f"\nNotes for the {len(pending)} people who did not finish:")
    for row in pending:
        submission = by_participant[row["id"]]
        status = norm_status(submission.get("status"))
        done = status == "RETURNED" or bool(submission.get("return_requested"))
        wording = wording_for(row["exit_reason"], args)
        print(f"  {status:15s} ${row['amount']:6.2f}  {row['exit_reason'] or 'reason not recorded':42s}"
              f" -> {'note only' if done else 'request return + note'} [{wording['name']}]")
        actionable.append((submission, row, wording, not done))
    for name in sorted({a[2]["name"] for a in actionable}):
        example = next(a for a in actionable if a[2]["name"] == name)
        print(f"\n--- '{name}' wording, example at ${example[1]['amount']:.2f} ---")
        print(f"Return reason: {example[2]['reason']}")
        print(example[2]["note"].replace("{amount}", f"{example[1]['amount']:.2f}").rstrip())
    if not confirm(f"\nSend these notes to {len(actionable)} people?", args):
        return
    for submission, row, wording, needs_return in actionable:
        if needs_return:
            api("POST", f"/submissions/{submission['id']}/request-return/", token,
                payload={"request_return_reasons": [wording["reason"]]})
        api("POST", "/messages/", token, payload={
            "participant_id": submission["participant_id"],
            "study_id": study_id,
            "body": wording["note"].replace("{amount}", f"{row['amount']:.2f}"),
        })
        # Recorded per person and at once, so a failure part-way through leaves
        # the people already messaged marked as such.
        ledger.setdefault("notes_sent", {})[row["id"]] = datetime.now().isoformat(timespec="seconds")
        write_ledger(run_path, ledger)
    print(f"Sent {len(actionable)} notes.")


def session_ledgers(saved, run, ledger):
    """The ledgers a session's spending is spread over: this run's, plus the one it paid before."""
    ledgers = [ledger]
    earlier = saved.get("run")
    if earlier and earlier != run and (PROJECT_ROOT / "data" / "runs" / earlier).is_dir():
        ledgers.append(read_ledger(PROJECT_ROOT / "data" / "runs" / earlier))
    return ledgers


def check_run_treatment(run_path, meta, saved):
    """Warn when the run's games are not the treatment the session was set up for.

    extract_run.py copies the raw game table to data/runs/<run>/raw/game.csv
    and lists the batch's game ids in run_meta.json. If those games' condition
    or tangram set is not what `setup` recorded, the batch in Empirica was made
    with the wrong treatment, or the wrong run is being paid.
    """
    if not saved:
        return
    table = run_path / "raw" / "game.csv"
    if not table.exists():
        return
    with open(table, newline="") as handle:
        games = list(csv.DictReader(handle))
    wanted = set((meta or {}).get("games") or [])
    if wanted:
        games = [g for g in games if g.get("id") in wanted]
    games = [g for g in games if (g.get("condition") or "").strip()]
    if not games:
        return
    found = {}
    for game in games:
        found.setdefault("condition", set()).add(game["condition"].strip())
        raw_set = (game.get("tangram_set") or "").strip()
        if raw_set:
            found.setdefault("set", set()).add(str(int(float(raw_set))))
    declared = {"condition": saved.get("condition"), "set": str(saved.get("tangram_set"))}
    for key, label in (("condition", "condition"), ("set", "tangram set")):
        if declared[key] in (None, "None") or key not in found:
            continue
        if found[key] != {declared[key]}:
            print(f"WARNING: this run's games have {label} {', '.join(sorted(found[key]))}, "
                  f"but the session was set up for {declared[key]}.\n"
                  "         Either the batch was created with the wrong treatment, or this is\n"
                  "         not the session's run (pass --run).")


# ============ tally: games per treatment cell ============

TANGRAM_SETS = ("0", "1")


def tangram_set_label(raw):
    """One spelling for a tangram set: "0.0", "0", 0 and 0.0 are all "0"."""
    text = ("" if raw is None else str(raw)).strip()
    if not text:
        return "?"
    try:
        return str(int(float(text)))
    except ValueError:
        return text


def read_player_removals(path):
    """{gameId: (players, removed)} from a players.csv; {} when it cannot say.

    A removed player is one whose `isActive` is false, which is how
    analysis/R/attrition.R defines it, so the two agree on what an intact game
    is.
    """
    if not path.exists():
        return {}
    with open(path, newline="") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames or []
        if "gameId" not in fields or "isActive" not in fields:
            return {}
        per_game = {}
        for row in reader:
            game = (row.get("gameId") or "").strip()
            if not game:
                continue
            players, removed = per_game.get(game, (0, 0))
            active = (row.get("isActive") or "").strip().lower() in ("true", "1")
            per_game[game] = (players + 1, removed + (0 if active else 1))
    return per_game


def game_status_label(row, removals):
    """"intact", "partial" or "incomplete" for one games.csv row.

    The stopping rule counts games that finished with all nine players still
    in them, so that is what "intact" means and what a cell's target is
    measured in. A game that finished a player short still yields usable
    data, so it is counted separately rather than discarded or, as this used
    to do, counted as if it were whole.
    """
    reason = (row.get("endedReason") or "").strip()
    if reason and reason != "end of game":
        return "incomplete"
    game_id = (row.get("gameId") or "").strip()
    if game_id in removals:
        players, removed = removals[game_id]
        return "intact" if players == PLAYERS_PER_GAME and removed == 0 else "partial"
    # No players.csv to check against. Fall back to the roster size the game
    # itself recorded, which counts everyone who was ever assigned and so
    # cannot see a removal; print_tally warns when it comes to this.
    try:
        assigned = int(float(row.get("numPlayers") or 0))
    except ValueError:
        assigned = 0
    return "intact" if assigned == PLAYERS_PER_GAME else "partial"


def read_games_table(path, removals=None):
    """[(condition, set, status)] for every game in a games.csv.

    `status` is one of "intact", "partial" and "incomplete"; see
    game_status_label. Removals are read from the players.csv beside the games
    file unless they are passed in.
    """
    if removals is None:
        removals = read_player_removals(Path(path).parent / "players.csv")
    with open(path, newline="") as handle:
        reader = csv.DictReader(handle)
        games = []
        for row in reader:
            condition = (row.get("condition") or "").strip()
            if not condition:
                continue
            games.append((
                condition,
                tangram_set_label(row.get("tangramSet")),
                game_status_label(row, removals),
            ))
    return games


def empty_cell():
    return {"intact": 0, "partial": 0, "incomplete": 0, "sessions": 0, "pending": 0}


def cell_counts(games, sessions):
    """Games and sessions per (condition, set) cell, every cell present.

    Returns (counts, emptiest): counts maps each cell to the keys of
    empty_cell(), where "intact" are the nine-player games the stopping rule
    counts, "partial" those that finished a player short, "incomplete" those
    that did not finish, "sessions" the saved sessions declaring the cell and
    "pending" those of them with no run paid yet. The emptiest cell has the
    fewest intact games, then the fewest sessions, then comes first in the
    conditions' order.
    """
    counts = {
        (condition, tangram_set): empty_cell()
        for condition in CONDITIONS
        for tangram_set in TANGRAM_SETS
    }
    for condition, tangram_set, status in games:
        cell = counts.setdefault((condition, tangram_set), empty_cell())
        cell[status] += 1
    for data in sessions.values():
        if not data.get("condition"):
            continue
        cell = counts.setdefault(
            (data["condition"], tangram_set_label(data.get("tangram_set"))),
            empty_cell(),
        )
        cell["sessions"] += 1
        if not data.get("run"):
            cell["pending"] += 1

    def order(cell):
        condition, tangram_set = cell
        rank = CONDITIONS.index(condition) if condition in CONDITIONS else len(CONDITIONS)
        return (counts[cell]["intact"], counts[cell]["sessions"], rank, tangram_set)

    emptiest = min(counts, key=order)
    return counts, emptiest


def tally_lines(counts, emptiest):
    lines = [
        f"  {'condition':18s} {'set':>3s} {'intact':>6s} {'partial':>8s} "
        f"{'incomplete':>11s} {'sessions':>9s}"
    ]
    for (condition, tangram_set), cell in counts.items():
        pending = f" ({cell['pending']} pending)" if cell["pending"] else ""
        marker = "   <- emptiest" if (condition, tangram_set) == emptiest else ""
        lines.append(
            f"  {condition:18s} {tangram_set:>3s} {cell['intact']:6d} {cell['partial']:8d} "
            f"{cell['incomplete']:11d} {cell['sessions']:9d}{pending}{marker}"
        )
    return lines


def print_tally(dataset=None):
    """Print games per treatment cell; returns (counts, emptiest) or None with no games yet."""
    dataset = dataset or active_dataset()
    games_path = PROJECT_ROOT / "data" / dataset / "games.csv"
    sessions = saved_sessions()
    if not games_path.exists():
        print(f"no games yet (no {games_path.relative_to(PROJECT_ROOT)})")
        if not sessions:
            return None
        games = []
    else:
        players_path = games_path.parent / "players.csv"
        removals = read_player_removals(players_path)
        games = read_games_table(games_path, removals)
        intact = sum(1 for g in games if g[2] == "intact")
        others = len(games) - intact
        print(f"{intact} intact nine-player game(s) in data/{dataset}/games.csv"
              + (f", {others} that lost a player or did not finish" if others else "")
              + f"; {len(sessions)} saved session(s):")
        if not removals:
            print(f"  WARNING: no usable {players_path.name} beside games.csv, so a game that "
                  "lost a player cannot be told from an intact one. The intact count below is "
                  "an upper bound.")
    counts, emptiest = cell_counts(games, sessions)
    for line in tally_lines(counts, emptiest):
        print(line)
    print("  Intact = finished with all nine players, which is what the stopping rule counts.")
    print("  Partial games still yield data; they do not count towards a cell's target.")
    print("  Sessions are the saved session files; pending ones have not paid a run yet.")
    return counts, emptiest


def cmd_tally(args, token=None):
    """Games per (condition, tangram set) cell, so the next session fills the emptiest. Needs no token."""
    print_tally(getattr(args, "dataset", None))


NO_TOKEN_COMMANDS = {"sessions", "tally"}


def main():
    parser = argparse.ArgumentParser(
        description="Run a data-collection session on Prolific. Every command that changes "
                    "anything shows its plan and asks before acting; pass --yes to skip the prompt.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def yes(p):
        p.add_argument("-y", "--yes", action="store_true", help="skip the confirmation prompt")

    def session(p, what):
        p.add_argument("--session", help=f"session name; supplies {what}")

    # --- lookups (read-only) ---
    p = sub.add_parser("sessions", help="list the sessions saved on this machine")
    p = sub.add_parser("tally", help="games per (condition, tangram set) cell, marking the emptiest")
    p.add_argument("--dataset", help="dataset whose games.csv to count (default: $DATASET or 'full')")
    p = sub.add_parser("surveys", help="watch this session's survey fill, or list survey ids")
    p.add_argument("--session", help="show only this session's survey and its count (one request)")
    p.add_argument("--counts", action="store_true", help="also fetch response counts (a request each)")
    p.add_argument("--limit", type=int, default=10, help="how many surveys to list (default 10)")
    p.add_argument("--all", action="store_true", help="list surveys even when --session is given")
    p = sub.add_parser("studies", help="list studies and their ids")
    p.add_argument("--match", default="communication game", help="substring of the study name ('' for all)")
    p.add_argument("--limit", type=int, default=15)

    # --- the session, in order ---
    p = sub.add_parser("setup", help="1. create the screening survey and both study drafts")
    p.add_argument("--session", help="a name for this session (default: condition-setN-date)")
    p.add_argument("--time", required=True, help='as it appears in the availability question, e.g. "6pm PT / 9pm ET"')
    p.add_argument("--title-time", help='shorter form for titles, e.g. "9pm ET" (default: --time)')
    p.add_argument("--condition", required=True, choices=CONDITIONS)
    p.add_argument("--set", required=True, choices=["0", "1"], help="tangram set")
    p.add_argument("--places", type=int, required=True, help="places on the game study (players you expect)")
    p.add_argument("--survey-places", type=int, default=100, help="ceiling on survey responses (default 100)")
    p.add_argument("--budget", type=float,
                   help="dollars this session may spend in total; `pay` refuses to go past it "
                        "(default: the cost ceiling setup prints)")
    p.add_argument("--blocklist-group", help=f"group id of past players (default: find '{BLOCKLIST_GROUP_NAME}')")
    p.add_argument("--template-survey", help="survey id to copy questions from (default: newest screening survey)")
    p.add_argument("--template-study", help="study id to copy game settings from (default: newest game study)")
    p.add_argument("--study-name", default=GAME_STUDY_NAME)
    p.add_argument("--internal-name", help="internal name for the game study draft")
    p.add_argument("--workspace", help="workspace id (default: PROLIFIC_WORKSPACE in .env)")
    p.add_argument(
        "--rehearsal",
        metavar="TEST_PARTICIPANT_ID",
        help="make a rehearsal: both studies allowlisted to this test participant only, 1 place each",
    )
    p.add_argument(
        "--allow-template-mismatch",
        action="store_true",
        help="create the draft even if the template's reward or completion codes have drifted "
             "from experiment/shared/constants.js",
    )
    yes(p)

    p = sub.add_parser("open", help="2. publish the screening survey")
    p.add_argument("study_id", nargs="?", help="screening study id (or --session)")
    session(p, "the screening study")
    yes(p)

    p = sub.add_parser("prepare", help="3. build the allowlist group from the survey and attach it to the game draft")
    p.add_argument("survey_id", nargs="?", help="survey id (or --session)")
    session(p, "the survey and game study")
    p.add_argument("--study", help="game study draft to allowlist (default: from --session)")
    p.add_argument("--name", help="group name (default: the session name)")
    p.add_argument("--workspace", help="workspace id (default: PROLIFIC_WORKSPACE in .env)")
    p.add_argument("--show-ids", action="store_true", help="print the eligible participant ids")
    p.add_argument(
        "--expect-questions",
        type=int,
        default=SCREENING_QUESTIONS,
        help=f"questions a complete response must carry (default {SCREENING_QUESTIONS}); "
             "responses with any other number are set aside rather than counted eligible",
    )
    yes(p)

    p = sub.add_parser("close", help="4. stop the screening survey so it collects no more responses")
    p.add_argument("study_id", nargs="?", help="screening study id (or --session)")
    session(p, "the screening study")
    yes(p)

    p = sub.add_parser("message", help="5. send the reminder to the session group")
    p.add_argument("group_id", nargs="?", help="participant group id (or --session)")
    session(p, "the group, screening study and time")
    p.add_argument("--time", help='substituted for {time} in the template (default: from --session)')
    p.add_argument("--study", help="study id to attach the message to (default: screening study)")
    p.add_argument("--body-file", help=f"template (default {MESSAGES_DIR}/reminder.txt)")
    yes(p)

    p = sub.add_parser("publish", help="6. publish the game study, optionally at a set time")
    p.add_argument("study_id", nargs="?", help="game study id (or --session)")
    session(p, "the game study")
    p.add_argument(
        "--at",
        help='wait until this 24-hour time, e.g. 21:00 or "21:00 ET". Without a timezone it '
             "is read in the timezone the session's announced time names, and a time that "
             "does not match what participants were told is refused",
    )
    p.add_argument("--force-time", action="store_true",
                   help="publish at --at even though it disagrees with the announced time")
    p.add_argument("--allow-open", action="store_true", help="publish even with no allowlist (whole Prolific pool)")
    yes(p)


    p = sub.add_parser("approve", help="7. approve the finishers' submissions")
    p.add_argument("study_id", nargs="?", help="game study id (or --session)")
    session(p, "the game study")
    p.add_argument("--run", help="run to cross-check finishers against (default: newest)")
    yes(p)

    p = sub.add_parser("pay", help="8. pay bonuses, partial pay and lobby-timeout pay, then send the notes")
    session(p, "the game study and run")
    p.add_argument("--study", help="game study id (default: from --session)")
    p.add_argument("--run", help="run timestamp under data/runs/ (default: newest)")
    p.add_argument("--max-each", type=float, default=MAX_EACH_DEFAULT,
                   help=f"refuse any single amount above this (default ${MAX_EACH_DEFAULT:.2f}, "
                        "BASE_PAY + MAX_BONUS from shared/constants.js)")
    p.add_argument("--max-total", type=float, help="refuse if a population's total exceeds this")
    p.add_argument("--force-budget", action="store_true",
                   help="pay even if it takes the session past the budget `setup` recorded (asks again)")
    p.add_argument("--reason", help="return reason shown to every removed player (default: by exit reason)")
    p.add_argument("--note-file", help="note template for every removed player (default: by exit reason)")
    p.add_argument("--skip-lobby", action="store_true",
                   help="do not pay the lobby-timeout participants this study recorded")
    yes(p)

    # --- maintenance ---
    p = sub.add_parser("blocklist", help="seed or repair the group of participants who have already played")
    p.add_argument("--name", default=BLOCKLIST_GROUP_NAME)
    p.add_argument("--workspace", help="workspace id (default: PROLIFIC_WORKSPACE in .env)")
    p.add_argument("--from-prolific", action="store_true", help="derive who played from Prolific submissions")
    p.add_argument("--study-name", default=GAME_STUDY_NAME)
    p.add_argument("--include-unknown", action="store_true", help="also block submissions with no completion code")
    yes(p)

    args = parser.parse_args()
    check_exit_reasons()
    # Commands that only read local files need no token, so a machine without
    # .env can still list sessions and count games.
    token = None if args.command in NO_TOKEN_COMMANDS else load_token()
    {
        "sessions": cmd_sessions,
        "tally": cmd_tally,
        "surveys": cmd_surveys,
        "studies": cmd_studies,
        "setup": cmd_setup,
        "open": cmd_open,
        "prepare": cmd_prepare,
        "message": cmd_message,
        "publish": cmd_publish,
        "close": cmd_close,
        "approve": cmd_approve,
        "pay": cmd_pay,
        "blocklist": cmd_blocklist,
    }[args.command](args, token)


if __name__ == "__main__":
    main()
