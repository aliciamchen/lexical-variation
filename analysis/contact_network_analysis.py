#!/usr/bin/env python3
"""
Contact network analysis for the refer_mixed condition.

Reconstructs who played with whom on each Phase 2 trial,
traces first-contact events, identifies bridge players,
and analyzes label transmission chains.

Usage:
    uv run python analysis/contact_network_analysis.py                          # uses processed_data
    uv run python analysis/contact_network_analysis.py --data-dir analysis/20260225_210047/data
"""

import argparse
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
import warnings
warnings.filterwarnings('ignore')

SCRIPT_DIR = Path(__file__).resolve().parent


def parse_args():
    parser = argparse.ArgumentParser(description="Contact network analysis for refer_mixed condition")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=SCRIPT_DIR / "processed_data",
        help="Path to preprocessed data directory (default: analysis/processed_data)",
    )
    return parser.parse_args()


def build_name_map(trials_df, game_id):
    """Build player ID → display name mapping from Phase 1 trial data."""
    p1 = trials_df[(trials_df["gameId"] == game_id) & (trials_df["phaseNum"] == 1)]
    name_map = {}
    for _, row in p1.drop_duplicates("playerId").iterrows():
        name_map[row["playerId"]] = row["playerName"]
    return name_map


def build_orig_group(trials_df, game_id, name_map):
    """Build display name → original group mapping."""
    t = trials_df[trials_df["gameId"] == game_id]
    orig_group = {}
    for _, row in t.drop_duplicates("playerId").iterrows():
        name = name_map.get(row["playerId"])
        if name:
            orig_group[name] = row["originalGroup"]
    return orig_group


args = parse_args()
DATA_DIR = args.data_dir
RAW_DIR = DATA_DIR.parent / "raw"

# ── Load data ──────────────────────────────────────────────────────────────

trials = pd.read_csv(DATA_DIR / "trials.csv")
messages = pd.read_csv(DATA_DIR / "messages.csv")
speaker_utt = pd.read_csv(DATA_DIR / "speaker_utterances.csv")
players_df = pd.read_csv(DATA_DIR / "players.csv")

# Auto-discover refer_mixed game
games = pd.read_csv(DATA_DIR / "games.csv")
refer_mixed_games = games[games["condition"] == "refer_mixed"]
if len(refer_mixed_games) == 0:
    print("No refer_mixed games found in", DATA_DIR / "games.csv")
    raise SystemExit(1)
GAME_ID = refer_mixed_games["gameId"].iloc[0]
print(f"Using refer_mixed game: {GAME_ID}")

t = trials[trials["gameId"] == GAME_ID].copy()
m = messages[messages["gameId"] == GAME_ID].copy()
su = speaker_utt[speaker_utt["gameId"] == GAME_ID].copy()

# ── Player identity map (built dynamically) ──────────────────────────────

NAME_MAP = build_name_map(trials, GAME_ID)
ORIG_GROUP = build_orig_group(trials, GAME_ID, NAME_MAP)

t["realName"] = t["playerId"].map(NAME_MAP)
su["realName"] = su["playerId"].map(NAME_MAP)

# Map message sender names: In phase 2 they are all "Player", use senderId
# Messages don't have senderId in a clean way, let's map via roundId
m_sender_map = {}
for _, row in m.iterrows():
    sid = row["senderId"]
    if sid in NAME_MAP:
        m_sender_map[sid] = NAME_MAP[sid]
m["realSenderName"] = m["senderId"].map(NAME_MAP)

# ── Tangram names for readability ─────────────────────────────────────────

TANGRAM_NAMES = {
    "page1-129": "T1",
    "page3-121": "T2",
    "page4-157": "T3",
    "page5-64":  "T4",
    "page6-149": "T5",
    "page7-26": "T6",
}

# ══════════════════════════════════════════════════════════════════════════
# SECTION 1: Reconstruct the Contact Network
# ══════════════════════════════════════════════════════════════════════════

print("=" * 100)
print("SECTION 1: FULL CONTACT NETWORK — Phase 2 Trial-by-Trial")
print("=" * 100)

p2 = t[t["phaseNum"] == 2.0].copy()

