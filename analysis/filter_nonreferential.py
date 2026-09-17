#!/usr/bin/env python3
"""
LLM-Based Non-Referential Message Filter

Classifies reference game messages as referential (R) or non-referential (NR)
using a Gemini-based classifier. Non-referential messages (e.g., "thanks",
"good job") are filtered before SBERT embedding analysis.

Subcommands:
  sample    - Sample messages for human annotation (annotation_sample.csv)
  classify  - Label the speaker messages that messages_classified.csv does not
              already hold (that file is the label cache); prints the number of
              messages and the estimated API calls first and asks before
              calling Vertex AI (--yes skips the prompt, --dry-run stops there)
  validate  - Compare the labels with the author's human_labels.csv
  apply     - Join the labels onto the current messages.csv and rebuild
              speaker_utterances_filtered.csv (plus its provenance sidecar)
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import sys
from pathlib import Path

import pandas as pd

from dataset_paths import (
    FILTERED_UTTERANCES_FILE,
    MESSAGES_FILE,
    write_filtered_sidecar,
)
from preprocessing import UTTERANCE_KEY_COLUMNS, assemble_speaker_utterances

# The Gemini model the classifier calls, and the one the committed pilot labels
# were produced with. `classify --model` overrides it for one run; the labels
# it writes carry no model name, so change the constant only together with a
# full re-classification.
MODEL_ID = "gemini-2.0-flash"

# The label cache: messages.csv plus `is_referential` and `llm_label`, keyed
# by MESSAGE_KEY. `classify` reads it to skip messages already labeled and
# rewrites it; `apply` and `validate` read it.
CLASSIFIED_FILE = "messages_classified.csv"

# The Vertex AI client, tqdm, and dotenv are imported inside the functions that
# need them so that the pure data functions (`build_filtered_utterances`) can be
# imported and unit-tested without the API dependencies installed.


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

    from google import genai

    location = os.environ.get("GOOGLE_CLOUD_LOCATION", "global")
    return genai.Client(vertexai=True, project=project, location=location)


class BatchParseError(ValueError):
    """The classifier's response does not label every message exactly once."""


_LABEL_LINE = re.compile(r"^\s*\*{0,2}(\d+)\*{0,2}\s*[:.)\-]\s*\*{0,2}(NR|R)\b", re.IGNORECASE)


def parse_batch_labels(text: str, n_messages: int) -> list[str]:
    """Parse "N: R" / "N: NR" lines into labels ordered by message number.

    Labels are matched to messages by the number the model echoes back, not
    by line position, so a skipped or reordered line cannot shift every later
    label. Any message without exactly one label, or a number outside the
    batch, raises BatchParseError instead of being silently defaulted.
    """
    found: dict[int, str] = {}
    conflicts: list[int] = []
    for line in text.splitlines():
        m = _LABEL_LINE.match(line)
        if not m:
            continue
        idx, label = int(m.group(1)), m.group(2).upper()
        if idx in found and found[idx] != label:
            conflicts.append(idx)
        found[idx] = label
    expected = set(range(1, n_messages + 1))
    missing = sorted(expected - set(found))
    extra = sorted(set(found) - expected)
    if missing or extra or conflicts:
        problems = []
        if missing:
            problems.append(f"no label for message(s) {missing}")
        if extra:
            problems.append(f"labels for numbers outside the batch {extra}")
        if conflicts:
            problems.append(f"conflicting labels for message(s) {sorted(set(conflicts))}")
        raise BatchParseError("; ".join(problems) + f". Response was:\n{text[:2000]}")
    return [found[i] for i in range(1, n_messages + 1)]


def classify_batch(
    client: genai.Client,
    model_name: str,
    messages: list[str],
    retries: int = 1,
) -> list[str]:
    """Classify a batch of messages as R or NR.

    Returns labels aligned with the input messages. A response that does not
    label every message exactly once is retried `retries` times and then
    raised, so a malformed batch can never be padded with defaults.
    """
    from google.genai import types

    prompt = CLASSIFICATION_PROMPT
    for i, msg in enumerate(messages, 1):
        prompt += f"  {i}: {msg}\n"

    last_error: Exception | None = None
    for _attempt in range(retries + 1):
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0),
        )
        try:
            return parse_batch_labels(response.text or "", len(messages))
        except BatchParseError as e:
            last_error = e
    raise BatchParseError(
        f"Batch of {len(messages)} messages could not be parsed after {retries + 1} attempt(s): {last_error}"
    )


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


