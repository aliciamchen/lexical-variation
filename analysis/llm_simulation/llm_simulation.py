#!/usr/bin/env python3
"""
LLM Reference Game Simulation (Phase 1)

Simulates groups of 3 LLM agents playing the tangram reference game,
matching the structure of the actual experiment. Used as an AI detection
benchmark (see paper, AI detection section).

Adapted from social-differentiation/reference_game.py for 3-player groups
with 16-tangram grids.
"""

import argparse
import concurrent.futures
import json
import os
import random
import re
import subprocess
import sys
import time
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.genai.errors import ClientError, ServerError
import yaml

from tangram_images import load_tangram_pngs

# ---------- constants (mirrors experiment/shared/constants.js) ----------

TANGRAM_SETS = {
    0: ["page7-255", "page9-46", "page5-28", "page7-107", "page3-35", "page-B"],
    1: ["page3-121", "page4-157", "page7-26", "page5-64", "page6-149", "page3-193"],
}
DISTRACTORS = ["page5-63", "page9-7", "page5-142", "page4-15"]
ALL_TANGRAMS = (
    TANGRAM_SETS[0] + TANGRAM_SETS[1] + DISTRACTORS
)  # 16 total

GROUP_SIZE = 3
PHASE_1_BLOCKS = 6
NUM_TANGRAMS = 6  # targets per set

# ---------- default prompts ----------

DEFAULT_PROMPTS = {
    "speaker": {
        "system": (
            "You are playing a communication game with two listeners. "
            "You will see 16 abstract tangram figures numbered 1 through 16. "
            "On each round, you'll be told which image is the TARGET.\n\n"
            "Your goal: Describe the target so both listeners can pick it out. "
            "Be concise but ensure they can identify it.\n\n"
            "IMPORTANT: Each listener sees the SAME images in a DIFFERENT ORDER. "
            "You cannot reference the number — describe visual features.\n\n"
            "Build on shared understanding from previous rounds."
        )
    },
    "listener": {
        "system": (
            "You are playing a communication game. You see 16 abstract tangram "
            "figures numbered 1 through 16. The speaker will describe one (the target).\n\n"
            "IMPORTANT: Everyone sees the same images in a DIFFERENT ORDER. "
            "Use only the description to identify the target.\n\n"
            "Respond with ONLY the number of the image you think is the target."
        )
    },
}


def load_prompts(prompts_path: str | None = None) -> dict:
    """Load prompts from YAML, falling back to defaults."""
    if prompts_path:
        path = Path(prompts_path)
    else:
        path = Path(__file__).parent / "llm_prompts.yaml"
    if path.exists():
        with open(path) as f:
            return yaml.safe_load(f)
    return DEFAULT_PROMPTS


# ---------- data structures ----------


@dataclass
class RoundRecord:
    """One round from the perspective of the whole group."""
    round_num: int
    block_num: int
    target: str
    speaker_id: int
    description: str
    word_count: int
    listener_results: list[dict]  # [{listener_id, selection, correct}]
    accuracy: float  # fraction of listeners correct


@dataclass
class GroupSimulation:
    """Complete simulation of one 3-player group through Phase 1."""
    group_id: str
    tangram_set: int
    target_tangrams: list[str]
    all_tangrams: list[str]
    model: str
    rounds: list[dict]
    summary: dict
    config: dict
    timestamp: str
    status: str = "complete"  # "in_progress" or "complete"
    player_orders: dict | None = None  # {player_id: [tangram_id, ...]}
    block_targets: list | None = None  # [[target_id, ...] per block]


# ---------- prompt builders ----------


