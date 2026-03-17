"""
Comprehensive linguistic analysis of label convergence, persistence, and loss
in the refer_mixed condition of the most recent pilot data.

Analyzes how group-specific labels for tangrams evolved in Phase 1 and
competed/converged when groups mixed in Phase 2.

Usage:
    uv run python analysis/label_dynamics_analysis.py                          # uses processed_data
    uv run python analysis/label_dynamics_analysis.py --data-dir analysis/20260225_210047/data
"""

import argparse
from collections import defaultdict
from pathlib import Path
import textwrap

import numpy as np
import pandas as pd
import warnings
warnings.filterwarnings('ignore')

SCRIPT_DIR = Path(__file__).resolve().parent


def parse_args():
    parser = argparse.ArgumentParser(description="Label dynamics analysis for refer_mixed condition")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=SCRIPT_DIR / "processed_data",
        help="Path to preprocessed data directory (default: analysis/processed_data)",
    )
    return parser.parse_args()


args = parse_args()
DATA_DIR = args.data_dir

# ─────────────────────────────────────────────────────────────────
# Load data
# ─────────────────────────────────────────────────────────────────
games = pd.read_csv(DATA_DIR / 'games.csv')
utt = pd.read_csv(DATA_DIR / 'speaker_utterances.csv')
msgs = pd.read_csv(DATA_DIR / 'messages.csv')
trials = pd.read_csv(DATA_DIR / 'trials.csv')

# Filter to refer_mixed game
game_id = games[games['condition'] == 'refer_mixed']['gameId'].values[0]
utt = utt[utt['gameId'] == game_id].copy()
msgs = msgs[msgs['gameId'] == game_id].copy()
trials = trials[trials['gameId'] == game_id].copy()

# Convert numeric columns
for df in [utt, msgs, trials]:
    for col in ['blockNum', 'phaseNum', 'trialNum', 'repNum']:
        if col in df.columns:
            df[col] = df[col].apply(lambda x: int(x) if pd.notna(x) else x)

tangrams = sorted(utt['target'].unique())
groups = ['A', 'B', 'C']

# Build a player lookup: playerId -> (originalGroup, playerName)
player_info = {}
for _, row in trials.drop_duplicates('playerId').iterrows():
    pid = row['playerId']
    # Use the name from Phase 1 (not "Player" from Phase 2)
    name = row['playerName']
    og = row['originalGroup']
    player_info[pid] = (og, name)

# Fix: get real names from Phase 1 trials
p1_names = trials[trials['phaseNum'] == 1][['playerId', 'playerName', 'originalGroup']].drop_duplicates('playerId')
for _, row in p1_names.iterrows():
    player_info[row['playerId']] = (row['originalGroup'], row['playerName'])

# Also get real names from messages (Phase 1)
p1_msg_names = msgs[msgs['phaseNum'] == 1][['senderId', 'senderName', 'group']].drop_duplicates('senderId')
for _, row in p1_msg_names.iterrows():
    if row['senderId'] in player_info:
        player_info[row['senderId']] = (player_info[row['senderId']][0], row['senderName'])
    else:
        player_info[row['senderId']] = (row['group'], row['senderName'])


def wrap(text, width=80, indent='    '):
    """Wrap text for readability."""
    return textwrap.fill(text, width=width, initial_indent=indent, subsequent_indent=indent)


print("=" * 100)
print("LINGUISTIC ANALYSIS: LABEL DYNAMICS IN REFER_MIXED CONDITION")
print("=" * 100)
print(f"\nGame ID: {game_id}")
print(f"Tangrams: {tangrams}")
print(f"Total speaker utterances: {len(utt)}")
print(f"Total messages (incl. listener): {len(msgs)}")
print(f"Total trial rows: {len(trials)}")

# ─────────────────────────────────────────────────────────────────
# SECTION 1: Per-tangram label inventory -- Phase 1 evolution
# ─────────────────────────────────────────────────────────────────
print("\n\n" + "=" * 100)
print("SECTION 1: PER-TANGRAM LABEL INVENTORY — PHASE 1 EVOLUTION")
print("=" * 100)

# Phase 1 blocks: blockNum 0-5 with phaseNum == 1
# Phase 2 blocks: blockNum 0-5 with phaseNum == 2
phase1_utt = utt[utt['phaseNum'] == 1].copy()
phase2_utt = utt[utt['phaseNum'] == 2].copy()