# Show block-by-block group compositions
for block in sorted(p2["blockNum"].unique()):
    b = p2[p2["blockNum"] == block]
    print(f"\n{'─' * 80}")
    print(f"BLOCK {int(block)} (Phase 2)")
    print(f"{'─' * 80}")

    for grp in sorted(b["currentGroup"].unique()):
        g = b[b["currentGroup"] == grp]
        players_in_grp = g.drop_duplicates("playerId")[["playerId", "realName", "originalGroup"]].sort_values("originalGroup")
        names = players_in_grp["realName"].tolist()
        origs = players_in_grp["originalGroup"].tolist()

        # Composition description
        comp = Counter(origs)
        comp_str = " + ".join(f"{v} from {k}" for k, v in sorted(comp.items()))

        print(f"\n  Current Group {grp}: [{', '.join(names)}] — {comp_str}")

        # Show each trial in this block for this group
        trials_in_block = sorted(g["trialNum"].unique())
        for trial_num in trials_in_block:
            trial_data = g[g["trialNum"] == trial_num]
            target = trial_data["target"].iloc[0]
            target_short = TANGRAM_NAMES.get(target, target)

            speaker_rows = trial_data[trial_data["role"] == "speaker"]
            listener_rows = trial_data[trial_data["role"] == "listener"]

            if len(speaker_rows) > 0:
                speaker_name = speaker_rows["realName"].iloc[0]
                speaker_orig = ORIG_GROUP[speaker_name]
            else:
                speaker_name = "?"
                speaker_orig = "?"

            listener_names = listener_rows["realName"].tolist()
            listener_origs = [ORIG_GROUP[n] for n in listener_names]

            # Get accuracy
            correct_count = listener_rows["clickedCorrect"].sum()
            total_listeners = len(listener_rows)

            # Get the speaker's utterance for this trial
            utt_match = su[(su["realName"] == speaker_name) &
                          (su["blockNum"] == block) &
                          (su["target"] == target) &
                          (su["phaseNum"] == 2.0)]
            utterance = utt_match["utterance"].iloc[0] if len(utt_match) > 0 else "(no utterance found)"

            # Cross-group indicator
            all_origs = [speaker_orig] + listener_origs
            is_cross = len(set(all_origs)) > 1
            cross_marker = " *** CROSS-GROUP" if is_cross else ""

            print(f"    Trial {int(trial_num):3d} | {target_short} | "
                  f"Speaker: {speaker_name}({speaker_orig}) → "
                  f"Listeners: {', '.join(f'{n}({o})' for n, o in zip(listener_names, listener_origs))} | "
                  f"Correct: {int(correct_count)}/{total_listeners}{cross_marker}")
            print(f"             | \"{utterance}\"")


# ══════════════════════════════════════════════════════════════════════════
# SECTION 2: First-Contact Analysis
# ══════════════════════════════════════════════════════════════════════════

print("\n\n" + "=" * 100)
print("SECTION 2: FIRST-CONTACT ANALYSIS")
print("=" * 100)

# For each pair of original groups, find first trial where they co-occur
group_pairs = [("A", "B"), ("A", "C"), ("B", "C")]

# Build block/group roster
block_group_roster = {}
for block in sorted(p2["blockNum"].unique()):
    b = p2[p2["blockNum"] == block]
    for grp in b["currentGroup"].unique():
        g = b[b["currentGroup"] == grp]
        members = g.drop_duplicates("playerId")
        roster = [(row["realName"], ORIG_GROUP[row["realName"]]) for _, row in members.iterrows()]
        block_group_roster[(block, grp)] = roster