def build_speaker_prompt(
    target_label: str,
    game_history: list[dict],
    player_id: int,
    player_labels: dict[str, str],
    prompts: dict,
) -> str:
    """Build the speaker's text prompt with full shared game history.

    All players see all rounds (matching the shared chat in the real game).
    History is shown from this player's perspective (using their image labels).
    """
    system = prompts.get("speaker", {}).get("system", DEFAULT_PROMPTS["speaker"]["system"])
    parts = [system.strip()]

    if game_history:
        lines = []
        for h in game_history:
            # Show every round from this player's perspective
            target_in_my_view = player_labels[h["target"]]
            if h["speaker_id"] == player_id:
                role_prefix = "You described"
            else:
                role_prefix = f"Player {h['speaker_id']} described"
            l_parts = []
            for lr in h["listener_results"]:
                sel = lr["selection"]
                if lr["correct"]:
                    l_parts.append(f"Listener {lr['listener_id']}: image {target_in_my_view} (correct)")
                elif sel != "?" and sel in player_labels:
                    l_parts.append(f"Listener {lr['listener_id']}: image {player_labels[sel]} (wrong)")
                else:
                    l_parts.append(f"Listener {lr['listener_id']}: no valid response (wrong)")
            lines.append(
                f'- {role_prefix} image {target_in_my_view}: '
                f'"{h["description"]}" → {", ".join(l_parts)}'
            )
        parts.append("\n\nGame history:\n" + "\n".join(lines))

    parts.append(f"\n\n---\nTARGET for this round: Image {target_label}")
    parts.append("\nProvide your description (be concise):")
    return "".join(parts)


def build_listener_prompt(
    description: str,
    game_history: list[dict],
    player_id: int,
    player_labels: dict[str, str],
    prompts: dict,
) -> str:
    """Build a listener's text prompt with full shared game history.

    All players see all rounds (matching the shared chat in the real game).
    History is shown from this player's perspective (using their image labels).
    """
    system = prompts.get("listener", {}).get("system", DEFAULT_PROMPTS["listener"]["system"])
    parts = [system.strip()]

    if game_history:
        lines = []
        for h in game_history:
            target_in_my_view = player_labels[h["target"]]
            if h["speaker_id"] == player_id:
                role_prefix = "You described"
            else:
                role_prefix = f"Player {h['speaker_id']} described"
            l_parts = []
            for lr in h["listener_results"]:
                sel = lr["selection"]
                if lr["correct"]:
                    l_parts.append(f"Listener {lr['listener_id']}: image {target_in_my_view} (correct)")
                elif sel != "?" and sel in player_labels:
                    l_parts.append(f"Listener {lr['listener_id']}: image {player_labels[sel]} (wrong)")
                else:
                    l_parts.append(f"Listener {lr['listener_id']}: no valid response (wrong)")
            lines.append(
                f'- {role_prefix} image {target_in_my_view}: '
                f'"{h["description"]}" → {", ".join(l_parts)}'
            )
        parts.append("\n\nGame history:\n" + "\n".join(lines))

    parts.append(f'\n\n---\nSpeaker\'s description: "{description}"')
    parts.append("\nWhich image is it? Reply with ONLY the number (1-16):")
    return "".join(parts)


# ---------- Gemini API ----------


MAX_RETRIES = 5
RETRY_BASE_DELAY = 10  # seconds; doubles each retry
CALL_DELAY = 1.0  # seconds between API calls to avoid rate limits


def call_gemini(
    client: genai.Client,
    model_name: str,
    images_ordered: list[tuple[str, bytes]],
    prompt: str,
    temperature: float | None = None,
    top_p: float | None = None,
) -> str:
    """Call Gemini with labeled images and a text prompt. Retries on transient errors."""
    content = []
    for label, img_bytes in images_ordered:
        content.append(f"[Image {label}]")
        content.append(types.Part.from_bytes(data=img_bytes, mime_type="image/png"))
    content.append(prompt)

    config = None
    if temperature is not None or top_p is not None:
        kwargs = {}
        if temperature is not None:
            kwargs["temperature"] = temperature
        if top_p is not None:
            kwargs["top_p"] = top_p
        config = types.GenerateContentConfig(**kwargs)

    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            time.sleep(CALL_DELAY)
            response = client.models.generate_content(
                model=model_name, contents=content, config=config,
            )
            return response.text.strip()
        except (ServerError, ConnectionError, TimeoutError) as e:
            # Server-side or network errors — always retry
            last_error = e
            delay = RETRY_BASE_DELAY * (2 ** attempt)
            print(f"\n    [{type(e).__name__}, retrying in {delay}s (attempt {attempt + 1}/{MAX_RETRIES})]",
                  flush=True)
            time.sleep(delay)
        except ClientError as e:
            err_str = str(e)
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                last_error = e
                delay = RETRY_BASE_DELAY * (2 ** attempt)
                print(f"\n    [Rate limited, retrying in {delay}s (attempt {attempt + 1}/{MAX_RETRIES})]",
                      flush=True)
                time.sleep(delay)
            else:
                raise
    raise RuntimeError(f"Failed after {MAX_RETRIES} retries: {last_error}")