# Store final Phase 1 labels for summary
final_p1_labels = {}  # {tangram: {group: label}}

for tang in tangrams:
    print(f"\n{'─' * 80}")
    print(f"TANGRAM: {tang}")
    print(f"{'─' * 80}")

    final_p1_labels[tang] = {}

    for grp in groups:
        grp_utt = phase1_utt[(phase1_utt['target'] == tang) &
                              (phase1_utt['originalGroup'] == grp)].sort_values('blockNum')

        print(f"\n  Group {grp}:")
        if len(grp_utt) == 0:
            print("    (no utterances)")
            final_p1_labels[tang][grp] = "(none)"
            continue

        for _, row in grp_utt.iterrows():
            speaker_name = player_info.get(row['playerId'], ('?', '?'))[1]
            print(f"    Block {row['blockNum']:>1} | Rep {row.get('repNum', '?'):>1} | "
                  f"{speaker_name:<6} | \"{row['utterance']}\" ({row['uttLength']} words)")

        # Final Phase 1 label = last utterance in Phase 1
        last = grp_utt.iloc[-1]
        final_p1_labels[tang][grp] = last['utterance']
        print(f"    >>> FINAL Phase 1 label: \"{last['utterance']}\"")


# ─────────────────────────────────────────────────────────────────
# SECTION 2: Phase 2 label dynamics
# ─────────────────────────────────────────────────────────────────
print("\n\n" + "=" * 100)
print("SECTION 2: PHASE 2 LABEL DYNAMICS — WHAT HAPPENED WHEN GROUPS MIXED")
print("=" * 100)

# In Phase 2, currentGroup != originalGroup for mixed conditions
# Let's trace what each speaker said, and whether listeners got it right

# Get Phase 2 trials with accuracy info
phase2_trials = trials[(trials['phaseNum'] == 2)].copy()

# Get Phase 2 messages (all, including listener)
phase2_msgs = msgs[msgs['phaseNum'] == 2].copy()

for tang in tangrams:
    print(f"\n{'─' * 80}")
    print(f"TANGRAM: {tang}")
    print(f"{'─' * 80}")

    # Phase 1 labels for reference
    print(f"\n  Phase 1 final labels:")
    for grp in groups:
        print(f"    Group {grp}: \"{final_p1_labels[tang].get(grp, '(none)')}\"")

    # Phase 2 utterances by block
    p2_tang = phase2_utt[phase2_utt['target'] == tang].sort_values('blockNum')

    # Phase 2 messages for this tangram
    p2_tang_msgs = phase2_msgs[phase2_msgs['target'] == tang].sort_values('timestamp')

    # Phase 2 trial outcomes for this tangram
    p2_tang_trials = phase2_trials[phase2_trials['target'] == tang].copy()

    print(f"\n  Phase 2 block-by-block:")

    for block in sorted(p2_tang['blockNum'].unique()):
        block_utt = p2_tang[p2_tang['blockNum'] == block]
        print(f"\n    Block {block}:")

        for _, row in block_utt.iterrows():
            orig_grp = row['originalGroup']
            curr_grp = row['currentGroup']
            speaker_name = player_info.get(row['playerId'], ('?', '?'))[1]

            # Get accuracy for listeners in this round
            round_trials = p2_tang_trials[
                (p2_tang_trials['blockNum'] == block) &
                (p2_tang_trials['role'] == 'listener') &
                (p2_tang_trials['currentGroup'] == curr_grp)
            ]

            correct_count = round_trials['clickedCorrect'].apply(lambda x: x == True or x == 'True').sum()
            total_listeners = len(round_trials)

            # Get all messages for this round
            round_msgs = p2_tang_msgs[
                (p2_tang_msgs['blockNum'] == block) &
                (p2_tang_msgs['group'] == curr_grp)
            ].sort_values('timestamp')

            grp_label = f"(orig {orig_grp}, now in {curr_grp})"
            print(f"      Speaker: {speaker_name} {grp_label}")
            print(f"      Utterance: \"{row['utterance']}\" ({row['uttLength']} words)")
            print(f"      Listener accuracy: {correct_count}/{total_listeners}")

            # Show full message exchange
            if len(round_msgs) > 0:
                print(f"      Full chat exchange:")
                for _, m in round_msgs.iterrows():
                    role_tag = f"[{m['senderRole']}]"
                    m_name = m['senderName']
                    # Get original group of this sender
                    sender_orig = player_info.get(m['senderId'], ('?', '?'))[0]
                    print(f"        {role_tag:<10} {m_name} (orig {sender_orig}): \"{m['text']}\"")
            print()