for g1, g2 in group_pairs:
    print(f"\n{'─' * 80}")
    print(f"First contact between Original Group {g1} and Original Group {g2}")
    print(f"{'─' * 80}")

    found = False
    for block in sorted(p2["blockNum"].unique()):
        if found:
            break
        b = p2[p2["blockNum"] == block]
        for grp in sorted(b["currentGroup"].unique()):
            g = b[b["currentGroup"] == grp]
            members = g.drop_duplicates("playerId")
            orig_groups_in_grp = set(ORIG_GROUP[row["realName"]] for _, row in members.iterrows())

            if g1 in orig_groups_in_grp and g2 in orig_groups_in_grp:
                # Found first contact!
                names_origs = [(row["realName"], ORIG_GROUP[row["realName"]]) for _, row in members.iterrows()]
                print(f"  Block {int(block)}, Current Group {grp}")
                print(f"  Members: {', '.join(f'{n}({o})' for n, o in names_origs)}")

                # Show all trials in this first-contact block
                trials_in_block = sorted(g["trialNum"].unique())
                for trial_num in trials_in_block:
                    trial_data = g[g["trialNum"] == trial_num]
                    target = trial_data["target"].iloc[0]
                    target_short = TANGRAM_NAMES.get(target, target)

                    speaker_rows = trial_data[trial_data["role"] == "speaker"]
                    listener_rows = trial_data[trial_data["role"] == "listener"]

                    if len(speaker_rows) > 0:
                        speaker_name = speaker_rows["realName"].iloc[0]
                        speaker_orig = ORIG_GROUP[speaker_name]
                    else:
                        speaker_name = "?"
                        speaker_orig = "?"

                    listener_names = listener_rows["realName"].tolist()
                    correct_count = listener_rows["clickedCorrect"].sum()

                    utt_match = su[(su["realName"] == speaker_name) &
                                  (su["blockNum"] == block) &
                                  (su["target"] == target) &
                                  (su["phaseNum"] == 2.0)]
                    utterance = utt_match["utterance"].iloc[0] if len(utt_match) > 0 else "(no utterance)"

                    print(f"    Trial {int(trial_num)} | {target_short} | Speaker: {speaker_name}({speaker_orig}) | "
                          f"Correct: {int(correct_count)}/{len(listener_rows)}")
                    print(f"      \"{utterance}\"")

                found = True
                break

    if not found:
        print("  Never co-occurred in Phase 2!")


# ══════════════════════════════════════════════════════════════════════════
# SECTION 3: Phase 1 Conventions (baseline)
# ══════════════════════════════════════════════════════════════════════════

print("\n\n" + "=" * 100)
print("SECTION 3: PHASE 1 CONVENTIONS (Baseline Labels)")
print("=" * 100)
print("Last Phase 1 utterances for each tangram by each group (the 'convention')")

p1_su = su[su["phaseNum"] == 1.0].copy()

for tangram in sorted(TANGRAM_NAMES.keys()):
    tname = TANGRAM_NAMES[tangram]
    print(f"\n  {tname} ({tangram}):")

    for orig_grp in ["A", "B", "C"]:
        grp_players = [n for n, g in ORIG_GROUP.items() if g == orig_grp and n != "Bavi"]
        # Get last block utterances
        last_block_p1 = p1_su[p1_su["target"] == tangram]
        last_block_p1 = last_block_p1[last_block_p1["playerId"].map(NAME_MAP).isin(grp_players)]

        if len(last_block_p1) > 0:
            # Get the last rep
            last_rep = last_block_p1.sort_values("blockNum", ascending=False)
            # Show last 2 utterances
            for _, row in last_rep.head(2).iterrows():
                name = NAME_MAP[row["playerId"]]
                print(f"    Group {orig_grp} | Block {int(row['blockNum'])} | {name}: \"{row['utterance']}\"")


# ══════════════════════════════════════════════════════════════════════════
# SECTION 4: Bridge Players & Key Spreaders
# ══════════════════════════════════════════════════════════════════════════

print("\n\n" + "=" * 100)
print("SECTION 4: BRIDGE PLAYERS & KEY SPREADERS")
print("=" * 100)

# Count cross-group exposure for each player
print("\n4a. Cross-group exposure frequency")
print("─" * 60)

cross_group_counts = defaultdict(lambda: defaultdict(int))
cross_group_blocks = defaultdict(lambda: defaultdict(list))

for block in sorted(p2["blockNum"].unique()):
    b = p2[p2["blockNum"] == block]
    for grp in b["currentGroup"].unique():
        g = b[b["currentGroup"] == grp]
        members = g.drop_duplicates("playerId")
        names = [row["realName"] for _, row in members.iterrows()]
        origs = [ORIG_GROUP[n] for n in names]

        for i, name in enumerate(names):
            for j, other_name in enumerate(names):
                if i != j:
                    other_orig = origs[j]
                    if other_orig != ORIG_GROUP[name]:
                        cross_group_counts[name][other_orig] += 1
                        if block not in cross_group_blocks[name][other_orig]:
                            cross_group_blocks[name][other_orig].append(block)

for name in sorted(cross_group_counts.keys()):
    orig = ORIG_GROUP[name]
    exposures = cross_group_counts[name]
    total = sum(exposures.values())
    detail = ", ".join(f"Group {g}: {c} blocks ({sorted(cross_group_blocks[name][g])})"
                       for g, c in sorted(exposures.items()))
    print(f"  {name} (orig {orig}): {total} cross-group block-exposures — {detail}")