# ---------- simulation logic ----------


def run_round(
    client: genai.Client,
    model_name: str,
    images: dict[str, bytes],
    target: str,
    speaker_id: int,
    listener_ids: list[int],
    player_orders: dict[int, list[str]],
    game_history: list[dict],
    block_num: int,
    round_num: int,
    prompts: dict,
    temperature: float | None = None,
    top_p: float | None = None,
    verbose: bool = True,
) -> RoundRecord:
    """Run a single round: speaker describes, 2 listeners select.

    player_orders: fixed grid order per player (generated once per game).
    game_history: shared history visible to all players (like the shared chat).
    """
    # --- Build per-player label mappings from their fixed grid orders ---
    def get_labels(pid: int) -> tuple[dict[str, str], dict[str, str]]:
        """Return (tangram_id -> label, label -> tangram_id) for a player."""
        order = player_orders[pid]
        tid_to_label = {tid: str(i + 1) for i, tid in enumerate(order)}
        label_to_tid = {str(i + 1): tid for i, tid in enumerate(order)}
        return tid_to_label, label_to_tid

    def get_images_for_player(pid: int) -> list[tuple[str, bytes]]:
        """Return labeled image list in this player's fixed grid order."""
        order = player_orders[pid]
        return [(str(i + 1), images[tid]) for i, tid in enumerate(order)]

    speaker_labels, _ = get_labels(speaker_id)
    target_label = speaker_labels[target]

    if verbose:
        print(f"  Round {round_num} (block {block_num}): "
              f"Player {speaker_id} describes target (img {target_label} in their view)...",
              end=" ", flush=True)

    speaker_prompt = build_speaker_prompt(
        target_label, game_history, speaker_id, speaker_labels, prompts
    )
    speaker_images = get_images_for_player(speaker_id)
    description = call_gemini(client, model_name, speaker_images, speaker_prompt, temperature, top_p)

    if verbose:
        print(f'"{description}"')

    # --- Listener turns (parallel) ---
    def _listener_call(lid):
        listener_labels, listener_reverse = get_labels(lid)
        listener_prompt = build_listener_prompt(
            description, game_history, lid, listener_labels, prompts
        )
        listener_images = get_images_for_player(lid)
        raw = call_gemini(client, model_name, listener_images, listener_prompt, temperature, top_p)
        return lid, listener_reverse, raw

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(listener_ids)) as pool:
        futures = {pool.submit(_listener_call, lid): lid for lid in listener_ids}
        raw_responses = {}
        for future in concurrent.futures.as_completed(futures):
            lid, listener_reverse, raw = future.result()
            raw_responses[lid] = (listener_reverse, raw)

    listener_results = []
    for lid in listener_ids:
        listener_reverse, raw = raw_responses[lid]

        # Parse selection — must be a number 1-16
        sel_label = "?"
        selection = "?"
        parse_error = None
        match = re.search(r"\b(\d{1,2})\b", raw)
        if match:
            num = int(match.group(1))
            if 1 <= num <= 16:
                sel_label = match.group(1)
                selection = listener_reverse.get(sel_label, "?")
            else:
                parse_error = f"number out of range: {num}"
        else:
            parse_error = f"no number found in response"

        if parse_error and verbose:
            print(f"    WARNING: Listener {lid} parse error ({parse_error}), raw: {raw!r}")

        correct = selection == target

        if verbose:
            result_str = "correct" if correct else f"WRONG (picked {selection})"
            print(f"    Listener {lid}: {result_str}")

        listener_results.append({
            "listener_id": lid,
            "selection": selection,
            "selection_label": sel_label,
            "correct": correct,
            "raw_response": raw,
            "parse_error": parse_error,
        })

    # Append to shared game history (all players will see this)
    game_history.append({
        "round_num": round_num,
        "block_num": block_num,
        "target": target,
        "speaker_id": speaker_id,
        "description": description,
        "listener_results": listener_results,
    })

    word_count = len(description.split())
    accuracy = sum(1 for lr in listener_results if lr["correct"]) / len(listener_results)

    return RoundRecord(
        round_num=round_num,
        block_num=block_num,
        target=target,
        speaker_id=speaker_id,
        description=description,
        word_count=word_count,
        listener_results=listener_results,
        accuracy=accuracy,
    )