def cached_labels(messages: pd.DataFrame, classified: pd.DataFrame | None) -> pd.Series:
    """The label each row of `messages` already has in the cache; NaN where none.

    `classified` is a previous messages_classified.csv (or None). Labels are
    looked up by MESSAGE_KEY, normalized the same way `attach_labels` does, so
    a message keeps its label across reprocessing as long as its game, round,
    sender, timestamp, and text are unchanged. The result is aligned with the
    index of `messages`.
    """
    key = message_key_frame(messages)
    if key.duplicated().any():
        raise ValueError(
            f"{int(key.duplicated().sum())} messages share a (gameId, roundId, senderId, "
            "timestamp, text) key; messages.csv should be deduplicated on sender and timestamp"
        )
    if classified is None or classified.empty or "llm_label" not in classified.columns:
        return pd.Series(pd.NA, index=messages.index, dtype="object")
    labels = classified.loc[
        classified["llm_label"].notna() & (classified["llm_label"].astype(str) != ""),
        MESSAGE_KEY + ["llm_label"],
    ].copy()
    labels[MESSAGE_KEY] = message_key_frame(labels)
    labels = labels.drop_duplicates(MESSAGE_KEY)
    joined = key.merge(labels, on=MESSAGE_KEY, how="left")
    return pd.Series(joined["llm_label"].values, index=messages.index, dtype="object")


def classified_frame(messages: pd.DataFrame, labels: pd.Series) -> pd.DataFrame:
    """messages_classified.csv: the current messages.csv plus the labels.

    Rows with a label get `llm_label` and `is_referential` (R → True); every
    other row (listener messages, and speaker messages not yet labeled) is
    marked referential with an empty label, which is what `attach_labels`
    treats as "unlabeled" for speaker rows.
    """
    out = messages.copy()
    out["is_referential"] = True
    out["llm_label"] = ""
    known = labels.notna()
    out.loc[known, "llm_label"] = labels[known].astype(str).values
    out.loc[known, "is_referential"] = labels[known].astype(str).eq("R").values
    return out


def cmd_classify(args):
    """Label the speaker messages that are not already in the cache.

    messages_classified.csv is treated as a cache keyed on the message
    (`cached_labels`), so reprocessing that leaves a message unchanged never
    sends it again: only the speaker messages without a label go to the API.
    The count and the estimated number of calls are printed before any call
    is made, and the run proceeds only with --yes or an interactive yes;
    --dry-run stops after the estimate. Whatever has been labeled is written
    back even if a later batch fails, so an interrupted run resumes from
    where it stopped.
    """
    data_dir = Path(args.data_dir)
    messages = pd.read_csv(data_dir / MESSAGES_FILE)
    classified_path = data_dir / CLASSIFIED_FILE
    classified = pd.read_csv(classified_path) if classified_path.exists() else None

    labels = cached_labels(messages, classified)
    speaker = messages["senderRole"] == "speaker"
    todo = messages.index[speaker & labels.isna()]
    n_cached = int((speaker & labels.notna()).sum())
    n_calls = math.ceil(len(todo) / args.batch_size)

    print(
        f"{int(speaker.sum())} speaker messages in {MESSAGES_FILE}: {n_cached} already labeled "
        f"in {CLASSIFIED_FILE}, {len(todo)} to classify"
    )
    print(
        f"Estimated API calls: {n_calls} ({len(todo)} messages in batches of "
        f"{args.batch_size}) to {args.model} through Vertex AI"
    )
    if args.dry_run:
        print("Dry run: no API calls made and nothing written.")
        return
    if len(todo) == 0:
        classified_frame(messages, labels).to_csv(classified_path, index=False)
        print(f"Nothing to classify; rewrote {classified_path} from the cached labels.")
        return
    if not args.yes:
        if not sys.stdin.isatty():
            print(
                "Error: refusing to call the API without --yes when not running interactively.",
                file=sys.stderr,
            )
            sys.exit(1)
        answer = input(f"Send {len(todo)} messages in {n_calls} API call(s)? [y/N] ")
        if answer.strip().lower() not in ("y", "yes"):
            print("Aborted; nothing written.")
            return

    from tqdm import tqdm

    client = get_client(args.project)
    texts = messages.loc[todo, "text"].fillna("").astype(str).tolist()
    new_labels: list[str] = []
    try:
        for i in tqdm(range(0, len(texts), args.batch_size), desc="Classifying"):
            new_labels.extend(classify_batch(client, args.model, texts[i : i + args.batch_size]))
    finally:
        # Keep every label obtained so far, so a failed batch costs only itself
        # and the next run picks up from the cache.
        labels.loc[todo[: len(new_labels)]] = new_labels
        classified_frame(messages, labels).to_csv(classified_path, index=False)

    n_nr = sum(1 for label in new_labels if label == "NR")
    print(
        f"Classified {len(new_labels)} speaker messages: {len(new_labels) - n_nr} referential, "
        f"{n_nr} non-referential ({n_cached} more came from the cache)"
    )
    print(f"Saved to {classified_path}")