# Identify bridge players
print("\n4b. Bridge player identification")
print("─" * 60)
print("A 'bridge' is someone who was exposed to Group X, then later carried labels to Group Y.")
print()

# For each player, track their sequence of group exposures
for name in sorted(ORIG_GROUP.keys()):
    if name == "Bavi":
        continue
    orig = ORIG_GROUP[name]
    exposure_seq = []

    for block in sorted(p2["blockNum"].unique()):
        b = p2[p2["blockNum"] == block]
        player_block = b[b["realName"] == name]
        if len(player_block) == 0:
            continue
        cur_grp = player_block["currentGroup"].iloc[0]
        g = b[b["currentGroup"] == cur_grp]
        members = g.drop_duplicates("playerId")
        co_players = [(row["realName"], ORIG_GROUP[row["realName"]]) for _, row in members.iterrows() if row["realName"] != name]
        orig_groups_encountered = set(o for _, o in co_players if o != orig)

        exposure_seq.append((int(block), cur_grp, co_players, orig_groups_encountered))

    print(f"  {name} (orig {orig}) trajectory:")
    for block, cur_grp, co_players, new_groups in exposure_seq:
        co_str = ", ".join(f"{n}({o})" for n, o in co_players)
        new_str = f" [NEW: {', '.join(new_groups)}]" if new_groups else " [same-group only]"
        print(f"    Block {block} → Group {cur_grp}: with {co_str}{new_str}")
    print()


# ══════════════════════════════════════════════════════════════════════════
# SECTION 5: Label Transmission Chains
# ══════════════════════════════════════════════════════════════════════════

print("\n" + "=" * 100)
print("SECTION 5: LABEL TRANSMISSION CHAINS")
print("=" * 100)
print("Tracing how specific labels for each tangram evolved across groups.")
print()

# For each tangram, show the full utterance history across all speakers in Phase 2
for tangram in sorted(TANGRAM_NAMES.keys()):
    tname = TANGRAM_NAMES[tangram]
    print(f"\n{'─' * 80}")
    print(f"Tangram {tname} ({tangram})")
    print(f"{'─' * 80}")

    # Phase 1 last conventions
    p1_last = p1_su[p1_su["target"] == tangram].sort_values("blockNum", ascending=False)
    print("  Phase 1 final conventions:")
    shown_groups = set()
    for _, row in p1_last.iterrows():
        name = NAME_MAP[row["playerId"]]
        grp = ORIG_GROUP[name]
        if grp not in shown_groups:
            print(f"    Group {grp} (Block {int(row['blockNum'])}): {name} said \"{row['utterance']}\"")
            shown_groups.add(grp)

    # Phase 2 utterances in order
    p2_utt = su[(su["target"] == tangram) & (su["phaseNum"] == 2.0)].sort_values("blockNum")
    print(f"\n  Phase 2 evolution:")
    for _, row in p2_utt.iterrows():
        name = NAME_MAP[row["playerId"]]
        orig = ORIG_GROUP[name]
        cur = row["currentGroup"]

        # Who was in this group?
        block = row["blockNum"]
        block_data = p2[(p2["blockNum"] == block) & (p2["currentGroup"] == cur)]
        grp_members = block_data.drop_duplicates("playerId")
        listeners = [r["realName"] for _, r in grp_members.iterrows() if r["realName"] != name]
        listener_origs = [ORIG_GROUP[n] for n in listeners]

        # Was this correct?
        trial_data = block_data[block_data["target"] == tangram]
        listener_trial = trial_data[trial_data["role"] == "listener"]
        correct = int(listener_trial["clickedCorrect"].sum()) if len(listener_trial) > 0 else "?"
        total = len(listener_trial)

        cross = " ***" if any(o != orig for o in listener_origs) else ""
        print(f"    Block {int(block)} | {name}(orig {orig}) → "
              f"[{', '.join(f'{n}({o})' for n, o in zip(listeners, listener_origs))}] | "
              f"Correct: {correct}/{total}{cross}")
        print(f"           \"{row['utterance']}\"")


# ══════════════════════════════════════════════════════════════════════════
# SECTION 6: First-Contact Analysis (Detailed)
# ══════════════════════════════════════════════════════════════════════════