def compute_summary(rounds: list[RoundRecord]) -> dict:
    """Compute summary statistics over all rounds."""
    n = len(rounds)
    overall_acc = sum(r.accuracy for r in rounds) / n if n else 0
    overall_words = sum(r.word_count for r in rounds) / n if n else 0

    # Count parse errors across all listener results
    n_parse_errors = 0
    n_listener_trials = 0
    for r in rounds:
        for lr in r.listener_results:
            n_listener_trials += 1
            if lr.get("parse_error"):
                n_parse_errors += 1

    # Per-block stats
    blocks = {}
    for r in rounds:
        blocks.setdefault(r.block_num, []).append(r)

    block_stats = {}
    for bnum in sorted(blocks):
        br = blocks[bnum]
        block_stats[bnum] = {
            "accuracy": round(sum(r.accuracy for r in br) / len(br), 3),
            "avg_word_count": round(sum(r.word_count for r in br) / len(br), 2),
            "n": len(br),
        }

    return {
        "overall": {
            "accuracy": round(overall_acc, 3),
            "avg_word_count": round(overall_words, 2),
            "n": n,
            "parse_errors": n_parse_errors,
            "listener_trials": n_listener_trials,
        },
        "per_block": block_stats,
        "word_count_trajectory": [r.word_count for r in rounds],
    }


def _save_intermediate(
    output_path: str,
    group_id: str,
    tangram_set: int,
    target_tangrams: list[str],
    all_tangram_ids: list[str],
    model_name: str,
    all_rounds: list[RoundRecord],
    num_blocks: int,
    temperature: float | None,
    top_p: float | None,
    player_orders: dict[int, list[str]],
    block_targets: list[list[str]],
    status: str = "in_progress",
) -> None:
    """Write current simulation state to disk."""
    summary = compute_summary(all_rounds) if all_rounds else {"overall": {}, "per_block": {}}
    sim = GroupSimulation(
        group_id=group_id,
        tangram_set=tangram_set,
        target_tangrams=target_tangrams,
        all_tangrams=all_tangram_ids,
        model=model_name,
        rounds=[asdict(r) for r in all_rounds],
        summary=summary,
        config={
            "num_blocks": num_blocks,
            "group_size": GROUP_SIZE,
            "num_tangrams": len(all_tangram_ids),
            "num_targets": len(target_tangrams),
            "temperature": temperature,
            "top_p": top_p,
        },
        timestamp=datetime.now().isoformat(),
        status=status,
        player_orders={str(k): v for k, v in player_orders.items()},
        block_targets=block_targets,
    )
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(asdict(sim), f, indent=2)


def _load_partial(output_path: str) -> dict | None:
    """Load a partial simulation file for resuming, or None if not resumable."""
    path = Path(output_path)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    if data.get("status") != "in_progress":
        return None
    if not data.get("player_orders") or not data.get("block_targets"):
        return None
    return data


