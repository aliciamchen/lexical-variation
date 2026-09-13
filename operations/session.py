"""
Run a Prolific data-collection session for the synchronous reference game.

The commands, in the order a session uses them:

    setup     create the screening survey and both study drafts
    open      publish the screening survey
    prepare   build the allowlist group from the survey; attach it to the game draft
    message   send the reminder to that group
    publish   publish the game study (optionally at a set clock time)
    approve   approve the finishers' submissions
    pay       set up and pay bonuses and partial pay; send the explanatory notes

    sessions / surveys / studies    look things up
    blocklist                       seed or repair the group of past players

Pass --session NAME to every step; `setup` saves the ids under that name and
the rest read them back. Every command that changes anything prints its plan
and asks before acting; --yes skips the prompt. The runbook is
operations/procedures.md. PROLIFIC_TOKEN and PROLIFIC_WORKSPACE come from the
repository-root .env and are never printed.
"""

import argparse
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests
from dotenv import dotenv_values

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


def session_file(name):
    return SESSIONS_DIR / f"{name}.json"


def read_session(name):
    """Load a session's saved ids, or exit naming the sessions that do exist."""
    import json

    path = session_file(name)
    if not path.exists():
        known = sorted(p.stem for p in SESSIONS_DIR.glob("*.json")) if SESSIONS_DIR.is_dir() else []
        listing = "\n".join(f"  {k}" for k in known) or "  (none yet)"
        sys.exit(f"No session {name!r}. Sessions on this machine:\n{listing}")
    return json.loads(path.read_text())


def write_session(name, **fields):
    """Merge ids into a session file, creating it if needed."""
    import json

    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    path = session_file(name)
    data = json.loads(path.read_text()) if path.exists() else {}
    data.update({k: v for k, v in fields.items() if v is not None})
    path.write_text(json.dumps(data, indent=2) + "\n")
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
FINISHED_CODE = "C2I8XDMC"


def cmd_sessions(args, token):
    """List the sessions saved on this machine."""
    if not SESSIONS_DIR.is_dir() or not any(SESSIONS_DIR.glob("*.json")):
        sys.exit(f"No sessions saved yet in {SESSIONS_DIR}.")
    import json

    for path in sorted(SESSIONS_DIR.glob("*.json")):
        data = json.loads(path.read_text())
        print(f"{path.stem}")
        for key in ("condition", "tangram_set", "time", "survey_id",
                    "screening_study_id", "game_study_id", "group_id", "run"):
            if data.get(key):
                print(f"  {key:20s} {data[key]}")


def load_token():
    """Read PROLIFIC_TOKEN from the repo-root .env without printing it."""
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        sys.exit(f"No .env at {env_path}. Copy .env.example and add PROLIFIC_TOKEN.")
    token = (dotenv_values(env_path).get("PROLIFIC_TOKEN") or "").strip()
    if not token:
        sys.exit("PROLIFIC_TOKEN is missing or empty in .env (see .env.example).")
    return token


def api(method, path, token, payload=None, params=None):
    """Call the Prolific API and return the decoded body (None for 204s)."""
    response = requests.request(
        method,
        f"{API_ROOT}{path}",
        headers={"Authorization": f"Token {token}"},
        json=payload,
        params=params,
        timeout=30,
    )
    if not response.ok:
        # Surface Prolific's own error text; it names the offending field.
        sys.exit(f"{method} {path} failed with {response.status_code}: {response.text[:500]}")
    if response.status_code == 204 or not response.content:
        return None
    return response.json()


def paged(path, token, params=None):
    """Yield every result from a paginated endpoint."""
    offset = 0
    while True:
        page = api(
            "GET", path, token, params={**(params or {}), "offset": offset, "limit": PAGE_SIZE}
        )
        results = page.get("results", []) if isinstance(page, dict) else page
        yield from results
        meta = page.get("meta") or {} if isinstance(page, dict) else {}
        # Surveys report meta.total; submissions report meta.count.
        total = meta.get("total", meta.get("count"))
        offset += PAGE_SIZE
        if total is None or offset >= total or not results:
            return


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
    """Flatten one survey response into {question_title: [answer values]}."""
    answers = {}
    sections = response.get("sections") or []
    questions = list(response.get("questions") or [])
    for section in sections:
        questions.extend(section.get("questions") or [])
    for question in questions:
        values = [a.get("value") for a in (question.get("answers") or [])]
        answers[question.get("question_title") or question.get("title") or "?"] = values
    return answers