print("\n\n" + "=" * 100)
print("SECTION 6: DETAILED FIRST-CONTACT OUTCOMES")
print("=" * 100)

# For each pair of original groups, track ALL co-occurrences
for g1, g2 in group_pairs:
    print(f"\n{'─' * 80}")
    print(f"All contacts between Original Group {g1} and Original Group {g2}")
    print(f"{'─' * 80}")

    for block in sorted(p2["blockNum"].unique()):
        b = p2[p2["blockNum"] == block]
        for grp in sorted(b["currentGroup"].unique()):
            g = b[b["currentGroup"] == grp]
            members = g.drop_duplicates("playerId")
            member_names = [row["realName"] for _, row in members.iterrows()]
            member_origs = [ORIG_GROUP[n] for n in member_names]

            has_g1 = g1 in member_origs
            has_g2 = g2 in member_origs

            if has_g1 and has_g2:
                g1_members = [n for n in member_names if ORIG_GROUP[n] == g1]
                g2_members = [n for n in member_names if ORIG_GROUP[n] == g2]

                print(f"\n  Block {int(block)}, Group {grp}: "
                      f"[{', '.join(f'{n}({ORIG_GROUP[n]})' for n in member_names)}]")

                # How many trials, who spoke, accuracy
                trials_in_block = sorted(g["trialNum"].unique())
                speaker_counts = defaultdict(int)
                correct_total = 0
                total_trials = 0

                for trial_num in trials_in_block:
                    trial_data = g[g["trialNum"] == trial_num]
                    speaker_rows = trial_data[trial_data["role"] == "speaker"]
                    listener_rows = trial_data[trial_data["role"] == "listener"]

                    if len(speaker_rows) > 0:
                        spk = speaker_rows["realName"].iloc[0]
                        spk_orig = ORIG_GROUP[spk]
                        speaker_counts[f"{spk}({spk_orig})"] += 1
                        correct_total += listener_rows["clickedCorrect"].sum()
                        total_trials += 1

                print(f"    Trials: {len(trials_in_block)}, Accuracy: {int(correct_total)}/{total_trials * (len(member_names)-1)} "
                      f"({correct_total / (total_trials * max(1, len(member_names)-1)):.0%})")
                print(f"    Speaker breakdown: {dict(speaker_counts)}")


# ══════════════════════════════════════════════════════════════════════════
# SECTION 7: Order Effects
# ══════════════════════════════════════════════════════════════════════════

print("\n\n" + "=" * 100)
print("SECTION 7: ORDER EFFECTS — Exposure Sequence vs. Label Adoption")
print("=" * 100)

# For each player, track:
# 1. When they first heard labels from other groups
# 2. Which labels they adopted

print("\n7a. Per-player exposure order and label evolution")
print("─" * 60)

for name in sorted(ORIG_GROUP.keys()):
    if name == "Bavi":
        continue
    orig = ORIG_GROUP[name]

    print(f"\n  {name} (orig Group {orig})")
    print(f"  {'.' * 50}")

    # Phase 1 — their last utterances
    p1_player = p1_su[p1_su["realName"] == name].sort_values(["target", "blockNum"])
    print(f"  Phase 1 final labels:")
    for tangram in sorted(TANGRAM_NAMES.keys()):
        p1_tang = p1_player[p1_player["target"] == tangram].sort_values("blockNum", ascending=False)
        if len(p1_tang) > 0:
            last = p1_tang.iloc[0]
            print(f"    {TANGRAM_NAMES[tangram]}: \"{last['utterance']}\"")

    # Phase 2 — when they spoke, what they said
    p2_player = su[(su["realName"] == name) & (su["phaseNum"] == 2.0)].sort_values(["blockNum", "target"])
    if len(p2_player) > 0:
        print(f"  Phase 2 utterances:")
        for _, row in p2_player.iterrows():
            block = int(row["blockNum"])
            cur = row["currentGroup"]
            tangram = row["target"]

            # Who was listening?
            block_data = p2[(p2["blockNum"] == row["blockNum"]) & (p2["currentGroup"] == cur)]
            members = block_data.drop_duplicates("playerId")
            listeners = [(r["realName"], ORIG_GROUP[r["realName"]]) for _, r in members.iterrows() if r["realName"] != name]
            listener_str = ", ".join(f"{n}({o})" for n, o in listeners)

            print(f"    Block {block} | {TANGRAM_NAMES[tangram]} | to [{listener_str}]: \"{row['utterance']}\"")

    # Phase 2 — when they listened, what they heard
    print(f"  Phase 2 what they heard as listener:")
    for block in sorted(p2["blockNum"].unique()):
        block_data = p2[(p2["blockNum"] == block) & (p2["realName"] == name)]
        if len(block_data) == 0:
            continue

        listener_trials = block_data[block_data["role"] == "listener"]
        for _, lt in listener_trials.iterrows():
            # Find the speaker's utterance
            cur = lt["currentGroup"]
            round_id = lt["roundId"]
            target = lt["target"]

            # Find speaker in same round
            same_round = p2[(p2["roundId"] == round_id) & (p2["role"] == "speaker")]
            if len(same_round) > 0:
                speaker_name = same_round["realName"].iloc[0]
                speaker_orig = ORIG_GROUP[speaker_name]

                utt_match = su[(su["realName"] == speaker_name) &
                              (su["blockNum"] == block) &
                              (su["target"] == target) &
                              (su["phaseNum"] == 2.0)]
                utterance = utt_match["utterance"].iloc[0] if len(utt_match) > 0 else "(no utt)"

                correct = "Y" if lt["clickedCorrect"] else "N"
                cross = " ***" if speaker_orig != orig else ""
                print(f"    Block {int(block)} | {TANGRAM_NAMES.get(target, target)} | "
                      f"heard from {speaker_name}({speaker_orig}): \"{utterance}\" | correct={correct}{cross}")