# ─────────────────────────────────────────────────────────────────
# SECTION 3: Label competition analysis — which labels won?
# ─────────────────────────────────────────────────────────────────
print("\n\n" + "=" * 100)
print("SECTION 3: LABEL COMPETITION — WHICH GROUP'S LABEL WON?")
print("=" * 100)

# For each tangram, look at Phase 2 late blocks (blocks 3-5)
# and see which labels are being used

for tang in tangrams:
    print(f"\n{'─' * 80}")
    print(f"TANGRAM: {tang}")
    print(f"{'─' * 80}")

    print(f"\n  Phase 1 final labels:")
    for grp in groups:
        print(f"    Group {grp}: \"{final_p1_labels[tang].get(grp, '(none)')}\"")

    # Early Phase 2 (blocks 0-2)
    early_p2 = phase2_utt[(phase2_utt['target'] == tang) &
                           (phase2_utt['blockNum'].isin([0, 1, 2]))].sort_values('blockNum')

    # Late Phase 2 (blocks 3-5)
    late_p2 = phase2_utt[(phase2_utt['target'] == tang) &
                          (phase2_utt['blockNum'].isin([3, 4, 5]))].sort_values('blockNum')

    print(f"\n  Early Phase 2 (blocks 0-2) — labels used:")
    for _, row in early_p2.iterrows():
        orig = row['originalGroup']
        curr = row['currentGroup']
        name = player_info.get(row['playerId'], ('?', '?'))[1]
        print(f"    Block {row['blockNum']} | {name} (orig {orig}, in {curr}) | \"{row['utterance']}\"")

    print(f"\n  Late Phase 2 (blocks 3-5) — labels used:")
    for _, row in late_p2.iterrows():
        orig = row['originalGroup']
        curr = row['currentGroup']
        name = player_info.get(row['playerId'], ('?', '?'))[1]
        print(f"    Block {row['blockNum']} | {name} (orig {orig}, in {curr}) | \"{row['utterance']}\"")

    # Determine which labels survived
    # Compare late Phase 2 utterances to Phase 1 final labels
    print(f"\n  ANALYSIS:")
    late_labels = [row['utterance'].lower().strip() for _, row in late_p2.iterrows()]
    late_speakers_orig = [row['originalGroup'] for _, row in late_p2.iterrows()]

    # For each Phase 1 label, check if it appears (or a variant) in late Phase 2
    for grp in groups:
        p1_label = final_p1_labels[tang].get(grp, '').lower().strip()
        if not p1_label or p1_label == '(none)':
            continue
        # Check if any late Phase 2 utterance is similar
        matches = []
        for i, ll in enumerate(late_labels):
            # Check substring match in either direction
            if p1_label in ll or ll in p1_label or \
               any(w in ll for w in p1_label.split() if len(w) > 3):
                matches.append((late_speakers_orig[i], ll))

        if matches:
            adopters = set(m[0] for m in matches)
            if len(adopters) > 1:
                print(f"    Group {grp}'s label \"{p1_label}\" was ADOPTED by speakers from groups: {adopters}")
            elif adopters == {grp}:
                print(f"    Group {grp}'s label \"{p1_label}\" PERSISTED (only used by orig group {grp})")
            else:
                print(f"    Group {grp}'s label \"{p1_label}\" was ADOPTED by {adopters} (not orig group)")
        else:
            print(f"    Group {grp}'s label \"{p1_label}\" was ABANDONED in late Phase 2")


# ─────────────────────────────────────────────────────────────────
# SECTION 4: Properties of winning vs. losing labels
# ─────────────────────────────────────────────────────────────────
print("\n\n" + "=" * 100)
print("SECTION 4: PROPERTIES OF WINNING VS. LOSING LABELS")
print("=" * 100)