def cmd_surveys(args, token):
    """List screening surveys, newest first, so you can pick the right id."""
    surveys = list(paged("/surveys/", token, params={"researcher_id": researcher_id(token)}))
    surveys.sort(key=lambda s: s.get("date_created") or "", reverse=True)
    print(f"{len(surveys)} surveys\n")
    for survey in surveys:
        survey_id = survey["_id"]
        created = (survey.get("date_created") or "")[:16].replace("T", " ")
        title = survey.get("title") or "(untitled)"
        suffix = ""
        if args.counts:
            count = (
                api("GET", f"/surveys/{survey_id}/responses/", token, params={"limit": 1}).get(
                    "meta", {}
                )
            ).get("total", 0)
            suffix = f"  [{count} responses]"
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
    print("\nThe game study is named 'Group communication game'; the screening one starts")
    print("'Screening survey:'. Survey ids (for `prepare`) come from `surveys --counts`.")


def set_study_allowlist(token, study_id, group_id):
    """Point a draft study's eligibility at a participant group.

    Prolific only allows `filters` to be changed while a study is still
    UNPUBLISHED -- after publishing, only internal_name, places, access_details
    and submissions_config are updatable -- so this refuses anything else.
    """
    study = api("GET", f"/studies/{study_id}/", token)
    status = study.get("status")
    if status != "UNPUBLISHED":
        sys.exit(
            f"Study {study_id} is {status}; Prolific only allows filters to be changed while\n"
            f"a study is UNPUBLISHED. Set the allowlist in the UI, or use a fresh draft."
        )

    existing = study.get("filters") or []
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

    eligible, rejected_by_question, seen = [], {}, set()
    for response in responses:
        participant = response.get("participant_id")
        if not participant or participant in seen:
            continue
        seen.add(participant)
        answers = survey_answers(response)
        failures = [q for q, values in answers.items() if values != [ELIGIBLE_ANSWER]]
        for question in failures:
            rejected_by_question[question] = rejected_by_question.get(question, 0) + 1
        if not failures:
            eligible.append(participant)

    print(f"Eligible (answered '{ELIGIBLE_ANSWER}' to every question): {len(eligible)}")
    print(f"Excluded: {len(seen) - len(eligible)}")
    for question, count in sorted(rejected_by_question.items(), key=lambda kv: -kv[1]):
        print(f"  {count:3d} did not answer '{ELIGIBLE_ANSWER}' to: {question[:80]}")
    # At the pilots' ~75% show-up rate, this is the expected turnout.
    print(f"\nExpected to show up at 75%: about {round(len(eligible) * 0.75)}")
    if args.show_ids:
        print("\n" + "\n".join(eligible))

    args.name = args.name or getattr(args, "session", None)
    if not args.name:
        sys.exit("Give --name for the group, or --session so the session name is used.")
    what = f"Create group '{args.name}' with these {len(eligible)} people"
    if args.study:
        what += f" and allowlist it on study {args.study}"
    if not confirm(f"\n{what}?", args):
        return
    if not eligible:
        sys.exit("No eligible participants, refusing to create an empty group.")

    group = api(
        "POST",
        "/participant-groups/",
        token,
        payload={
            "workspace_id": workspace_id(token, args.workspace),
            "name": args.name,
            "description": f"Eligible respondents to survey {args.survey_id}",
        },
    )
    added = api(
        "POST",
        f"/participant-groups/{group['id']}/participants/",
        token,
        payload={"participant_ids": eligible},
    )
    print(f"\nCreated group {group['id']} ({args.name})")
    print(f"Added {len(added.get('results', []))} of {len(eligible)} participants")
    if args.session:
        write_session(args.session, group_id=group["id"])
    if args.study:
        set_study_allowlist(token, args.study, group["id"])
    else:
        print("Use this group id as the allowlist filter on the game study,")
        print("or pass --study <game_study_id> next time to have it set for you.")