# Check for cascade moments
print("\n\n7b. Cascade detection — sudden label spread")
print("─" * 60)

# For each tangram, track which label each speaker used per block
for tangram in sorted(TANGRAM_NAMES.keys()):
    tname = TANGRAM_NAMES[tangram]
    tang_utt = su[su["target"] == tangram].sort_values("blockNum")

    # Get all utterances by block
    by_block = defaultdict(list)
    for _, row in tang_utt.iterrows():
        name = NAME_MAP[row["playerId"]]
        orig = ORIG_GROUP[name]
        phase = row["phaseNum"]
        by_block[(row["blockNum"], phase)].append((name, orig, row["utterance"]))

    print(f"\n  {tname} ({tangram}) — All speaker labels over time:")
    for (block, phase), entries in sorted(by_block.items()):
        phase_label = "P1" if phase == 1.0 else "P2"
        for name, orig, utt in entries:
            print(f"    {phase_label} Block {int(block)} | {name}({orig}): \"{utt}\"")


# ══════════════════════════════════════════════════════════════════════════
# SECTION 8: Speaker Role Asymmetry
# ══════════════════════════════════════════════════════════════════════════

print("\n\n" + "=" * 100)
print("SECTION 8: SPEAKER ROLE ASYMMETRY")
print("=" * 100)
print("When cross-group encounters happen, does the speaker's convention win?")
print()

# For cross-group trials in Phase 2:
# Track whether the speaker used their own group's convention or adopted the listener's
# Track accuracy as a proxy for convention compatibility

cross_trials = []
for block in sorted(p2["blockNum"].unique()):
    b = p2[p2["blockNum"] == block]
    for grp in b["currentGroup"].unique():
        g = b[b["currentGroup"] == grp]
        members = g.drop_duplicates("playerId")
        member_origs = set(ORIG_GROUP[row["realName"]] for _, row in members.iterrows())

        if len(member_origs) <= 1:
            continue  # Same-group, skip

        trials_in_grp = sorted(g["trialNum"].unique())
        for trial_num in trials_in_grp:
            trial_data = g[g["trialNum"] == trial_num]
            speaker_rows = trial_data[trial_data["role"] == "speaker"]
            listener_rows = trial_data[trial_data["role"] == "listener"]

            if len(speaker_rows) == 0:
                continue

            spk_name = speaker_rows["realName"].iloc[0]
            spk_orig = ORIG_GROUP[spk_name]
            target = trial_data["target"].iloc[0]

            for _, lr in listener_rows.iterrows():
                lis_name = lr["realName"]
                lis_orig = ORIG_GROUP[lis_name]

                if spk_orig != lis_orig:
                    correct = lr["clickedCorrect"]
                    cross_trials.append({
                        "block": int(block),
                        "trial": int(trial_num),
                        "target": target,
                        "speaker": spk_name,
                        "speaker_orig": spk_orig,
                        "listener": lis_name,
                        "listener_orig": lis_orig,
                        "correct": correct,
                    })