# Categorize each tangram's labels
def classify_label_type(label):
    """Classify whether a label is transparent/iconic, metaphorical, or abstract."""
    label_lower = label.lower()

    # Geometric/shape descriptions (transparent)
    geometric_words = ['triangle', 'square', 'rectangle', 'parallelogram', 'rhombus',
                       'shape', 'symmetrical', 'sides', 'corner', 'angle', 'line',
                       'top', 'bottom', 'left', 'right', 'upside down', 'attached']

    # Object metaphors
    metaphor_words = ['looks like', 'shaped like', 'like a', 'like the']
    object_words = ['house', 'boat', 'bed', 'bow tie', 'dress', 'gown', 'car', 'jet',
                    'turtle', 'dog', 'rabbit', 'anchor', 'tapestry', 'hat',
                    'letter', 'capital', 'new york', 'stilts', 'pillow']

    has_geometric = any(w in label_lower for w in geometric_words)
    has_metaphor = any(w in label_lower for w in metaphor_words)
    has_object = any(w in label_lower for w in object_words)

    if has_object and not has_geometric:
        return "metaphorical"
    elif has_geometric and not has_object:
        return "transparent/geometric"
    elif has_geometric and has_object:
        return "mixed (geometric + metaphor)"
    elif len(label.split()) <= 2 and has_object:
        return "conventionalized metaphor"
    else:
        return "descriptive"


def check_convergence(tang, final_labels):
    """Check if multiple groups independently invented similar labels."""
    labels = {g: final_labels[tang].get(g, '').lower().strip() for g in groups}

    # Check pairwise similarity
    convergent_pairs = []
    for i, g1 in enumerate(groups):
        for g2 in groups[i+1:]:
            l1, l2 = labels[g1], labels[g2]
            if not l1 or not l2:
                continue
            # Check for shared key words (> 3 chars)
            words1 = set(w for w in l1.split() if len(w) > 3)
            words2 = set(w for w in l2.split() if len(w) > 3)
            overlap = words1 & words2
            if overlap:
                convergent_pairs.append((g1, g2, overlap))

    return convergent_pairs


# Get Phase 1 frequency counts for each group's label
def get_phase1_frequency(tang, grp):
    """Count how many times a group used its final label (or variants) in Phase 1."""
    grp_utt = phase1_utt[(phase1_utt['target'] == tang) &
                          (phase1_utt['originalGroup'] == grp)]
    return len(grp_utt)


print("\nFor each tangram, analyzing properties of each group's label:\n")

for tang in tangrams:
    print(f"\n{'─' * 80}")
    print(f"TANGRAM: {tang}")
    print(f"{'─' * 80}")

    for grp in groups:
        label = final_p1_labels[tang].get(grp, '(none)')
        if label == '(none)':
            continue

        label_type = classify_label_type(label)
        word_count = len(label.split())
        freq = get_phase1_frequency(tang, grp)

        print(f"\n  Group {grp}: \"{label}\"")
        print(f"    Type: {label_type}")
        print(f"    Length: {word_count} words")
        print(f"    Phase 1 uses by this group: {freq}")

    # Check convergence
    conv = check_convergence(tang, final_p1_labels)
    if conv:
        print(f"\n  CONVERGENCE:")
        for g1, g2, overlap in conv:
            print(f"    Groups {g1} and {g2} share key words: {overlap}")
            print(f"      {g1}: \"{final_p1_labels[tang][g1]}\"")
            print(f"      {g2}: \"{final_p1_labels[tang][g2]}\"")
    else:
        print(f"\n  CONVERGENCE: No shared key words between groups")


# ─────────────────────────────────────────────────────────────────
# SECTION 5: Listener feedback patterns in Phase 2
# ─────────────────────────────────────────────────────────────────
print("\n\n" + "=" * 100)
print("SECTION 5: LISTENER FEEDBACK PATTERNS IN PHASE 2")
print("=" * 100)

listener_msgs = phase2_msgs[phase2_msgs['senderRole'] == 'listener'].copy()

if len(listener_msgs) == 0:
    print("\n  No listener messages found in Phase 2.")
    print("  (Listeners may have only clicked without chatting.)")