def cmd_message(args, token):
    """Send the reminder to a participant group (dry run unless --send)."""
    args.group_id = from_session(args, "group_id", args.group_id)
    args.study = from_session(args, "screening_study_id", args.study)
    args.time = args.time or (read_session(args.session).get("time") if args.session else None)
    if not args.group_id:
        sys.exit("Give a group id, or --session NAME once `prepare --create` has run.")
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
    when = f"at {args.at}" if args.at else "now"
    if not confirm(f"\nPublish this game study {when}?", args):
        return

    if args.at:
        try:
            hour, minute = (int(part) for part in args.at.split(":"))
        except ValueError:
            sys.exit("--at wants a 24-hour local clock time, e.g. --at 18:30.")
        now = datetime.now()
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            sys.exit(f"{args.at} is already past (it is {now:%H:%M}). Nothing published.")
        print(f"\nWaiting until {target:%H:%M} local ({(target - now).seconds // 60} min). Ctrl-C cancels.")
        while datetime.now() < target:
            remaining = target - datetime.now()
            print(f"  {remaining.seconds // 60:3d}m {remaining.seconds % 60:02d}s to go", end="\r")
            time.sleep(min(15, max(1, remaining.total_seconds())))
        print()

    api("POST", f"/studies/{args.study_id}/transition/", token, payload={"action": "PUBLISH"})
    print(f"Published at {datetime.now():%H:%M:%S}.")


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
    import csv

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

SCREENING_TITLE = "Screening survey: Group communication game [starts {time}]"


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


def retime_sections(sections, time_text):
    """Copy a survey's sections, substituting the session time and fresh ids."""
    import copy
    import re
    import uuid

    sections = copy.deepcopy(sections)
    changed = []
    for section in sections:
        section["id"] = str(uuid.uuid4())
        for question in section.get("questions") or []:
            question["id"] = str(uuid.uuid4())
            for answer in question.get("answers") or []:
                answer["id"] = str(uuid.uuid4())
            title = question.get("title") or ""
            # Only the availability question names a time.
            if re.search(r"available at ", title, re.I):
                found = re.search(r"available at (.*?) to participate", title, re.I)
                if found:
                    retime_sections.old_time = found.group(1).strip()
                new_title = re.sub(
                    r"available at .*? to participate",
                    f"available at {time_text} to participate",
                    title,
                    flags=re.I,
                )
                if new_title != title:
                    question["title"] = new_title
                    changed.append(new_title)
    if not changed:
        sys.exit(
            "Could not find an availability question to retime in the template survey.\n"
            "Check the template, or edit the new survey's time by hand after creating it."
        )
    return sections, changed


def with_group_action(completion_codes, group_id):
    """Make the game study add its own players to the blocklist group.

    Attaching `ADD_TO_PARTICIPANT_GROUP` to the codes that mean "saw the task"
    means Prolific maintains the blocklist itself: each player joins the group
    the moment they submit, so no post-session command is needed. The
    lobby-timeout code is deliberately left alone, so participants who never
    reached a game stay eligible for a later session.
    """
    import copy

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
    template_survey = pick_template_survey(token, args.template_survey)
    detail = api("GET", f"/surveys/{template_survey['_id']}", token)
    sections, retimed = retime_sections(detail.get("sections") or [], args.time)
    title = SCREENING_TITLE.format(time=args.title_time or args.time)

    screening_template = find_survey_study(token, template_survey["_id"])
    game_template = pick_template_study(token, args.study_name, args.template_study)

    # Participant-facing descriptions are copied from the templates, so any
    # mention of the previous session's time has to be swapped for the new one.
    old_time = getattr(retime_sections, "old_time", None)
    screening_description, n_screen = retime_text(
        (screening_template or {}).get("description"), old_time, args.time)
    game_description, n_game = retime_text(game_template.get("description"), old_time, args.time)
    if screening_template is not None:
        screening_template = {**screening_template, "description": screening_description}
    game_template = {**game_template, "description": game_description}
    print(f"Retimed descriptions: {n_screen} mention(s) in the screening study, {n_game} in the game study"
          + (f" ('{old_time}' -> '{args.time}')" if old_time else ""))

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

    if not confirm("\nCreate the survey and both study drafts? Nothing is published.", args):
        return

    survey = api(
        "POST",
        "/surveys/",
        token,
        payload={"researcher_id": researcher_id(token), "title": title, "sections": sections},
    )
    print(f"\nCreated survey {survey['_id']}")

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

    game = api("POST", "/studies/", token, payload=game_payload)
    print(f"Created game study draft {game['id']} ({game.get('status')})")
    print("\nNeither is published. Next: `session.py open --session <name>` when you are ready for responses.")
    print("\n--- ids for the rest of this session (keep these) ---")
    print(f"  SURVEY_ID={survey['_id']}          # prepare")
    print(f"  SCREENING_STUDY_ID={screening['id']}  # message --study")
    print(f"  GAME_STUDY_ID={game['id']}       # prepare, publish, approve, pay")
    print("`session.py sessions` shows them again; you should not need them with --session.")

    name = args.session or f"{args.condition}-set{args.set}-{datetime.now():%Y%m%d-%H%M}"
    path = write_session(
        name,
        condition=args.condition,
        tangram_set=args.set,
        time=args.title_time or args.time,
        survey_id=survey["_id"],
        screening_study_id=screening["id"],
        game_study_id=game["id"],
    )
    print(f"\nSaved to {path}. From here on you can use --session {name}")