cross_df = pd.DataFrame(cross_trials)
print(f"Total cross-group speaker-listener trials: {len(cross_df)}")
print(f"Overall cross-group accuracy: {cross_df['correct'].mean():.1%}")
print()

# Accuracy by speaker's original group
print("Accuracy when speaker is from each original group:")
for grp in ["A", "B", "C"]:
    subset = cross_df[cross_df["speaker_orig"] == grp]
    if len(subset) > 0:
        print(f"  Speaker from {grp}: {subset['correct'].mean():.1%} ({int(subset['correct'].sum())}/{len(subset)})")

print()
print("Accuracy when listener is from each original group:")
for grp in ["A", "B", "C"]:
    subset = cross_df[cross_df["listener_orig"] == grp]
    if len(subset) > 0:
        print(f"  Listener from {grp}: {subset['correct'].mean():.1%} ({int(subset['correct'].sum())}/{len(subset)})")

print()
print("Accuracy by block (does it improve with more exposure?):")
for block in sorted(cross_df["block"].unique()):
    subset = cross_df[cross_df["block"] == block]
    print(f"  Block {block}: {subset['correct'].mean():.1%} ({int(subset['correct'].sum())}/{len(subset)})")

print()
print("Accuracy by specific cross-group direction:")
for (spk_g, lis_g), subset in cross_df.groupby(["speaker_orig", "listener_orig"]):
    print(f"  {spk_g} speaking → {lis_g} listening: {subset['correct'].mean():.1%} ({int(subset['correct'].sum())}/{len(subset)})")

# All cross-group trials detail
print("\n\nDetailed cross-group trial list:")
print("─" * 100)
for _, row in cross_df.sort_values(["block", "trial"]).iterrows():
    target_short = TANGRAM_NAMES.get(row["target"], row["target"])
    correct_str = "CORRECT" if row["correct"] else "WRONG"

    # Get the utterance
    utt_match = su[(su["realName"] == row["speaker"]) &
                  (su["blockNum"] == row["block"]) &
                  (su["target"] == row["target"]) &
                  (su["phaseNum"] == 2.0)]
    utterance = utt_match["utterance"].iloc[0] if len(utt_match) > 0 else "?"

    print(f"  Block {row['block']} Trial {row['trial']} | {target_short} | "
          f"{row['speaker']}({row['speaker_orig']}) → {row['listener']}({row['listener_orig']}) | "
          f"{correct_str} | \"{utterance}\"")


# ══════════════════════════════════════════════════════════════════════════
# SECTION 9: Group Composition Patterns
# ══════════════════════════════════════════════════════════════════════════

print("\n\n" + "=" * 100)
print("SECTION 9: GROUP COMPOSITION PATTERNS")
print("=" * 100)

composition_counts = defaultdict(int)
composition_accuracy = defaultdict(list)

for block in sorted(p2["blockNum"].unique()):
    b = p2[p2["blockNum"] == block]
    for grp in b["currentGroup"].unique():
        g = b[b["currentGroup"] == grp]
        members = g.drop_duplicates("playerId")
        origs = sorted(ORIG_GROUP[row["realName"]] for _, row in members.iterrows())
        n_members = len(origs)

        comp = Counter(origs)
        if n_members == 3:
            if max(comp.values()) == 3:
                comp_type = "3-from-same"
            elif max(comp.values()) == 2:
                comp_type = "2+1"
            else:
                comp_type = "1+1+1"
        elif n_members == 2:
            if max(comp.values()) == 2:
                comp_type = "2-from-same (pair)"
            else:
                comp_type = "1+1 (pair)"
        else:
            comp_type = f"{n_members}-member"

        composition_counts[comp_type] += 1

        # Get accuracy for this group-block
        listener_trials = g[g["role"] == "listener"]
        if len(listener_trials) > 0:
            acc = listener_trials["clickedCorrect"].mean()
            composition_accuracy[comp_type].append(acc)

print("\nGroup composition frequency (per block):")
for comp_type, count in sorted(composition_counts.items()):
    accs = composition_accuracy[comp_type]
    mean_acc = np.mean(accs) if accs else float('nan')
    print(f"  {comp_type}: {count} group-blocks, mean accuracy = {mean_acc:.1%}")