else:
    print(f"\n  Found {len(listener_msgs)} listener messages in Phase 2:\n")

    for _, m in listener_msgs.iterrows():
        sender_orig = player_info.get(m['senderId'], ('?', '?'))
        print(f"  Target: {m['target']} | Block {m['blockNum']}")
        print(f"  Listener: {m['senderName']} (orig group {sender_orig[0]}, in group {m['group']})")
        print(f"  Message: \"{m['text']}\"")

        # Classify the message
        text_lower = m['text'].lower()
        if any(w in text_lower for w in ['what', '?', 'which', 'need', 'clue', 'describe']):
            print(f"  Type: CLARIFICATION REQUEST")
        elif any(w in text_lower for w in ['oh', 'got it', 'ok', 'yes', 'yeah']):
            print(f"  Type: CONFIRMATION")
        elif any(w in text_lower for w in ['you mean', 'is it', 'the one']):
            print(f"  Type: OFFERED OWN LABEL")
        else:
            print(f"  Type: OTHER")

        # Show the full exchange for context
        round_msgs = phase2_msgs[
            (phase2_msgs['target'] == m['target']) &
            (phase2_msgs['blockNum'] == m['blockNum']) &
            (phase2_msgs['group'] == m['group'])
        ].sort_values('timestamp')

        print(f"  Full exchange:")
        for _, rm in round_msgs.iterrows():
            s_orig = player_info.get(rm['senderId'], ('?', '?'))
            print(f"    [{rm['senderRole']:<8}] {rm['senderName']} (orig {s_orig[0]}): \"{rm['text']}\"")
        print()

# Also check Phase 2 accuracy patterns tied to label mismatch
print(f"\n  Phase 2 accuracy by whether speaker's label matches listeners' Phase 1 label:")
print(f"  (Proxy: accuracy by block — early blocks should show more errors if labels clash)\n")

phase2_listener_trials = phase2_trials[phase2_trials['role'] == 'listener'].copy()
phase2_listener_trials['correct'] = phase2_listener_trials['clickedCorrect'].apply(
    lambda x: 1 if (x == True or x == 'True') else 0
)

accuracy_by_block = phase2_listener_trials.groupby('blockNum')['correct'].agg(['mean', 'count'])
print(f"  {'Block':>5} | {'Accuracy':>10} | {'N trials':>10}")
print(f"  {'─'*5} | {'─'*10} | {'─'*10}")
for block, row in accuracy_by_block.iterrows():
    print(f"  {block:>5} | {row['mean']:>10.2%} | {int(row['count']):>10}")


# ─────────────────────────────────────────────────────────────────
# SECTION 6: Detailed label competition traces
# ─────────────────────────────────────────────────────────────────
print("\n\n" + "=" * 100)
print("SECTION 6: DETAILED LABEL COMPETITION TRACES")
print("=" * 100)
print("\nFor each tangram, showing every Phase 2 trial with speaker's original group,")
print("current mixed group, utterance, and whether listeners from other groups succeeded.\n")

for tang in tangrams:
    print(f"\n{'─' * 80}")
    print(f"TANGRAM: {tang}")
    print(f"{'─' * 80}")

    # Phase 1 labels
    print(f"  Phase 1 conventionalized labels:")
    for grp in groups:
        print(f"    Group {grp}: \"{final_p1_labels[tang].get(grp, '(none)')}\"")

    # Get all Phase 2 data for this tangram
    p2_utt_tang = phase2_utt[phase2_utt['target'] == tang].sort_values('blockNum')

    print(f"\n  Phase 2 trials:")
    for _, row in p2_utt_tang.iterrows():
        block = row['blockNum']
        orig_grp = row['originalGroup']
        curr_grp = row['currentGroup']
        speaker_name = player_info.get(row['playerId'], ('?', '?'))[1]

        # Get listener outcomes for this specific round
        round_trials = phase2_trials[
            (phase2_trials['target'] == tang) &
            (phase2_trials['blockNum'] == block) &
            (phase2_trials['role'] == 'listener') &
            (phase2_trials['currentGroup'] == curr_grp)
        ]

        listener_results = []
        for _, lt in round_trials.iterrows():
            l_orig = lt['originalGroup']
            l_correct = lt['clickedCorrect'] == True or lt['clickedCorrect'] == 'True'
            l_name = player_info.get(lt['playerId'], ('?', '?'))[1]
            listener_results.append((l_name, l_orig, l_correct, lt.get('clicked', '')))

        # Determine if this is a cross-group interaction
        listener_orig_groups = set(lr[1] for lr in listener_results)
        is_cross_group = any(g != orig_grp for g in listener_orig_groups)

        cross_tag = " [CROSS-GROUP]" if is_cross_group else " [SAME-GROUP]"

        print(f"\n    Block {block}{cross_tag}")
        print(f"    Speaker: {speaker_name} (orig {orig_grp}, playing in {curr_grp})")
        print(f"    Said: \"{row['utterance']}\"")

        for l_name, l_orig, l_correct, l_clicked in listener_results:
            status = "CORRECT" if l_correct else f"WRONG (clicked {l_clicked})"
            same_tag = "(same orig group)" if l_orig == orig_grp else f"(orig group {l_orig})"
            print(f"    Listener: {l_name} {same_tag} → {status}")