def read_human_labels(path: Path) -> pd.DataFrame:
    """The author's annotations: annotation_sample.csv with human_label filled in.

    Every row must carry R or NR; an empty label means the annotation is not
    finished, and validating against a partial file would overstate agreement.
    """
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Run `sample` to write annotation_sample.csv, fill its "
            "human_label column with R or NR, and save it as human_labels.csv."
        )
    human = pd.read_csv(path, dtype={"human_label": str})
    if "human_label" not in human.columns:
        raise ValueError(f"{path.name} has no human_label column")
    human["human_label"] = human["human_label"].fillna("").str.strip().str.upper()
    empty = human["human_label"] == ""
    if empty.any():
        raise ValueError(
            f"{int(empty.sum())} of {len(human)} rows in {path.name} have no human_label; "
            "annotate every row with R or NR before validating"
        )
    bad = ~human["human_label"].isin(["R", "NR"])
    if bad.any():
        raise ValueError(
            f"{path.name} has labels other than R/NR: {sorted(human.loc[bad, 'human_label'].unique())}"
        )
    return human


def cmd_validate(args):
    """Validate LLM classifications against human labels."""
    data_dir = Path(args.data_dir)
    labels_path = Path(args.labels) if args.labels else data_dir / "human_labels.csv"
    try:
        human_labels = read_human_labels(labels_path)
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    classified_path = data_dir / CLASSIFIED_FILE
    if not classified_path.exists():
        print(f"Error: {classified_path} not found. Run `classify` first.", file=sys.stderr)
        sys.exit(1)
    classified = pd.read_csv(classified_path)

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


def build_filtered_utterances(
    messages: pd.DataFrame, trials: pd.DataFrame
) -> tuple[pd.DataFrame, int]:
    """Rebuild speaker utterances from referential messages only.

    The utterances are assembled by `preprocessing.assemble_speaker_utterances`,
    the same function that builds speaker_utterances.csv, so the filtered file
    differs from it only in the messages that went in. Rounds in which every
    speaker message was classified as non-referential are dropped rather than
    kept as empty utterances: the preregistration treats them like rounds in
    which the speaker sent no message, which never produce an utterance row
    either. Returns the utterances and the number of speaker rounds dropped
    for that reason.
    """
    speaker = messages[messages["senderRole"] == "speaker"]
    referential = speaker[speaker["is_referential"] == True].copy()
    utterances = assemble_speaker_utterances(referential, trials)

    # Rounds where ALL speaker messages were non-referential have no row in
    # `utterances`; count them so the caller can report how many were dropped.
    n_speaker_rounds = speaker.groupby(UTTERANCE_KEY_COLUMNS, dropna=False).ngroups
    n_dropped = n_speaker_rounds - len(utterances)
    return utterances, n_dropped


# The columns that identify one chat message across messages.csv and the
# classifier's cache. `senderId` and `timestamp` alone are what messages.csv is
# deduplicated on; `text` is included so an edited or re-parsed message is never
# matched to a label given to different words.
MESSAGE_KEY = ["gameId", "roundId", "senderId", "timestamp", "text"]


def message_key_frame(df: pd.DataFrame) -> pd.DataFrame:
    """The MESSAGE_KEY columns of `df`, normalized so two CSV round trips agree.

    Read back from CSV, `timestamp` can come out as int or float depending on
    whether the column has a gap, and an empty text as NaN or "". Both would
    make a cached label look uncached, and an uncached message costs an API
    call, so the key is normalized before any lookup.
    """
    key = pd.DataFrame(index=df.index)
    for column in MESSAGE_KEY:
        values = df[column]
        if column == "timestamp":
            key[column] = pd.to_numeric(values, errors="coerce").astype("Int64").astype(str)
        else:
            key[column] = values.fillna("").astype(str)
    return key