# Note about Bavi's dropout
print(f"\n  NOTE: Bavi (Group B) was dropped for idleness, leaving 8 players.")
print(f"  This means one group each block has only 2 members instead of 3.")

# Detailed composition per block
print("\n\nDetailed composition by block:")
for block in sorted(p2["blockNum"].unique()):
    b = p2[p2["blockNum"] == block]
    print(f"\n  Block {int(block)}:")
    for grp in sorted(b["currentGroup"].unique()):
        g = b[b["currentGroup"] == grp]
        members = g.drop_duplicates("playerId")
        names = [row["realName"] for _, row in members.iterrows()]
        origs = [ORIG_GROUP[n] for n in names]
        comp = Counter(origs)

        n = len(names)
        if n == 3:
            if max(comp.values()) == 3:
                comp_type = "3-from-same"
            elif max(comp.values()) == 2:
                comp_type = "2+1"
            else:
                comp_type = "1+1+1"
        else:
            same = max(comp.values()) == n
            comp_type = f"{n}-same" if same else f"{'|'.join(str(v) for v in sorted(comp.values(), reverse=True))}"

        listener_trials = g[g["role"] == "listener"]
        acc = listener_trials["clickedCorrect"].mean() if len(listener_trials) > 0 else float('nan')

        print(f"    Group {grp}: [{', '.join(f'{n}({o})' for n, o in zip(names, origs))}] "
              f"— {comp_type} — accuracy {acc:.0%}")


# ══════════════════════════════════════════════════════════════════════════
# SECTION 10: Summary — Convention Convergence
# ══════════════════════════════════════════════════════════════════════════

print("\n\n" + "=" * 100)
print("SECTION 10: SUMMARY — DID CONVENTIONS CONVERGE?")
print("=" * 100)

print("\nFor each tangram, compare Phase 1 final label vs Phase 2 final label per group:")
print()

for tangram in sorted(TANGRAM_NAMES.keys()):
    tname = TANGRAM_NAMES[tangram]
    print(f"\n{tname} ({tangram}):")

    # Phase 1 last utterances per group
    for orig_grp in ["A", "B", "C"]:
        grp_players = [n for n, g in ORIG_GROUP.items() if g == orig_grp and n != "Bavi"]

        # Phase 1 last
        p1_tang = p1_su[(p1_su["target"] == tangram) & (p1_su["realName"].isin(grp_players))]
        p1_last = p1_tang.sort_values("blockNum", ascending=False)
        p1_label = p1_last.iloc[0]["utterance"] if len(p1_last) > 0 else "(never spoke)"
        p1_speaker = NAME_MAP[p1_last.iloc[0]["playerId"]] if len(p1_last) > 0 else "?"

        # Phase 2 last
        p2_tang = su[(su["target"] == tangram) & (su["phaseNum"] == 2.0) & (su["realName"].isin(grp_players))]
        p2_last = p2_tang.sort_values("blockNum", ascending=False)
        p2_label = p2_last.iloc[0]["utterance"] if len(p2_last) > 0 else "(never spoke in P2)"
        p2_speaker = NAME_MAP[p2_last.iloc[0]["playerId"]] if len(p2_last) > 0 else "?"

        print(f"  Group {orig_grp}: P1=\"{p1_label}\" ({p1_speaker}) → P2=\"{p2_label}\" ({p2_speaker})")


# ══════════════════════════════════════════════════════════════════════════
# SECTION 11: Label Reduction / Shortening Analysis
# ══════════════════════════════════════════════════════════════════════════

print("\n\n" + "=" * 100)
print("SECTION 11: UTTERANCE LENGTH OVER TIME")
print("=" * 100)

for tangram in sorted(TANGRAM_NAMES.keys()):
    tname = TANGRAM_NAMES[tangram]
    tang_utt = su[su["target"] == tangram].sort_values(["phaseNum", "blockNum"])

    print(f"\n  {tname}:")
    for _, row in tang_utt.iterrows():
        name = NAME_MAP[row["playerId"]]
        orig = ORIG_GROUP[name]
        phase = "P1" if row["phaseNum"] == 1.0 else "P2"
        print(f"    {phase} Block {int(row['blockNum'])} | {name}({orig}) | "
              f"len={row['uttLength']:3.0f} words | \"{row['utterance']}\"")


print("\n\n" + "=" * 100)
print("ANALYSIS COMPLETE")
print("=" * 100)