# ─────────────────────────────────────────────────────────────────
# SECTION 7: Summary table
# ─────────────────────────────────────────────────────────────────
print("\n\n" + "=" * 100)
print("SECTION 7: SUMMARY TABLE — LABEL FATE PER TANGRAM")
print("=" * 100)

# For each tangram, determine which label won
print(f"\n{'Tang':<14} | {'Grp A P1 Label':<28} | {'Grp B P1 Label':<28} | {'Grp C P1 Label':<28} | {'Late P2 Label(s)':<35} | {'Winner':<8} | {'Why':<40}")
print("─" * 190)

for tang in tangrams:
    a_label = final_p1_labels[tang].get('A', '(none)')
    b_label = final_p1_labels[tang].get('B', '(none)')
    c_label = final_p1_labels[tang].get('C', '(none)')

    # Late Phase 2 labels (blocks 3-5)
    late_p2 = phase2_utt[(phase2_utt['target'] == tang) &
                          (phase2_utt['blockNum'].isin([3, 4, 5]))]

    late_labels = []
    late_speakers = []
    for _, row in late_p2.iterrows():
        late_labels.append(row['utterance'])
        late_speakers.append(row['originalGroup'])

    late_str = "; ".join(f"\"{l}\" ({s})" for l, s in zip(late_labels, late_speakers))
    if not late_str:
        # Try all Phase 2 labels
        all_p2 = phase2_utt[phase2_utt['target'] == tang]
        for _, row in all_p2.iterrows():
            late_labels.append(row['utterance'])
            late_speakers.append(row['originalGroup'])
        late_str = "; ".join(f"\"{l}\" ({s})" for l, s in zip(late_labels, late_speakers))

    # Determine winner
    winner = "unclear"
    why = ""

    # Check which Phase 1 label best matches the late Phase 2 labels
    for grp, p1_label in [('A', a_label), ('B', b_label), ('C', c_label)]:
        if p1_label == '(none)':
            continue
        p1_words = set(w.lower() for w in p1_label.split() if len(w) > 2)
        match_count = 0
        for ll in late_labels:
            ll_words = set(w.lower() for w in ll.split() if len(w) > 2)
            if p1_words & ll_words:
                match_count += 1
        if match_count >= len(late_labels) * 0.5 and len(late_labels) > 0:
            winner = f"Grp {grp}"

    # Check convergence
    conv = check_convergence(tang, final_p1_labels)
    conv_str = ""
    if conv:
        conv_groups = set()
        for g1, g2, overlap in conv:
            conv_groups.add(g1)
            conv_groups.add(g2)
        conv_str = f"convergent ({','.join(sorted(conv_groups))})"

    # Determine why
    label_types = {g: classify_label_type(final_p1_labels[tang].get(g, ''))
                   for g in groups if final_p1_labels[tang].get(g, '') != '(none)'}

    if conv_str:
        why = f"Independent convergence: {conv_str}"
    elif winner != "unclear":
        winning_grp = winner.split()[-1]
        winning_type = label_types.get(winning_grp, '')
        winning_label = final_p1_labels[tang].get(winning_grp, '')
        why = f"{winning_type}, {len(winning_label.split())} words"

    # Truncate for table
    def trunc(s, n):
        return s[:n-2] + ".." if len(s) > n else s

    print(f"{tang:<14} | {trunc(a_label, 28):<28} | {trunc(b_label, 28):<28} | {trunc(c_label, 28):<28} | {trunc(late_str, 35):<35} | {winner:<8} | {trunc(why, 40):<40}")


# ─────────────────────────────────────────────────────────────────
# SECTION 8: Detailed narrative analysis per tangram
# ─────────────────────────────────────────────────────────────────
print("\n\n" + "=" * 100)
print("SECTION 8: NARRATIVE ANALYSIS — THE STORY OF EACH TANGRAM'S LABELS")
print("=" * 100)