def played_participant_ids():
    """Every participant who was actually placed in a game, across all runs.

    bonuses.csv and early_ended.csv are written only for players with a real
    gameID (see analysis/extract_run.py), so together they are exactly the set
    of people who saw the task. Participants who timed out in the lobby never
    reach either file and so stay eligible for later sessions. Amounts are
    ignored here -- a $0.00 partial pay still means they played.
    """
    import csv

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


# Completion codes from experiment/shared/constants.js. Someone who only ever
# timed out in the lobby never saw the task, so that code is deliberately absent
# from the "played" set and those participants stay eligible for later sessions.
PLAYED_CODES = {"C2I8XDMC", "CFTYDMIY"}
LOBBY_TIMEOUT_CODE = "CMZUY3MK"


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
    import json

    path = ledger_path(run_path)
    return json.loads(path.read_text()) if path.exists() else {}


def write_ledger(run_path, ledger):
    import json

    ledger_path(run_path).write_text(json.dumps(ledger, indent=2) + "\n")



# ============ wording for removed participants ============

OTHERS_LEFT_REASONS = {"group disbanded", "insufficient groups after accuracy check"}

NEUTRAL_RETURN_REASON = "The study session ended before it could be completed."

# Mirrors `conditions` in experiment/shared/constants.js.
CONDITIONS = ["refer_separated", "refer_mixed", "social_mixed", "social_first"]


def wording_for(exit_reason, args):
    """Pick the return reason and note template for one removed participant.

    Removals happen for four causes (experiment/server/src/callbacks.js). Two
    are caused by other players leaving, so those participants can be told
    plainly that nothing went wrong on their end. "low accuracy" and "player
    timeout" get blame-neutral wording: the first would be unkind to spell out,
    and the second was in the participant's own hands.
    """
    others_left = exit_reason.strip().lower() in OTHERS_LEFT_REASONS
    name = "others-left" if others_left else "neutral"
    if args.reason:
        reason = args.reason
    elif others_left:
        reason = "Other players left, so the session could not be completed."
    else:
        reason = NEUTRAL_RETURN_REASON
    note_file = args.note_file or MESSAGES_DIR / (
        "partial_payment_others_left.txt" if others_left else "partial_payment.txt"
    )
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
    api("POST", f"/studies/{study_id}/transition/", token, payload={"action": "PUBLISH"})
    print(f"Published at {datetime.now():%H:%M:%S}. Watch it fill with `session.py surveys --counts`.")


# ============ approve: approve the finishers ============


def cmd_approve(args, token):
    """Approve every AWAITING REVIEW submission that carries the finished code."""
    study_id = from_session(args, "game_study_id", args.study_id)
    if not study_id:
        sys.exit("Give the game study id, or --session NAME.")
    submissions = list(paged(f"/studies/{study_id}/submissions/", token))

    def norm(status):
        return (status or "").replace("_", " ").upper()

    by_status = {}
    for s in submissions:
        by_status[norm(s.get("status"))] = by_status.get(norm(s.get("status")), 0) + 1
    print(f"{len(submissions)} submissions:")
    for status, n in sorted(by_status.items()):
        print(f"  {n:3d} {status}")

    awaiting = [s for s in submissions if norm(s.get("status")) == "AWAITING REVIEW"]
    finishers = [s for s in awaiting if (s.get("study_code") or "").strip().rstrip(".") == FINISHED_CODE]
    others = [s for s in awaiting if s not in finishers]
    if others:
        print(f"\n{len(others)} awaiting review WITHOUT the finished code -- these need a human:")
        for s in others:
            print(f"  code {s.get('study_code')!r}")
    if not finishers:
        print("\nNo finishers awaiting review. Nothing to approve.")
        return
    if not confirm(f"\nApprove {len(finishers)} finisher submission(s)? Payment of the base reward follows.", args):
        return
    for s in finishers:
        api("POST", f"/submissions/{s['id']}/transition/", token, payload={"action": "APPROVE"})
    print(f"Approved {len(finishers)}.")


