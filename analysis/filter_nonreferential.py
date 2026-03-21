#!/usr/bin/env python3
"""
LLM-Based Non-Referential Message Filter

Classifies reference game messages as referential (R) or non-referential (NR)
using a Gemini-based classifier. Non-referential messages (e.g., "thanks",
"good job") are filtered before SBERT embedding analysis.

Subcommands:
  sample    - Sample messages for human annotation
  classify  - Classify all messages with LLM
  validate  - Compare LLM labels against human labels
  apply     - Filter messages and rebuild speaker_utterances_filtered.csv
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from google import genai
from google.genai import types
from tqdm import tqdm


CLASSIFICATION_PROMPT = """\
You are classifying messages from a communication game where players describe \
abstract tangram images to each other.

A message is REFERENTIAL (R) if it contains ANY information — even vague or \
indirect — that could help identify or describe the target tangram image. \
When in doubt, classify as R. This includes:
- Visual descriptions, even vague ones ("looks like a person kneeling", \
"this shape is weird", "jumbled picture", "this is a big jumble")
- Labels or names for the tangram ("birdhouse", "the dancer", "diamond")
- Metaphorical or game-related labels ("popular game item", "a board game piece")
- Spatial descriptions ("the one with the triangle on top")
- Confirmatory descriptions ("yes, the one pointing right", "sure diamond!")
- Clarifying descriptions in response to questions ("no, the bigger one")
- Questions that reference visual features ("the one with arms up?")
- References to other players' conventions ("or chess piece I heard one say", \
"or cig i heard another say")
- Typos or misspellings of referential content ("[raying" = "praying")
- Any message containing a tangram label or convention name, even mixed with \
non-referential content

A message is NON-REFERENTIAL (NR) ONLY if it contains absolutely NO information \
that helps identify the target. This is a narrow category:
- Social pleasantries ("thanks", "good job", "nice one", "lol")
- Meta-game comments ("Is the speaker there?", "ready", "Did you see that?")
- Encouragement without content ("get it", "you got this")
- Pure acknowledgments with no tangram reference ("ok", "yes", "right")
- Greetings ("hi", "hello")
- Apologies or off-topic remarks ("sorry", "sorry pc crashed")

Classify each message below. Respond with one line per message in the format:
  N: R
or
  N: NR

where N is the message number.