for tang in tangrams:
    print(f"\n\n{'━' * 80}")
    print(f"  TANGRAM: {tang}")
    print(f"{'━' * 80}")

    # --- Phase 1 full trajectory ---
    print(f"\n  ╔══ PHASE 1: HOW EACH GROUP'S LABEL EVOLVED ══╗")

    for grp in groups:
        grp_p1 = phase1_utt[(phase1_utt['target'] == tang) &
                             (phase1_utt['originalGroup'] == grp)].sort_values('blockNum')

        print(f"\n  Group {grp} trajectory:")
        if len(grp_p1) == 0:
            print("    (no data)")
            continue

        prev_label = None
        for _, row in grp_p1.iterrows():
            label = row['utterance']
            change = ""
            if prev_label is not None:
                if len(label.split()) < len(prev_label.split()):
                    change = " ← SHORTENED"
                elif label.lower() != prev_label.lower():
                    change = " ← CHANGED"
                else:
                    change = " ← stable"
            prev_label = label
            name = player_info.get(row['playerId'], ('?', '?'))[1]
            print(f"    Block {row['blockNum']}: \"{label}\" (by {name}, {row['uttLength']}w){change}")

    # --- Phase 2 dynamics ---
    print(f"\n  ╔══ PHASE 2: LABEL COMPETITION AND RESOLUTION ══╗")

    p2_tang = phase2_utt[phase2_utt['target'] == tang].sort_values('blockNum')

    if len(p2_tang) == 0:
        print("    (no Phase 2 data)")
        continue

    for _, row in p2_tang.iterrows():
        block = row['blockNum']
        orig = row['originalGroup']
        curr = row['currentGroup']
        name = player_info.get(row['playerId'], ('?', '?'))[1]

        # Get listener results
        round_trials = phase2_trials[
            (phase2_trials['target'] == tang) &
            (phase2_trials['blockNum'] == block) &
            (phase2_trials['role'] == 'listener') &
            (phase2_trials['currentGroup'] == curr)
        ]

        correct = sum(1 for _, lt in round_trials.iterrows()
                      if lt['clickedCorrect'] == True or lt['clickedCorrect'] == 'True')
        total = len(round_trials)

        # Check if any listeners are from different original groups
        listener_groups = []
        for _, lt in round_trials.iterrows():
            l_orig = lt['originalGroup']
            l_correct = lt['clickedCorrect'] == True or lt['clickedCorrect'] == 'True'
            listener_groups.append((l_orig, l_correct))

        cross_results = [(lg, lc) for lg, lc in listener_groups if lg != orig]
        same_results = [(lg, lc) for lg, lc in listener_groups if lg == orig]

        print(f"\n    Block {block}: {name} (orig {orig} → playing in {curr})")
        print(f"    Said: \"{row['utterance']}\"")

        if cross_results:
            cross_correct = sum(1 for _, c in cross_results if c)
            print(f"    Cross-group listeners: {cross_correct}/{len(cross_results)} correct")
        if same_results:
            same_correct = sum(1 for _, c in same_results if c)
            print(f"    Same-group listeners: {same_correct}/{len(same_results)} correct")

        if not correct and total > 0:
            print(f"    *** COMMUNICATION FAILURE — label may not have been understood ***")

    # --- Determine outcome ---
    print(f"\n  ╔══ OUTCOME ══╗")

    # Get late Phase 2 dominant label
    late = phase2_utt[(phase2_utt['target'] == tang) &
                       (phase2_utt['blockNum'] >= 3)]

    if len(late) > 0:
        late_labels = [(row['utterance'], row['originalGroup']) for _, row in late.iterrows()]
        print(f"  Late Phase 2 labels: {late_labels}")

        # Check which P1 label it matches
        for grp in groups:
            p1 = final_p1_labels[tang].get(grp, '').lower()
            matches = sum(1 for ll, _ in late_labels
                         if any(w in ll.lower() for w in p1.split() if len(w) > 3))
            if matches > 0:
                print(f"  → Matches Group {grp}'s Phase 1 label \"{final_p1_labels[tang][grp]}\" ({matches}/{len(late_labels)} late utterances)")
    else:
        print("  (No late Phase 2 data)")


# ─────────────────────────────────────────────────────────────────
# SECTION 9: Cross-group accuracy breakdown
# ─────────────────────────────────────────────────────────────────
print("\n\n" + "=" * 100)
print("SECTION 9: CROSS-GROUP VS SAME-GROUP ACCURACY IN PHASE 2")
print("=" * 100)