def run_group_simulation(
    client: genai.Client,
    model_name: str,
    images: dict[str, bytes],
    tangram_set: int,
    num_blocks: int,
    prompts: dict,
    group_id: str = "G1",
    temperature: float | None = None,
    top_p: float | None = None,
    verbose: bool = True,
    output_path: str | None = None,
) -> GroupSimulation:
    """Run a full Phase 1 simulation for one group of 3 players.

    If output_path is provided, writes intermediate results after each round
    so that partial progress is preserved if the process is interrupted.
    Automatically resumes from a partial file if one exists at output_path.
    """
    target_tangrams = TANGRAM_SETS[tangram_set]
    all_tangram_ids = list(ALL_TANGRAMS)

    # Check for resumable partial results
    partial = _load_partial(output_path) if output_path else None

    if partial:
        # Resume: reload state from partial file
        player_orders = {int(k): v for k, v in partial["player_orders"].items()}
        block_targets = partial["block_targets"]
        all_rounds = [
            RoundRecord(
                round_num=r["round_num"],
                block_num=r["block_num"],
                target=r["target"],
                speaker_id=r["speaker_id"],
                description=r["description"],
                word_count=r["word_count"],
                listener_results=r["listener_results"],
                accuracy=r["accuracy"],
            )
            for r in partial["rounds"]
        ]
        # Reconstruct game_history from completed rounds
        game_history = [
            {
                "round_num": r["round_num"],
                "block_num": r["block_num"],
                "target": r["target"],
                "speaker_id": r["speaker_id"],
                "description": r["description"],
                "listener_results": r["listener_results"],
            }
            for r in partial["rounds"]
        ]
        resume_from = len(all_rounds)
        if verbose:
            print(f"  Resuming from round {resume_from} (loaded {resume_from} completed rounds)")
    else:
        # Fresh start: generate player orders and block target schedules
        player_orders = {}
        for pid in range(GROUP_SIZE):
            order = all_tangram_ids.copy()
            random.shuffle(order)
            player_orders[pid] = order

        block_targets = []
        for _ in range(num_blocks):
            targets = target_tangrams.copy()
            random.shuffle(targets)
            block_targets.append(targets)

        game_history = []
        all_rounds = []
        resume_from = 0

    total_rounds = num_blocks * len(target_tangrams)
    global_round = 0

    for block_num in range(num_blocks):
        speaker_id = block_num % GROUP_SIZE
        listener_ids = [i for i in range(GROUP_SIZE) if i != speaker_id]
        targets = block_targets[block_num]

        if verbose:
            print(f"\n--- Block {block_num} (speaker: player {speaker_id}) ---")

        for target in targets:
            # Skip already-completed rounds when resuming
            if global_round < resume_from:
                global_round += 1
                if verbose:
                    print(f"  Round {global_round - 1}: (already completed, skipping)")
                continue

            result = run_round(
                client=client,
                model_name=model_name,
                images=images,
                target=target,
                speaker_id=speaker_id,
                listener_ids=listener_ids,
                player_orders=player_orders,
                game_history=game_history,
                block_num=block_num,
                round_num=global_round,
                prompts=prompts,
                temperature=temperature,
                top_p=top_p,
                verbose=verbose,
            )
            all_rounds.append(result)
            global_round += 1

            # Save intermediate results after each round
            if output_path:
                _save_intermediate(
                    output_path, group_id, tangram_set, target_tangrams,
                    all_tangram_ids, model_name, all_rounds, num_blocks,
                    temperature, top_p, player_orders, block_targets,
                    status="in_progress",
                )
                if verbose:
                    print(f"    [saved {global_round}/{total_rounds} rounds to {output_path}]")

    summary = compute_summary(all_rounds)

    if verbose:
        print(f"\n{'=' * 40}")
        print(f"SUMMARY for group {group_id}:")
        print(f"  Overall accuracy: {summary['overall']['accuracy']:.1%}")
        print(f"  Overall avg words: {summary['overall']['avg_word_count']:.1f}")
        for bnum, bs in summary["per_block"].items():
            print(f"  Block {bnum}: acc={bs['accuracy']:.1%}, words={bs['avg_word_count']:.1f}")
        if summary["overall"].get("parse_errors", 0) > 0:
            print(f"  Parse errors: {summary['overall']['parse_errors']}/{summary['overall']['listener_trials']} listener trials")

    final = GroupSimulation(
        group_id=group_id,
        tangram_set=tangram_set,
        target_tangrams=target_tangrams,
        all_tangrams=all_tangram_ids,
        model=model_name,
        rounds=[asdict(r) for r in all_rounds],
        summary=summary,
        config={
            "num_blocks": num_blocks,
            "group_size": GROUP_SIZE,
            "num_tangrams": len(all_tangram_ids),
            "num_targets": len(target_tangrams),
            "temperature": temperature,
            "top_p": top_p,
        },
        timestamp=datetime.now().isoformat(),
        status="complete",
        player_orders={str(k): v for k, v in player_orders.items()},
        block_targets=block_targets,
    )

    # Write final complete result
    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(asdict(final), f, indent=2)

    return final