# ============ pay: bonuses, partial pay, and the notes that explain them ============


def newest_run():
    """The most recent run registered in the active dataset's runs.txt.

    Deliberately not the newest directory under data/runs/: a stale re-export
    of an old server can sit there, and paying against it would pay past
    participants a second time. DATASET defaults to `full` here, never to the
    frozen pilot.
    """
    import os

    dataset = os.environ.get("DATASET") or "full"
    runs_file = PROJECT_ROOT / "data" / dataset / "runs.txt"
    if not runs_file.exists():
        return None
    runs = [
        line.split("#", 1)[0].strip()
        for line in runs_file.read_text().splitlines()
    ]
    runs = sorted(r for r in runs if r)
    return runs[-1] if runs else None


def setup_payment(token, run_path, population, study_id, rows, ledger, max_each, max_total):
    """Create (but do not pay) one bulk bonus payment and record it in the ledger."""
    total = round(sum(r["amount"] for r in rows), 2)
    largest = max(r["amount"] for r in rows)
    if largest > max_each:
        sys.exit(f"{population}: largest amount ${largest:.2f} exceeds --max-each ${max_each:.2f}.")
    if max_total and total > max_total:
        sys.exit(f"{population}: total ${total:.2f} exceeds --max-total ${max_total:.2f}.")
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
        "requested_total": total,
        "response": {k: created.get(k) for k in ("amount", "fees", "vat", "total_amount")},
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "paid_at": None,
    }
    write_ledger(run_path, ledger)
    return ledger[population]