# For each trial in Phase 2, determine if listener shares original group with speaker
phase2_speaker_trials = phase2_trials[phase2_trials['role'] == 'speaker'][
    ['target', 'blockNum', 'currentGroup', 'originalGroup', 'playerId']
].rename(columns={'originalGroup': 'speakerOrigGroup', 'playerId': 'speakerId'})

phase2_listener_trials2 = phase2_trials[phase2_trials['role'] == 'listener'].copy()
phase2_listener_trials2 = phase2_listener_trials2.merge(
    phase2_speaker_trials, on=['target', 'blockNum', 'currentGroup'], how='left'
)
phase2_listener_trials2['same_orig_group'] = phase2_listener_trials2['originalGroup'] == phase2_listener_trials2['speakerOrigGroup']
phase2_listener_trials2['correct'] = phase2_listener_trials2['clickedCorrect'].apply(
    lambda x: 1 if (x == True or x == 'True') else 0
)

print(f"\n  Overall accuracy:")
cross = phase2_listener_trials2[~phase2_listener_trials2['same_orig_group']]
same = phase2_listener_trials2[phase2_listener_trials2['same_orig_group']]

print(f"    Same original group:  {same['correct'].mean():.2%} ({same['correct'].sum()}/{len(same)})")
print(f"    Cross-group:          {cross['correct'].mean():.2%} ({cross['correct'].sum()}/{len(cross)})")

print(f"\n  By block:")
print(f"  {'Block':>5} | {'Same-group acc':>15} | {'Cross-group acc':>16} | {'Same N':>7} | {'Cross N':>7}")
print(f"  {'─'*5} | {'─'*15} | {'─'*16} | {'─'*7} | {'─'*7}")

for block in sorted(phase2_listener_trials2['blockNum'].unique()):
    s = same[same['blockNum'] == block]
    c = cross[cross['blockNum'] == block]
    s_acc = f"{s['correct'].mean():.2%}" if len(s) > 0 else "N/A"
    c_acc = f"{c['correct'].mean():.2%}" if len(c) > 0 else "N/A"
    print(f"  {block:>5} | {s_acc:>15} | {c_acc:>16} | {len(s):>7} | {len(c):>7}")

print(f"\n  By tangram:")
print(f"  {'Tangram':<14} | {'Same-group acc':>15} | {'Cross-group acc':>16} | {'Same N':>7} | {'Cross N':>7}")
print(f"  {'─'*14} | {'─'*15} | {'─'*16} | {'─'*7} | {'─'*7}")

for tang in tangrams:
    s = same[same['target'] == tang]
    c = cross[cross['target'] == tang]
    s_acc = f"{s['correct'].mean():.2%}" if len(s) > 0 else "N/A"
    c_acc = f"{c['correct'].mean():.2%}" if len(c) > 0 else "N/A"
    print(f"  {tang:<14} | {s_acc:>15} | {c_acc:>16} | {len(s):>7} | {len(c):>7}")


# ─────────────────────────────────────────────────────────────────
# SECTION 10: Label reduction analysis (shortening over time)
# ─────────────────────────────────────────────────────────────────
print("\n\n" + "=" * 100)
print("SECTION 10: LABEL REDUCTION — SHORTENING TRAJECTORIES")
print("=" * 100)

all_utt = utt.sort_values(['target', 'originalGroup', 'phaseNum', 'blockNum'])

for tang in tangrams:
    print(f"\n  {tang}:")
    for grp in groups:
        grp_utt = all_utt[(all_utt['target'] == tang) &
                           (all_utt['originalGroup'] == grp)].sort_values(['phaseNum', 'blockNum'])
        if len(grp_utt) == 0:
            continue

        lengths = grp_utt['uttLength'].tolist()
        phases = grp_utt['phaseNum'].tolist()
        blocks = grp_utt['blockNum'].tolist()
        labels = grp_utt['utterance'].tolist()

        trajectory = " → ".join(f"{l}w" for l in lengths)
        first_label = labels[0]
        last_label = labels[-1]
        reduction = lengths[0] - lengths[-1]

        print(f"    Group {grp}: {trajectory}")
        print(f"      First: \"{first_label}\" ({lengths[0]}w)")
        print(f"      Last:  \"{last_label}\" ({lengths[-1]}w)")
        print(f"      Reduction: {reduction} words ({reduction/max(lengths[0],1)*100:.0f}%)")


print("\n\n" + "=" * 100)
print("END OF ANALYSIS")
print("=" * 100)