# ---------- CLI ----------


def get_gcp_project() -> str | None:
    """Try to get GCP project from env or gcloud config."""
    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    if project:
        return project
    try:
        result = subprocess.run(
            ["gcloud", "config", "get-value", "project"],
            capture_output=True, text=True, check=True,
        )
        return result.stdout.strip() or None
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Simulate Phase 1 reference game with LLM agents (3-player groups)",
    )
    parser.add_argument(
        "--tangram-set", "-t", type=int, choices=[0, 1], default=0,
        help="Which tangram target set to use (default: 0)",
    )
    parser.add_argument(
        "--blocks", "-b", type=int, default=PHASE_1_BLOCKS,
        help=f"Number of blocks (default: {PHASE_1_BLOCKS})",
    )
    parser.add_argument(
        "--output", "-o", help="Output JSON file path (default: stdout)",
    )
    parser.add_argument(
        "--model", "-m", default="gemini-3.1-pro-preview",
        help="Gemini model (default: gemini-3.1-pro-preview)",
    )
    parser.add_argument(
        "--group-id", "-g", default="G1",
        help="Group identifier (default: G1)",
    )
    parser.add_argument(
        "--project", help="Google Cloud project ID",
    )
    parser.add_argument(
        "--location", default="global",
        help="Google Cloud location (default: global)",
    )
    parser.add_argument(
        "--prompts", "-p", help="Path to prompts YAML file",
    )
    parser.add_argument(
        "--quiet", "-q", action="store_true",
        help="Suppress verbose output",
    )
    parser.add_argument(
        "--seed", type=int, help="Random seed for reproducibility",
    )
    parser.add_argument(
        "--temperature", type=float, default=None,
        help="Generation temperature (default: API default; 0=deterministic, 1=default sampling)",
    )
    parser.add_argument(
        "--top-p", type=float, default=None,
        help="Nucleus sampling top-p (default: API default; 0.95 recommended for tangrams)",
    )

    args = parser.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    # GCP project
    project = args.project or get_gcp_project()
    if not project:
        print("Error: No Google Cloud project. Set GOOGLE_CLOUD_PROJECT, "
              "use --project, or run gcloud config set project.", file=sys.stderr)
        sys.exit(1)

    location = args.location or os.environ.get("GOOGLE_CLOUD_LOCATION", "global")

    # Init client
    client = genai.Client(vertexai=True, project=project, location=location)
    prompts = load_prompts(args.prompts)
    verbose = not args.quiet

    if verbose:
        print(f"LLM Reference Game Simulation (Phase 1)")
        print(f"{'=' * 45}")
        print(f"Project: {project} ({location})")
        print(f"Model: {args.model}")
        print(f"Tangram set: {args.tangram_set}")
        print(f"Blocks: {args.blocks}")
        print(f"Group ID: {args.group_id}")
        if args.seed is not None:
            print(f"Seed: {args.seed}")
        print(f"Temperature: {args.temperature if args.temperature is not None else 'API default'}")
        print(f"Top-p: {args.top_p if args.top_p is not None else 'API default'}")

    # Load tangram images
    if verbose:
        print("\nLoading tangram images...")
    images = load_tangram_pngs(ALL_TANGRAMS)
    if verbose:
        print(f"  Loaded {len(images)} tangrams as PNG")

    # Run simulation
    if verbose:
        print("\nStarting simulation...")

    result = run_group_simulation(
        client=client,
        model_name=args.model,
        images=images,
        tangram_set=args.tangram_set,
        num_blocks=args.blocks,
        prompts=prompts,
        group_id=args.group_id,
        temperature=args.temperature,
        top_p=args.top_p,
        verbose=verbose,
        output_path=args.output,
    )

    # Output (if no output path, print to stdout; file is already written by run_group_simulation)
    if args.output:
        if verbose:
            print(f"\nResults saved to: {args.output}")
    else:
        print(json.dumps(asdict(result), indent=2))


if __name__ == "__main__":
    main()