Messages:
"""


def get_client(project: str | None = None) -> genai.Client:
    """Initialize Gemini client via Vertex AI."""
    if not project:
        project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    if not project:
        try:
            result = subprocess.run(
                ["gcloud", "config", "get-value", "project"],
                capture_output=True, text=True, check=True,
            )
            project = result.stdout.strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
    if not project:
        print("Error: No GCP project. Set GOOGLE_CLOUD_PROJECT or use --project.",
              file=sys.stderr)
        sys.exit(1)

    location = os.environ.get("GOOGLE_CLOUD_LOCATION", "global")
    return genai.Client(vertexai=True, project=project, location=location)


def classify_batch(
    client: genai.Client,
    model_name: str,
    messages: list[str],
) -> list[str]:
    """Classify a batch of messages as R or NR.

    Returns list of labels ('R' or 'NR') aligned with input messages.
    """
    prompt = CLASSIFICATION_PROMPT
    for i, msg in enumerate(messages, 1):
        prompt += f"  {i}: {msg}\n"

    response = client.models.generate_content(
        model=model_name,
        contents=prompt,
        config=types.GenerateContentConfig(temperature=0),
    )
    text = response.text.strip()

    # Parse response lines
    labels = []
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        if "NR" in line.upper():
            labels.append("NR")
        elif "R" in line.upper():
            labels.append("R")

    # Pad if response is short (shouldn't happen, but be safe)
    while len(labels) < len(messages):
        labels.append("R")  # default to referential if unparseable

    return labels[:len(messages)]


# ---------- subcommands ----------


def cmd_sample(args):
    """Sample messages for human annotation."""
    data_dir = Path(args.data_dir)
    messages = pd.read_csv(data_dir / "messages.csv")

    # Only speaker messages (these are what get filtered)
    speaker_msgs = messages[messages["senderRole"] == "speaker"].copy()

    n = min(args.n, len(speaker_msgs))

    # Stratified sample: by block (early vs late) and message length
    speaker_msgs["is_short"] = speaker_msgs["text"].str.split().str.len() <= 3
    speaker_msgs["is_early"] = speaker_msgs["blockNum"] <= 2

    sampled = speaker_msgs.groupby(["is_short", "is_early"], group_keys=False).apply(
        lambda g: g.sample(n=min(len(g), n // 4 + 1), random_state=42),
        include_groups=False,
    ).head(n)

    # Output annotation CSV
    output = sampled[["gameId", "roundId", "senderId", "text", "target", "blockNum"]].copy()
    output["human_label"] = ""  # to be filled manually
    output_path = data_dir / "annotation_sample.csv"
    output.to_csv(output_path, index=False)
    print(f"Saved {len(output)} messages for annotation to {output_path}")
    print("Fill the 'human_label' column with 'R' or 'NR' and save as human_labels.csv")


def cmd_classify(args):
    """Classify all speaker messages with LLM."""
    data_dir = Path(args.data_dir)
    messages = pd.read_csv(data_dir / "messages.csv")
    speaker_msgs = messages[messages["senderRole"] == "speaker"].copy()

    client = get_client(args.project)
    batch_size = args.batch_size

    all_labels = []
    texts = speaker_msgs["text"].tolist()

    for i in tqdm(range(0, len(texts), batch_size), desc="Classifying"):
        batch = texts[i : i + batch_size]
        labels = classify_batch(client, args.model, batch)
        all_labels.extend(labels)

    speaker_msgs["is_referential"] = [l == "R" for l in all_labels]
    speaker_msgs["llm_label"] = all_labels

    # Merge back: add is_referential to full messages df
    messages["is_referential"] = True  # default for listener messages
    messages["llm_label"] = ""
    mask = messages["senderRole"] == "speaker"
    messages.loc[mask, "is_referential"] = speaker_msgs["is_referential"].values
    messages.loc[mask, "llm_label"] = speaker_msgs["llm_label"].values

    output_path = data_dir / "messages_classified.csv"
    messages.to_csv(output_path, index=False)

    n_nr = sum(1 for l in all_labels if l == "NR")
    print(f"Classified {len(all_labels)} speaker messages: "
          f"{len(all_labels) - n_nr} referential, {n_nr} non-referential")
    print(f"Saved to {output_path}")


def cmd_validate(args):
    """Validate LLM classifications against human labels."""
    data_dir = Path(args.data_dir)
    human_labels = pd.read_csv(args.labels)

    classified = pd.read_csv(data_dir / "messages_classified.csv")

    # Merge on shared key columns
    merged = human_labels.merge(
        classified[["gameId", "roundId", "senderId", "text", "llm_label"]],
        on=["gameId", "roundId", "senderId", "text"],
        how="inner",
    )

    if len(merged) == 0:
        print("Error: No matching messages found between human labels and classified data.")
        sys.exit(1)

    # Compute agreement
    agree = (merged["human_label"] == merged["llm_label"]).sum()
    total = len(merged)
    accuracy = agree / total

    print(f"Agreement: {agree}/{total} = {accuracy:.1%}")

    # Confusion matrix
    from collections import Counter
    pairs = list(zip(merged["human_label"], merged["llm_label"]))
    counts = Counter(pairs)
    print(f"\nConfusion matrix (human x LLM):")
    print(f"              LLM_R   LLM_NR")
    print(f"  Human_R:    {counts.get(('R','R'), 0):5d}    {counts.get(('R','NR'), 0):5d}")
    print(f"  Human_NR:   {counts.get(('NR','R'), 0):5d}    {counts.get(('NR','NR'), 0):5d}")

    # Cohen's kappa
    p_o = accuracy
    p_r = sum(merged["human_label"] == "R") / total
    p_l = sum(merged["llm_label"] == "R") / total
    p_e = p_r * p_l + (1 - p_r) * (1 - p_l)
    kappa = (p_o - p_e) / (1 - p_e) if p_e < 1 else 1.0
    print(f"\nCohen's kappa: {kappa:.3f}")

    if accuracy >= 0.95:
        print("\nTarget met (>= 95% agreement).")
    else:
        print(f"\nBelow target. Review disagreements:")
        disagree = merged[merged["human_label"] != merged["llm_label"]]
        for _, row in disagree.iterrows():
            print(f'  "{row["text"]}" — human={row["human_label"]}, llm={row["llm_label"]}')


def cmd_apply(args):
    """Apply filter and produce speaker_utterances_filtered.csv."""
    data_dir = Path(args.data_dir)

    # Use classified messages if available, otherwise classify first
    classified_path = data_dir / "messages_classified.csv"
    if not classified_path.exists():
        print("No messages_classified.csv found. Run 'classify' first.")
        sys.exit(1)

    messages = pd.read_csv(classified_path)
    trials = pd.read_csv(data_dir / "trials.csv")

    # Filter to referential speaker messages only
    speaker_msgs = messages[
        (messages["senderRole"] == "speaker") & (messages["is_referential"] == True)
    ].copy()
    speaker_msgs = speaker_msgs.sort_values(["roundId", "timestamp"])

    # Concatenate per round (same logic as preprocessing.build_speaker_utterances)
    groupby_cols = [
        "gameId", "roundId", "senderId", "blockNum", "phase", "phaseNum", "target",
        "trialNum", "tangramSet",
    ]
    utterances = (
        speaker_msgs.groupby(groupby_cols)
        .agg(utterance=("text", lambda x: ", ".join(x.astype(str))))
        .reset_index()
    )
    utterances["uttLength"] = utterances["utterance"].apply(lambda x: len(x.split()))

    # Handle rounds where ALL speaker messages were non-referential
    # These rounds won't appear in utterances; add them back with empty utterance
    all_speaker = messages[messages["senderRole"] == "speaker"]
    all_rounds = all_speaker.groupby(groupby_cols).size().reset_index(name="_count")
    all_rounds = all_rounds.drop(columns=["_count"])

    utterances = all_rounds.merge(utterances, on=groupby_cols, how="left")
    utterances["utterance"] = utterances["utterance"].fillna("")
    utterances["uttLength"] = utterances["uttLength"].fillna(0).astype(int)

    # Merge speaker trial info (same as preprocessing.py)
    speaker_trials = trials[trials["role"] == "speaker"][
        ["gameId", "playerId", "originalGroup", "currentGroup", "roundId", "repNum"]
    ].drop_duplicates()

    utterances = utterances.merge(
        speaker_trials,
        left_on=["gameId", "roundId", "senderId"],
        right_on=["gameId", "roundId", "playerId"],
        how="left",
    )

    cols = [
        "gameId", "playerId", "originalGroup", "currentGroup", "tangramSet",
        "blockNum", "trialNum", "phase", "phaseNum", "target", "repNum",
        "utterance", "uttLength",
    ]
    existing_cols = [c for c in cols if c in utterances.columns]
    utterances = utterances[existing_cols]

    output_path = data_dir / "speaker_utterances_filtered.csv"
    utterances.to_csv(output_path, index=False)

    # Stats
    original = pd.read_csv(data_dir / "speaker_utterances.csv")
    orig_words = original["uttLength"].sum()
    filt_words = utterances["uttLength"].sum()
    print(f"Original: {orig_words} total words across {len(original)} utterances")
    print(f"Filtered: {filt_words} total words across {len(utterances)} utterances")
    print(f"Removed {orig_words - filt_words} words ({(orig_words - filt_words) / orig_words:.1%})")
    print(f"Saved to {output_path}")


# ---------- main ----------


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="LLM-based non-referential message filter",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # sample
    p_sample = subparsers.add_parser("sample", help="Sample messages for annotation")
    p_sample.add_argument("--data-dir", required=True, help="Path to data directory")
    p_sample.add_argument("--n", type=int, default=200, help="Number of messages to sample")

    # classify
    p_classify = subparsers.add_parser("classify", help="Classify messages with LLM")
    p_classify.add_argument("--data-dir", required=True, help="Path to data directory")
    p_classify.add_argument("--model", default="gemini-2.0-flash", help="Gemini model")
    p_classify.add_argument("--batch-size", type=int, default=30, help="Messages per API call")
    p_classify.add_argument("--project", help="GCP project ID")

    # validate
    p_validate = subparsers.add_parser("validate", help="Validate against human labels")
    p_validate.add_argument("--data-dir", required=True, help="Path to data directory")
    p_validate.add_argument("--labels", required=True, help="Path to human_labels.csv")

    # apply
    p_apply = subparsers.add_parser("apply", help="Apply filter and rebuild utterances")
    p_apply.add_argument("--data-dir", required=True, help="Path to data directory")

    args = parser.parse_args()

    if args.command == "sample":
        cmd_sample(args)
    elif args.command == "classify":
        cmd_classify(args)
    elif args.command == "validate":
        cmd_validate(args)
    elif args.command == "apply":
        cmd_apply(args)


if __name__ == "__main__":
    main()