def cmd_pay(args, token):
    """Set up and pay bonuses and partial pay for a run, then send the explanatory notes.

    Three confirmations, one per irreversible step: set up (charges nothing,
    but reveals Prolific's fee-inclusive total), pay, and message the removed
    players. A ledger under the run directory records each bulk payment id and
    when it was paid, so re-running never pays twice -- the pay endpoint is not
    idempotent.
    """
    study_id = from_session(args, "game_study_id", args.study)
    if not study_id:
        sys.exit("Give --study, or --session NAME.")
    run = args.run or (read_session(args.session).get("run") if args.session else None) or newest_run()
    if not run:
        sys.exit("No run registered in the active dataset. Run analysis/extract_run.py --dataset full first, or pass --run.")
    run_path = run_dir(run)
    if args.session:
        write_session(args.session, run=run)
    print(f"Run:   {run}   (pass --run to choose another)")
    print(f"Study: {study_id}\n")

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
    if not populations:
        sys.exit("Nothing to pay: no positive amounts in bonuses.csv or early_ended.csv.")

    ledger = read_ledger(run_path)
    label = {"bonuses": "finishers", "early": "removed early"}
    for pop, (rows, skipped) in populations.items():
        total = sum(r["amount"] for r in rows)
        entry = ledger.get(pop)
        state = "paid" if entry and entry.get("paid_at") else "set up, not paid" if entry else "not set up"
        print(f"{label[pop]:14s} {len(rows):3d} people  ${total:8.2f}  ({skipped} zero rows skipped)  -- {state}")

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
        if not confirm(f"\nPay ${grand:,.2f} now? This cannot be undone.", args):
            return
        for pop in unpaid:
            api("POST", f"/bulk-bonus-payments/{ledger[pop]['bulk_id']}/pay/", token)
            ledger[pop]["paid_at"] = datetime.now().isoformat(timespec="seconds")
            write_ledger(run_path, ledger)
            print(f"  {label[pop]}: paid")
    else:
        print("\nEverything is already paid.")

    # Phase 3: notes to the removed players.
    if "early" not in populations:
        return
    if ledger.get("notes_sent_at"):
        print(f"\nPartial-payment notes were already sent at {ledger['notes_sent_at']}.")
        return
    rows = populations["early"][0]
    submissions = {s.get("participant_id"): s for s in paged(f"/studies/{study_id}/submissions/", token)}
    actionable = []
    print(f"\nNotes for the {len(rows)} removed players:")
    for row in rows:
        submission = submissions.get(row["id"])
        if not submission:
            print("  one participant has no submission in this study -- skipped")
            continue
        done = submission.get("status") == "RETURNED" or bool(submission.get("return_requested"))
        wording = wording_for(row["exit_reason"], args)
        print(f"  {submission.get('status'):9s} ${row['amount']:6.2f}  {row['exit_reason'] or 'reason not recorded':42s}"
              f" -> {'note only' if done else 'request return + note'} [{wording['name']}]")
        actionable.append((submission, row, wording, not done))
    if not actionable:
        return
    for name in {a[2]["name"] for a in actionable}:
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
    ledger["notes_sent_at"] = datetime.now().isoformat(timespec="seconds")
    write_ledger(run_path, ledger)
    print(f"Sent {len(actionable)} notes.")


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
    p = sub.add_parser("surveys", help="list screening surveys and their ids")
    p.add_argument("--counts", action="store_true", help="also fetch response counts (slower)")
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
    p.add_argument("--blocklist-group", help=f"group id of past players (default: find '{BLOCKLIST_GROUP_NAME}')")
    p.add_argument("--template-survey", help="survey id to copy questions from (default: newest screening survey)")
    p.add_argument("--template-study", help="study id to copy game settings from (default: newest game study)")
    p.add_argument("--study-name", default="Group communication game")
    p.add_argument("--internal-name", help="internal name for the game study draft")
    p.add_argument("--workspace", help="workspace id (default: PROLIFIC_WORKSPACE in .env)")
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
    yes(p)

    p = sub.add_parser("message", help="4. send the reminder to the session group")
    p.add_argument("group_id", nargs="?", help="participant group id (or --session)")
    session(p, "the group, screening study and time")
    p.add_argument("--time", help='substituted for {time} in the template (default: from --session)')
    p.add_argument("--study", help="study id to attach the message to (default: screening study)")
    p.add_argument("--body-file", help=f"template (default {MESSAGES_DIR}/reminder.txt)")
    yes(p)

    p = sub.add_parser("publish", help="5. publish the game study, optionally at a set time")
    p.add_argument("study_id", nargs="?", help="game study id (or --session)")
    session(p, "the game study")
    p.add_argument("--at", help="wait until this 24-hour local time, e.g. 21:00")
    p.add_argument("--allow-open", action="store_true", help="publish even with no allowlist (whole Prolific pool)")
    yes(p)

    p = sub.add_parser("approve", help="6. approve the finishers' submissions")
    p.add_argument("study_id", nargs="?", help="game study id (or --session)")
    session(p, "the game study")
    yes(p)

    p = sub.add_parser("pay", help="7. set up and pay bonuses and partial pay, then send the notes")
    session(p, "the game study and run")
    p.add_argument("--study", help="game study id (default: from --session)")
    p.add_argument("--run", help="run timestamp under data/runs/ (default: newest)")
    p.add_argument("--max-each", type=float, default=30.0, help="refuse any single amount above this")
    p.add_argument("--max-total", type=float, help="refuse if a population's total exceeds this")
    p.add_argument("--reason", help="return reason shown to every removed player (default: by exit reason)")
    p.add_argument("--note-file", help="note template for every removed player (default: by exit reason)")
    yes(p)

    # --- maintenance ---
    p = sub.add_parser("blocklist", help="seed or repair the group of participants who have already played")
    p.add_argument("--name", default=BLOCKLIST_GROUP_NAME)
    p.add_argument("--workspace", help="workspace id (default: PROLIFIC_WORKSPACE in .env)")
    p.add_argument("--from-prolific", action="store_true", help="derive who played from Prolific submissions")
    p.add_argument("--study-name", default="Group communication game")
    p.add_argument("--include-unknown", action="store_true", help="also block submissions with no completion code")
    yes(p)

    args = parser.parse_args()
    token = load_token()
    {
        "sessions": cmd_sessions,
        "surveys": cmd_surveys,
        "studies": cmd_studies,
        "setup": cmd_setup,
        "open": cmd_open,
        "prepare": cmd_prepare,
        "message": cmd_message,
        "publish": cmd_publish,
        "approve": cmd_approve,
        "pay": cmd_pay,
        "blocklist": cmd_blocklist,
    }[args.command](args, token)


if __name__ == "__main__":
    main()