def attach_labels(messages: pd.DataFrame, classified: pd.DataFrame) -> pd.DataFrame:
    """Join the classifier's labels onto the current messages.csv.

    `messages_classified.csv` is the classifier's output for whatever
    messages.csv existed when `classify` ran, so it is treated as a lookup
    table keyed on MESSAGE_KEY rather than as the messages themselves: the
    current messages.csv is the source of truth, and every speaker message in
    it must have a label. One without a label means messages.csv has changed
    since classification (a new run, an exclusion, a fixed parser), and the
    caller is told to rerun `classify`, which sends only the unlabeled ones.
    Listener messages are never classified and are marked referential.
    """
    labels = classified.loc[
        classified["llm_label"].notna() & (classified["llm_label"].astype(str) != ""),
        MESSAGE_KEY + ["is_referential", "llm_label"],
    ].copy()
    labels[MESSAGE_KEY] = message_key_frame(labels)
    labels = labels.drop_duplicates(MESSAGE_KEY)

    out = messages.copy()
    key = message_key_frame(out)
    if key.duplicated().any():
        raise ValueError(
            f"{int(key.duplicated().sum())} messages share a (gameId, roundId, senderId, "
            "timestamp, text) key; messages.csv should be deduplicated on sender and timestamp"
        )
    joined = key.merge(labels, on=MESSAGE_KEY, how="left")
    joined.index = out.index

    speaker = out["senderRole"] == "speaker"
    unlabeled = speaker & joined["llm_label"].isna()
    if unlabeled.any():
        raise ValueError(
            f"{int(unlabeled.sum())} of {int(speaker.sum())} speaker messages in "
            f"{MESSAGES_FILE} have no label in messages_classified.csv; messages.csv has "
            "changed since the classifier ran. Rerun `classify` (only the unlabeled "
            "messages are sent) before `apply`."
        )
    out["is_referential"] = True
    out["llm_label"] = ""
    out.loc[speaker, "llm_label"] = joined.loc[speaker, "llm_label"].astype(str).values
    out.loc[speaker, "is_referential"] = joined.loc[speaker, "llm_label"].astype(str).eq("R").values
    return out


def cmd_apply(args):
    """Apply filter and produce speaker_utterances_filtered.csv (plus its sidecar)."""
    data_dir = Path(args.data_dir)

    classified_path = data_dir / "messages_classified.csv"
    if not classified_path.exists():
        print("No messages_classified.csv found. Run 'classify' first.")
        sys.exit(1)

    # The labels are joined onto the *current* messages.csv, so the filtered
    # utterances are always a function of the file the sidecar fingerprints.
    messages = pd.read_csv(data_dir / MESSAGES_FILE)
    classified = pd.read_csv(classified_path)
    try:
        messages = attach_labels(messages, classified)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    trials = pd.read_csv(data_dir / "trials.csv")
    utterances, n_dropped = build_filtered_utterances(messages, trials)

    output_path = data_dir / FILTERED_UTTERANCES_FILE
    utterances.to_csv(output_path, index=False)
    sidecar = write_filtered_sidecar(data_dir)

    # Stats
    original = pd.read_csv(data_dir / "speaker_utterances.csv")
    orig_words = original["uttLength"].sum()
    filt_words = utterances["uttLength"].sum()
    print(f"Original: {orig_words} total words across {len(original)} utterances")
    print(f"Filtered: {filt_words} total words across {len(utterances)} utterances")
    print(f"Dropped {n_dropped} speaker rounds whose messages were all non-referential")
    print(f"Removed {orig_words - filt_words} words ({(orig_words - filt_words) / orig_words:.1%})")
    print(f"Saved to {output_path}")
    print(f"Recorded the source messages.csv fingerprint in {sidecar.name}")


# ---------- main ----------


def main():
    from dotenv import load_dotenv

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
    p_classify = subparsers.add_parser(
        "classify",
        help="Label speaker messages with the LLM (only those not already in messages_classified.csv)",
        description=(
            "Classify the speaker messages of messages.csv as referential or not. "
            f"{CLASSIFIED_FILE} is a label cache: messages already labeled there are not "
            "sent again. The number of messages and the estimated API calls are printed "
            "before anything is sent, and the run needs --yes or an interactive confirmation."
        ),
    )
    p_classify.add_argument("--data-dir", required=True, help="Path to data directory")
    p_classify.add_argument(
        "--model", default=MODEL_ID,
        help=f"Gemini model (default: {MODEL_ID}, which produced the committed pilot labels)",
    )
    p_classify.add_argument("--batch-size", type=int, default=30, help="Messages per API call")
    p_classify.add_argument("--project", help="GCP project ID")
    p_classify.add_argument(
        "--dry-run", action="store_true",
        help="Print how many messages would be sent and the estimated calls, then stop",
    )
    p_classify.add_argument(
        "--yes", "-y", action="store_true",
        help="Make the API calls without asking (required when not running interactively)",
    )

    # validate
    p_validate = subparsers.add_parser(
        "validate",
        help="Compare the LLM labels with the author's annotations (human_labels.csv)",
        description=(
            "Agreement, confusion matrix, and Cohen's kappa between the classifier's labels "
            "and the author's. The author annotates annotation_sample.csv (written by "
            "`sample`) by filling its human_label column with R or NR for every row and "
            "saves it as human_labels.csv in the data directory; a file with empty labels "
            "is refused."
        ),
    )
    p_validate.add_argument("--data-dir", required=True, help="Path to data directory")
    p_validate.add_argument(
        "--labels", default=None,
        help="Path to the annotated file (default: <data-dir>/human_labels.csv)",
    )

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
