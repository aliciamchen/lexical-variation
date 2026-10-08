"""Add everyone on blocklist_ids.txt to the participant group the scheduling surveys block.

`make payments` writes data/payments/<dataset>/blocklist_ids.txt: everyone who
has started a game, failed the quiz, or seen the social-first instructions, and
everyone who took part in a pilot session. The scheduling surveys carry a
`participant_group_blocklist` filter on the Prolific participant group named
by GROUP_NAME, and a participant group is live: adding someone makes them
ineligible for every study that blocks the group, including one that is
already published. This command brings the group up to date with the list.

It is the only command in operations/ that writes to Prolific, and the only
write it makes is adding members to that one group. It never removes anyone
(members who are not on the list are reported, so that a mistake cannot
quietly unblock someone), never touches a study, and asks before adding
unless --yes is given; --dry-run only reports.

    uv run python operations/sync_blocklist.py --dataset full [--dry-run | --yes]
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import prolific

GROUP_NAME = "Played the game"
PAYMENTS_DIR = prolific.PROJECT_ROOT / "data" / "payments"
BLOCKLIST_FILE = "blocklist_ids.txt"
# Prolific ids are 24 lowercase hex characters; anything else would be refused.
PROLIFIC_ID = re.compile(r"[0-9a-f]{24}")
# Members are added in chunks so that one request never carries the whole list.
CHUNK = 200


def read_blocklist(path: Path) -> tuple[list[str], list[str]]:
    """The valid Prolific ids in blocklist_ids.txt, and the lines that are not one."""
    if not path.exists():
        sys.exit(f"{path} does not exist; run `make payments DATASET=<name>` first.")
    lines = [line.strip() for line in path.read_text().splitlines() if line.strip()]
    valid = sorted({line for line in lines if PROLIFIC_ID.fullmatch(line)})
    invalid = [line for line in lines if not PROLIFIC_ID.fullmatch(line)]
    return valid, invalid


def plan(blocklist: list[str], members: set[str]) -> tuple[list[str], list[str]]:
    """(ids to add, current members not on the list); the second are reported, never removed."""
    wanted = set(blocklist)
    return sorted(wanted - members), sorted(members - wanted)


def chunks(ids: list[str], size: int = CHUNK) -> list[list[str]]:
    return [ids[i:i + size] for i in range(0, len(ids), size)]


def find_group(token: str, name: str = GROUP_NAME) -> dict:
    """The one active participant group with this name across the user's workspaces."""
    workspaces = prolific.api("GET", "/workspaces/", token) or {}
    workspaces = workspaces.get("results", []) if isinstance(workspaces, dict) else workspaces
    found = []
    for workspace in workspaces:
        groups = prolific.api("GET", "/participant-groups/", token, params={"workspace_id": workspace["id"]}) or {}
        found += [g for g in groups.get("results", []) if g.get("name") == name and not g.get("is_deleted")]
    if len(found) != 1:
        sys.exit(f"Expected exactly one participant group named {name!r}, found {len(found)}. "
                 "Create it on Prolific (Participants > Participant groups) or remove the duplicate.")
    return found[0]


def group_members(token: str, group_id: str) -> set[str]:
    """Every member's id. The endpoint returns the whole group at once; a `next` link is followed if present."""
    members, path = set(), f"/participant-groups/{group_id}/participants/"
    while path:
        page = prolific.api("GET", path, token) or {}
        members |= {m.get("participant_id") for m in page.get("results", []) if m.get("participant_id")}
        nxt = ((page.get("_links") or {}).get("next") or {}).get("href")
        path = nxt.split("/api/v1", 1)[1] if nxt and "/api/v1" in nxt else None
    return members


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--dataset", required=True, help="Dataset whose data/payments/<dataset>/blocklist_ids.txt to sync")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Report what would be added; change nothing")
    mode.add_argument("--yes", action="store_true", help="Add without asking")
    return parser.parse_args(argv)


def main(argv=None) -> None:
    args = parse_args(argv)
    blocklist, invalid = read_blocklist(PAYMENTS_DIR / args.dataset / BLOCKLIST_FILE)
    if invalid:
        print(f"Skipping {len(invalid)} line(s) of {BLOCKLIST_FILE} that are not Prolific ids.")
    token = prolific.load_token()
    group = find_group(token)
    members = group_members(token, group["id"])
    to_add, extra = plan(blocklist, members)
    print(f"Participant group {GROUP_NAME!r} has {len(members)} members; {BLOCKLIST_FILE} lists {len(blocklist)}.")
    print(f"  {len(to_add)} on the list are not yet in the group.")
    if extra:
        print(f"  {len(extra)} member(s) are not on the list. They stay in the group (this command never removes "
              "anyone); remove them on Prolific if they should be eligible again.")
    if not to_add:
        print("Nothing to add.")
        return
    if args.dry_run:
        print("Dry run: nothing was changed.")
        return
    if not args.yes:
        try:
            answer = input(f"Add {len(to_add)} participant(s) to {GROUP_NAME!r}? This takes effect at once on every "
                           "survey that blocks the group. [y/N] ")
        except EOFError:
            # No terminal to answer from, as under Claude Code's `!` prefix.
            print("\nNo answer could be read, so nothing was changed. Rerun with SYNC_ARGS=--yes to add without asking.")
            return
        if answer.strip().lower() not in ("y", "yes"):
            print("Nothing was changed.")
            return
    for part in chunks(to_add):
        prolific.api("POST", f"/participant-groups/{group['id']}/participants/", token,
                     payload={"participant_ids": part})
    after = group_members(token, group["id"])
    missing = set(to_add) - after
    print(f"Added {len(to_add) - len(missing)}; the group now has {len(after)} members.")
    if missing:
        sys.exit(f"{len(missing)} id(s) were sent but are not in the group; Prolific may have refused them.")


if __name__ == "__main__":
    main()
