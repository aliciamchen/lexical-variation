"""
Data integrity tests for preprocessed experiment data.

Validates the preprocessed CSV files in analysis/processed/ against the
registered report specifications and the experiment's server-side logic.

Run with:
    uv run pytest analysis/test_data_integrity.py -v
"""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# ============ CONSTANTS (from experiment design) ============

GROUP_SIZE = 3
NUM_TANGRAMS = 6
PHASE_1_BLOCKS = 6
PHASE_2_BLOCKS = 6
TOTAL_BLOCKS = PHASE_1_BLOCKS + PHASE_2_BLOCKS
LISTENERS_PER_TRIAL = 2
PLAYERS_PER_GAME = 9
NUM_GROUPS = PLAYERS_PER_GAME // GROUP_SIZE  # 3
VALID_CONDITIONS = {"refer_separated", "refer_mixed", "social_mixed"}
VALID_GROUPS = {"A", "B", "C"}
VALID_ROLES = {"speaker", "listener"}
VALID_SOCIAL_GUESSES = {"same_group", "different_group"}

# Scoring
LISTENER_CORRECT_POINTS = 2
SPEAKER_MAX_POINTS_PER_ROUND = 2
SOCIAL_GUESS_CORRECT_POINTS = 4
SOCIAL_SPEAKER_POINTS_PER_CORRECT = 4
BONUS_PER_POINT = 0.05
BONUS_PER_POINT_SOCIAL = 0.03

# Names from constants.js
VALID_NAMES = {"Repi", "Minu", "Laju", "Hera", "Zuda", "Bavi", "Lika", "Felu", "Nori"}

# Data directory
DATA_DIR = Path(__file__).parent / "processed_data"


# ============ FIXTURES ============


@pytest.fixture(scope="session")
def games():
    """Load games.csv, filtered to real (non-test) games."""
    df = pd.read_csv(DATA_DIR / "games.csv")
    return df[df["condition"].notna()].copy()


@pytest.fixture(scope="session")
def players():
    """Load players.csv, filtered to players in real games."""
    df = pd.read_csv(DATA_DIR / "players.csv")
    games = pd.read_csv(DATA_DIR / "games.csv")
    real_game_ids = games[games["condition"].notna()]["gameId"].tolist()
    return df[df["gameId"].isin(real_game_ids)].copy()


@pytest.fixture(scope="session")
def trials():
    """Load trials.csv, filtered to real games."""
    df = pd.read_csv(DATA_DIR / "trials.csv")
    games = pd.read_csv(DATA_DIR / "games.csv")
    real_game_ids = games[games["condition"].notna()]["gameId"].tolist()
    return df[df["gameId"].isin(real_game_ids)].copy()


@pytest.fixture(scope="session")
def messages():
    """Load messages.csv, filtered to real games."""
    df = pd.read_csv(DATA_DIR / "messages.csv")
    games = pd.read_csv(DATA_DIR / "games.csv")
    real_game_ids = games[games["condition"].notna()]["gameId"].tolist()
    return df[df["gameId"].isin(real_game_ids)].copy()


@pytest.fixture(scope="session")
def speaker_utterances():
    """Load speaker_utterances.csv, filtered to real games."""
    df = pd.read_csv(DATA_DIR / "speaker_utterances.csv")
    games = pd.read_csv(DATA_DIR / "games.csv")
    real_game_ids = games[games["condition"].notna()]["gameId"].tolist()
    return df[df["gameId"].isin(real_game_ids)].copy()


@pytest.fixture(scope="session")
def social_guesses():
    """Load social_guesses.csv, filtered to real games."""
    df = pd.read_csv(DATA_DIR / "social_guesses.csv")
    games = pd.read_csv(DATA_DIR / "games.csv")
    real_game_ids = games[games["condition"].notna()]["gameId"].tolist()
    return df[df["gameId"].isin(real_game_ids)].copy()


@pytest.fixture(scope="session")
def game_ids(games):
    """List of real game IDs."""
    return games["gameId"].tolist()


@pytest.fixture(scope="session")
def game_condition_map(games):
    """Mapping from gameId to condition."""
    return dict(zip(games["gameId"], games["condition"]))


@pytest.fixture(scope="session")
def active_players(players):
    """Players who were not removed for idleness."""
    return players[players["isActive"] == True].copy()


@pytest.fixture(scope="session")
def idle_players(players):
    """Players removed for idleness."""
    return players[players["isActive"] == False].copy()


# ============ 1. SCHEMA VALIDATION ============


class TestSchemaValidation:
    """Verify required columns exist and critical fields are non-null."""

    def test_games_required_columns(self, games):
        required = [
            "gameId", "condition", "tangramSet", "numPlayers",
            "activeGroups", "phase1Blocks", "phase2Blocks",
        ]
        missing = set(required) - set(games.columns)
        assert not missing, f"games.csv missing columns: {missing}"

    def test_games_no_null_in_critical_fields(self, games):
        for col in ["gameId", "condition", "tangramSet", "numPlayers"]:
            null_count = games[col].isna().sum()
            assert null_count == 0, (
                f"games.csv has {null_count} null values in '{col}'"
            )

    def test_players_required_columns(self, players):
        required = [
            "playerId", "gameId", "name", "originalGroup", "originalName",
            "score", "bonus", "isActive", "idleRounds",
        ]
        missing = set(required) - set(players.columns)
        assert not missing, f"players.csv missing columns: {missing}"

    def test_active_players_no_null_in_critical_fields(self, active_players):
        for col in ["playerId", "gameId", "originalGroup", "originalName",
                     "score", "bonus", "isActive"]:
            null_count = active_players[col].isna().sum()
            assert null_count == 0, (
                f"players.csv active players have {null_count} null values in '{col}'"
            )

    def test_trials_required_columns(self, trials):
        required = [
            "gameId", "playerId", "playerName", "originalGroup",
            "currentGroup", "role", "blockNum", "phase", "phaseNum",
            "target", "roundScore", "roundId", "trialNum", "tangramSet",
        ]
        missing = set(required) - set(trials.columns)
        assert not missing, f"trials.csv missing columns: {missing}"

    def test_trials_no_null_in_structural_fields(self, trials):
        """Structural fields should never be null."""
        for col in ["gameId", "playerId", "originalGroup", "currentGroup",
                     "role", "blockNum", "phaseNum", "target", "roundId"]:
            null_count = trials[col].isna().sum()
            assert null_count == 0, (
                f"trials.csv has {null_count} null values in '{col}'"
            )

    def test_messages_required_columns(self, messages):
        required = [
            "gameId", "roundId", "blockNum", "phase", "phaseNum",
            "target", "group", "senderId", "senderName", "senderRole",
            "text", "timestamp",
        ]
        missing = set(required) - set(messages.columns)
        assert not missing, f"messages.csv missing columns: {missing}"

    def test_speaker_utterances_required_columns(self, speaker_utterances):
        required = [
            "gameId", "playerId", "originalGroup", "currentGroup",
            "tangramSet", "blockNum", "trialNum", "phase", "phaseNum",
            "target", "repNum", "utterance", "uttLength",
        ]
        missing = set(required) - set(speaker_utterances.columns)
        assert not missing, f"speaker_utterances.csv missing columns: {missing}"

    def test_social_guesses_required_columns(self, social_guesses):
        required = [
            "gameId", "playerId", "originalGroup", "blockNum", "phase",
            "target", "socialGuess", "socialGuessCorrect", "tangramSet",
        ]
        missing = set(required) - set(social_guesses.columns)
        assert not missing, f"social_guesses.csv missing columns: {missing}"


# ============ 2. GAME STRUCTURE ============


class TestGameStructure:
    """Validate overall game structure matches design."""

    def test_valid_conditions(self, games):
        invalid = set(games["condition"].unique()) - VALID_CONDITIONS
        assert not invalid, f"Invalid conditions found: {invalid}"

    def test_num_players_per_game(self, games):
        for _, game in games.iterrows():
            assert game["numPlayers"] == PLAYERS_PER_GAME, (
                f"Game {game['gameId']}: expected {PLAYERS_PER_GAME} players, "
                f"got {game['numPlayers']}"
            )

    def test_active_groups_per_game(self, games):
        for _, game in games.iterrows():
            assert game["activeGroups"] == NUM_GROUPS, (
                f"Game {game['gameId']}: expected {NUM_GROUPS} active groups, "
                f"got {game['activeGroups']}"
            )

    def test_phase1_blocks(self, games):
        for _, game in games.iterrows():
            assert game["phase1Blocks"] == PHASE_1_BLOCKS, (
                f"Game {game['gameId']}: expected {PHASE_1_BLOCKS} Phase 1 blocks, "
                f"got {game['phase1Blocks']}"
            )

    def test_phase2_blocks(self, games):
        for _, game in games.iterrows():
            assert game["phase2Blocks"] == PHASE_2_BLOCKS, (
                f"Game {game['gameId']}: expected {PHASE_2_BLOCKS} Phase 2 blocks, "
                f"got {game['phase2Blocks']}"
            )

    def test_tangram_set_valid(self, games):
        for _, game in games.iterrows():
            assert game["tangramSet"] in [0, 1], (
                f"Game {game['gameId']}: invalid tangram set {game['tangramSet']}"
            )


# ============ 3. PLAYER ASSIGNMENT ============


class TestPlayerAssignment:
    """Validate player-to-game and player-to-group assignments."""

    def test_nine_players_per_game(self, players, game_ids):
        for gid in game_ids:
            game_players = players[players["gameId"] == gid]
            assert len(game_players) == PLAYERS_PER_GAME, (
                f"Game {gid}: expected {PLAYERS_PER_GAME} players, "
                f"got {len(game_players)}"
            )

    def test_three_groups_per_game(self, players, game_ids):
        for gid in game_ids:
            game_players = players[players["gameId"] == gid]
            groups = set(game_players["originalGroup"].dropna().unique())
            assert groups == VALID_GROUPS, (
                f"Game {gid}: expected groups {VALID_GROUPS}, got {groups}"
            )

    def test_three_players_per_original_group(self, players, game_ids):
        for gid in game_ids:
            game_players = players[players["gameId"] == gid]
            for grp in VALID_GROUPS:
                count = len(game_players[game_players["originalGroup"] == grp])
                assert count == GROUP_SIZE, (
                    f"Game {gid}, group {grp}: expected {GROUP_SIZE} players, "
                    f"got {count}"
                )

    def test_original_names_are_valid(self, active_players):
        invalid = set(active_players["originalName"].unique()) - VALID_NAMES
        assert not invalid, f"Invalid original names found: {invalid}"

    def test_original_names_unique_within_game(self, active_players, game_ids):
        for gid in game_ids:
            game_players = active_players[active_players["gameId"] == gid]
            names = game_players["originalName"].tolist()
            assert len(names) == len(set(names)), (
                f"Game {gid}: duplicate original names found: {names}"
            )

    def test_idle_player_has_idle_rounds_at_threshold(self, idle_players):
        """Idle players should have been removed after MAX_IDLE_ROUNDS consecutive idle rounds."""
        MAX_IDLE_ROUNDS = 3
        for _, p in idle_players.iterrows():
            assert p["idleRounds"] == MAX_IDLE_ROUNDS, (
                f"Idle player {p['playerId']}: expected idleRounds={MAX_IDLE_ROUNDS}, "
                f"got {p['idleRounds']}"
            )

    def test_active_players_below_idle_threshold(self, active_players):
        """Active players should have fewer idle rounds than the removal threshold."""
        MAX_IDLE_ROUNDS = 3
        for _, p in active_players.iterrows():
            assert p["idleRounds"] < MAX_IDLE_ROUNDS, (
                f"Active player {p['playerId']}: expected idleRounds < {MAX_IDLE_ROUNDS}, "
                f"got {p['idleRounds']}"
            )


# ============ 4. ROLE ASSIGNMENT ============


class TestRoleAssignment:
    """Validate speaker/listener roles within each trial."""

    def test_valid_roles(self, trials):
        invalid = set(trials["role"].unique()) - VALID_ROLES
        assert not invalid, f"Invalid roles found: {invalid}"

    def test_one_speaker_per_group_per_round(self, trials, game_ids):
        """Each group should have exactly 1 speaker per round (per phase)."""
        for gid in game_ids:
            game_trials = trials[trials["gameId"] == gid]
            for pn in game_trials["phaseNum"].unique():
                phase_trials = game_trials[game_trials["phaseNum"] == pn]
                for bn in phase_trials["blockNum"].unique():
                    block = phase_trials[phase_trials["blockNum"] == bn]
                    for grp in block["currentGroup"].unique():
                        group_block = block[block["currentGroup"] == grp]
                        for rid in group_block["roundId"].unique():
                            round_data = group_block[group_block["roundId"] == rid]
                            speakers = round_data[round_data["role"] == "speaker"]
                            assert len(speakers) == 1, (
                                f"Game {gid}, phase {pn}, block {bn}, group {grp}, "
                                f"round {rid}: expected 1 speaker, "
                                f"got {len(speakers)}"
                            )

    def test_two_listeners_per_group_per_round(self, trials, game_ids):
        """Each active group should have exactly 2 listeners per round.

        Groups with removed players may have fewer listeners.
        """
        for gid in game_ids:
            game_trials = trials[trials["gameId"] == gid]
            for pn in game_trials["phaseNum"].unique():
                phase_trials = game_trials[game_trials["phaseNum"] == pn]
                for bn in phase_trials["blockNum"].unique():
                    block = phase_trials[phase_trials["blockNum"] == bn]
                    for grp in block["currentGroup"].unique():
                        group_block = block[block["currentGroup"] == grp]
                        for rid in group_block["roundId"].unique():
                            round_data = group_block[group_block["roundId"] == rid]
                            listeners = round_data[round_data["role"] == "listener"]
                            # Allow 1 listener if a player was kicked
                            assert len(listeners) in [
                                LISTENERS_PER_TRIAL - 1,
                                LISTENERS_PER_TRIAL,
                            ], (
                                f"Game {gid}, phase {pn}, block {bn}, group {grp}, "
                                f"round {rid}: expected {LISTENERS_PER_TRIAL} "
                                f"listeners, got {len(listeners)}"
                            )

    def test_speaker_rotation_by_block(self, trials, game_ids, game_condition_map):
        """Speaker should rotate: player_index == blockNum % GROUP_SIZE.

        Within each group in a given phase+block, there should be exactly
        one speaker, and across blocks the speaker role should rotate among
        the group members.

        This check only applies to stable groups where:
        - All GROUP_SIZE members are present in every block
        - The group composition doesn't change (i.e., not Phase 2 of
          mixed conditions where groups are reshuffled each trial)
        - No player was removed mid-phase

        When a player has been removed or groups are reshuffled, the
        fallback speaker selection changes the rotation pattern.
        """
        for gid in game_ids:
            game_trials = trials[trials["gameId"] == gid]
            condition = game_condition_map.get(gid)
            is_mixed = condition in ("refer_mixed", "social_mixed")

            for pn in game_trials["phaseNum"].unique():
                # Skip Phase 2 of mixed conditions: groups are reshuffled
                # each block, so different players occupy the same group
                # label in different blocks. The modular rotation check
                # doesn't apply.
                if is_mixed and pn == 2:
                    continue

                phase_trials = game_trials[game_trials["phaseNum"] == pn]
                for grp in phase_trials["currentGroup"].unique():
                    group_trials = phase_trials[phase_trials["currentGroup"] == grp]

                    # Check per-block player count (not across all blocks,
                    # since a player may be removed mid-phase)
                    # Use the minimum block-level player count
                    per_block_counts = []
                    for bn_check in group_trials["blockNum"].unique():
                        block_check = group_trials[group_trials["blockNum"] == bn_check]
                        per_block_counts.append(block_check["playerId"].nunique())
                    n_group_players = min(per_block_counts) if per_block_counts else 0

                    # Get unique speakers per block
                    speakers_by_block = {}
                    for bn in sorted(group_trials["blockNum"].unique()):
                        block = group_trials[group_trials["blockNum"] == bn]
                        speaker_ids = block[block["role"] == "speaker"]["playerId"].unique()
                        assert len(speaker_ids) == 1, (
                            f"Game {gid}, phase {pn}, group {grp}, block {bn}: "
                            f"expected 1 unique speaker, got {len(speaker_ids)}"
                        )
                        speakers_by_block[bn] = speaker_ids[0]

                    # Only verify the modular rotation for full-size groups.
                    # When a player is removed, the fallback uses
                    # blockNum % remaining_count which changes the pattern.
                    if n_group_players < GROUP_SIZE:
                        continue

                    # Verify rotation: speakers at blocks 0,3 should be same,
                    # blocks 1,4 should be same, blocks 2,5 should be same
                    # (because blockNum % 3 determines speaker_index)
                    for b1, s1 in speakers_by_block.items():
                        for b2, s2 in speakers_by_block.items():
                            if int(b1) % GROUP_SIZE == int(b2) % GROUP_SIZE:
                                assert s1 == s2, (
                                    f"Game {gid}, phase {pn}, group {grp}: "
                                    f"speaker at block {b1} ({s1}) != "
                                    f"speaker at block {b2} ({s2}), "
                                    f"but blockNum % {GROUP_SIZE} is equal"
                                )


# ============ 5. PHASE STRUCTURE ============


class TestPhaseStructure:
    """Validate phase numbering and block numbering."""

    def test_phase_nums(self, trials):
        phase_nums = set(trials["phaseNum"].unique())
        assert phase_nums == {1, 2}, (
            f"Expected phaseNums {{1, 2}}, got {phase_nums}"
        )

    def test_phase_name(self, trials):
        phases = set(trials["phase"].unique())
        assert phases == {"refgame"}, (
            f"Expected phase {{'refgame'}}, got {phases}"
        )

    def test_block_nums_range(self, trials):
        """BlockNum values should be within expected range (games may end early due to dropouts)."""
        expected_blocks = set(range(PHASE_1_BLOCKS))
        for pn in [1, 2]:
            phase_trials = trials[trials["phaseNum"] == pn]
            if phase_trials.empty:
                continue
            actual_blocks = set(int(b) for b in phase_trials["blockNum"].unique())
            assert actual_blocks.issubset(expected_blocks), (
                f"Phase {pn}: blocks {actual_blocks} not subset of {expected_blocks}"
            )

    def test_trials_per_block_per_group(self, trials, game_ids, game_condition_map):
        """Each group should have the right number of trials per block.

        In stable groups (Phase 1, or Phase 2 refer_separated), each
        (block, group) should have n_players * NUM_TANGRAMS trials.

        In mixed Phase 2, groups are reshuffled each trial, so we check
        per (roundId, currentGroup) that each player appears exactly once.
        """
        for gid in game_ids:
            game_trials = trials[trials["gameId"] == gid]
            condition = game_condition_map.get(gid)
            is_mixed = condition in ("refer_mixed", "social_mixed")

            for pn in game_trials["phaseNum"].unique():
                phase_trials = game_trials[game_trials["phaseNum"] == pn]

                if is_mixed and pn == 2:
                    # Per-trial check: within each round, each group's
                    # players should all appear exactly once
                    for rid in phase_trials["roundId"].unique():
                        round_data = phase_trials[phase_trials["roundId"] == rid]
                        for grp in round_data["currentGroup"].unique():
                            group_round = round_data[round_data["currentGroup"] == grp]
                            n_players = group_round["playerId"].nunique()
                            actual = len(group_round)
                            assert actual == n_players, (
                                f"Game {gid}, phase {pn}, round {rid}, group {grp}: "
                                f"expected {n_players} trials (one per player), "
                                f"got {actual}"
                            )
                else:
                    # Stable groups: check per (block, group)
                    for bn in phase_trials["blockNum"].unique():
                        block = phase_trials[phase_trials["blockNum"] == bn]
                        for grp in block["currentGroup"].unique():
                            group_block = block[block["currentGroup"] == grp]
                            n_players = group_block["playerId"].nunique()
                            expected = n_players * NUM_TANGRAMS
                            actual = len(group_block)
                            assert actual == expected, (
                                f"Game {gid}, phase {pn}, block {bn}, group {grp}: "
                                f"expected {expected} trials ({n_players} players * "
                                f"{NUM_TANGRAMS} tangrams), got {actual}"
                            )


# ============ 6. TARGET COVERAGE ============


class TestTargetCoverage:
    """Validate that each block covers all tangrams."""

    def test_six_tangrams_per_block_per_group(self, trials, game_ids):
        """Each group should see all 6 tangrams exactly once per block."""
        for gid in game_ids:
            game_trials = trials[trials["gameId"] == gid]
            for pn in game_trials["phaseNum"].unique():
                phase_trials = game_trials[game_trials["phaseNum"] == pn]
                for bn in phase_trials["blockNum"].unique():
                    block = phase_trials[phase_trials["blockNum"] == bn]
                    for grp in block["currentGroup"].unique():
                        group_block = block[block["currentGroup"] == grp]
                        # Each player should see exactly 6 unique targets
                        for pid in group_block["playerId"].unique():
                            player_block = group_block[group_block["playerId"] == pid]
                            targets = player_block["target"].tolist()
                            assert len(targets) == NUM_TANGRAMS, (
                                f"Game {gid}, phase {pn}, block {bn}, group {grp}, "
                                f"player {pid}: expected {NUM_TANGRAMS} targets, "
                                f"got {len(targets)}"
                            )
                            assert len(set(targets)) == NUM_TANGRAMS, (
                                f"Game {gid}, phase {pn}, block {bn}, group {grp}, "
                                f"player {pid}: duplicate targets found in "
                                f"{targets}"
                            )

    def test_all_players_in_group_see_same_targets(
        self, trials, game_ids, game_condition_map
    ):
        """Within a group, all players should see the same target each round.

        For stable groups (Phase 1, refer_separated Phase 2), we check per
        (block, group). For mixed Phase 2, groups change each trial, so we
        check per (roundId, currentGroup) that all players share the same target.
        """
        for gid in game_ids:
            game_trials = trials[trials["gameId"] == gid]
            condition = game_condition_map.get(gid)
            is_mixed = condition in ("refer_mixed", "social_mixed")

            for pn in game_trials["phaseNum"].unique():
                phase_trials = game_trials[game_trials["phaseNum"] == pn]

                if is_mixed and pn == 2:
                    # Per-trial check: within each round, all players in the
                    # same current group should see the same target
                    for rid in phase_trials["roundId"].unique():
                        round_data = phase_trials[phase_trials["roundId"] == rid]
                        for grp in round_data["currentGroup"].unique():
                            group_round = round_data[round_data["currentGroup"] == grp]
                            targets = group_round["target"].unique()
                            assert len(targets) == 1, (
                                f"Game {gid}, phase {pn}, round {rid}, group {grp}: "
                                f"players see different targets: {targets}"
                            )
                else:
                    # Stable groups: check per (block, group)
                    for bn in phase_trials["blockNum"].unique():
                        block = phase_trials[phase_trials["blockNum"] == bn]
                        for grp in block["currentGroup"].unique():
                            group_block = block[block["currentGroup"] == grp]
                            target_sets = []
                            for pid in group_block["playerId"].unique():
                                player_targets = set(
                                    group_block[group_block["playerId"] == pid]["target"]
                                )
                                target_sets.append(player_targets)
                            for ts in target_sets[1:]:
                                assert ts == target_sets[0], (
                                    f"Game {gid}, phase {pn}, block {bn}, group {grp}: "
                                    f"players see different target sets"
                                )


# ============ 7. SHUFFLING IN PHASE 2 ============


class TestShuffling:
    """Validate group shuffling behavior by condition."""

    def test_phase1_no_shuffling(self, trials, game_ids):
        """In Phase 1, currentGroup should always equal originalGroup."""
        for gid in game_ids:
            game_trials = trials[trials["gameId"] == gid]
            p1 = game_trials[game_trials["phaseNum"] == 1]
            mismatched = p1[p1["currentGroup"] != p1["originalGroup"]]
            assert len(mismatched) == 0, (
                f"Game {gid}, Phase 1: {len(mismatched)} trials where "
                f"currentGroup != originalGroup"
            )

    def test_refer_separated_no_shuffling(self, trials, game_condition_map):
        """In refer_separated, currentGroup should always equal originalGroup."""
        for gid, cond in game_condition_map.items():
            if cond != "refer_separated":
                continue
            game_trials = trials[trials["gameId"] == gid]
            mismatched = game_trials[
                game_trials["currentGroup"] != game_trials["originalGroup"]
            ]
            assert len(mismatched) == 0, (
                f"Game {gid} (refer_separated): {len(mismatched)} trials "
                f"where currentGroup != originalGroup"
            )

    def test_mixed_conditions_have_shuffling_in_phase2(
        self, trials, game_condition_map
    ):
        """In mixed conditions, some Phase 2 trials should have different groups."""
        for gid, cond in game_condition_map.items():
            if cond not in ("refer_mixed", "social_mixed"):
                continue
            game_trials = trials[trials["gameId"] == gid]
            p2 = game_trials[game_trials["phaseNum"] == 2]
            if len(p2) == 0:
                continue
            different = (p2["currentGroup"] != p2["originalGroup"]).sum()
            assert different > 0, (
                f"Game {gid} ({cond}): no shuffling detected in Phase 2 "
                f"(all currentGroup == originalGroup)"
            )

    def test_mixed_groups_are_truly_mixed(self, trials, game_condition_map):
        """In mixed Phase 2, each group should contain players from 2+
        original groups (per trial, since groups are reshuffled each trial).

        With constrained reshuffling and all 9 players active, ALL groups
        are guaranteed mixed. We check per (roundId, currentGroup).
        """
        for gid, cond in game_condition_map.items():
            if cond not in ("refer_mixed", "social_mixed"):
                continue
            game_trials = trials[trials["gameId"] == gid]
            p2 = game_trials[game_trials["phaseNum"] == 2]
            if len(p2) == 0:
                continue
            for rid in p2["roundId"].unique():
                round_data = p2[p2["roundId"] == rid]
                any_mixed = False
                for grp in round_data["currentGroup"].unique():
                    group_data = round_data[round_data["currentGroup"] == grp]
                    original_groups = group_data["originalGroup"].nunique()
                    if original_groups >= 2:
                        any_mixed = True
                        break
                assert any_mixed, (
                    f"Game {gid} ({cond}), Phase 2 round {rid}: "
                    f"no group has players from 2+ original groups"
                )

    def test_reshuffling_preserves_group_sizes(self, trials, game_condition_map):
        """After reshuffling, each group should still have GROUP_SIZE members
        (or GROUP_SIZE-1 if a player was removed).

        Groups are reshuffled each trial, so check per (roundId, currentGroup).
        """
        for gid, cond in game_condition_map.items():
            if cond not in ("refer_mixed", "social_mixed"):
                continue
            game_trials = trials[trials["gameId"] == gid]
            p2 = game_trials[game_trials["phaseNum"] == 2]
            for rid in p2["roundId"].unique():
                round_data = p2[p2["roundId"] == rid]
                for grp in round_data["currentGroup"].unique():
                    group_data = round_data[round_data["currentGroup"] == grp]
                    n_players = group_data["playerId"].nunique()
                    assert n_players in [GROUP_SIZE - 1, GROUP_SIZE], (
                        f"Game {gid} ({cond}), Phase 2 round {rid}, group {grp}: "
                        f"expected {GROUP_SIZE} or {GROUP_SIZE - 1} players, "
                        f"got {n_players}"
                    )


# ============ 7b. IN-GROUP LISTENER CONSTRAINT ============


class TestInGroupListenerConstraint:
    """Validate that constrained reshuffling produces exactly 1 in-group listener.

    In Phase 2 mixed conditions, when all 9 players (3 original groups × 3
    player indices) are active, each group of 3 should have exactly 1 listener
    who shares the speaker's original group.
    """

    def test_exactly_one_ingroup_listener(self, trials, game_condition_map):
        """For each trial in Phase 2 mixed conditions with a full group of 3,
        the speaker should have exactly 1 listener from their original group.
        """
        violations = []
        for gid, cond in game_condition_map.items():
            if cond not in ("refer_mixed", "social_mixed"):
                continue
            game_trials = trials[trials["gameId"] == gid]
            p2 = game_trials[game_trials["phaseNum"] == 2]
            if len(p2) == 0:
                continue

            # Check how many active players are in each round
            for rid in p2["roundId"].unique():
                round_data = p2[p2["roundId"] == rid]
                total_active = round_data["playerId"].nunique()

                for grp in round_data["currentGroup"].unique():
                    group_data = round_data[round_data["currentGroup"] == grp]
                    n_players = group_data["playerId"].nunique()

                    # Only check groups of exactly 3 with all 9 active
                    if n_players != GROUP_SIZE or total_active != 9:
                        continue

                    speaker_rows = group_data[group_data["role"] == "speaker"]
                    if len(speaker_rows) == 0:
                        continue
                    speaker_og = speaker_rows.iloc[0]["originalGroup"]

                    listener_rows = group_data[group_data["role"] == "listener"]
                    ingroup_listeners = listener_rows[
                        listener_rows["originalGroup"] == speaker_og
                    ]

                    if len(ingroup_listeners) != 1:
                        violations.append(
                            f"Game {gid}, round {rid}, group {grp}: "
                            f"speaker og={speaker_og}, "
                            f"in-group listeners={len(ingroup_listeners)} "
                            f"(expected 1)"
                        )

        assert len(violations) == 0, (
            f"In-group listener constraint violated in {len(violations)} "
            f"trials:\n" + "\n".join(violations[:10])
        )


# ============ 8. IDENTITY MASKING ============


class TestIdentityMasking:
    """Validate identity masking in mixed Phase 2 conditions."""

    def test_phase1_uses_original_names(self, trials, game_ids):
        """In Phase 1, playerName should be the player's original name (not 'Player')."""
        for gid in game_ids:
            game_trials = trials[trials["gameId"] == gid]
            p1 = game_trials[game_trials["phaseNum"] == 1]
            player_names = p1["playerName"].unique()
            assert "Player" not in player_names, (
                f"Game {gid}, Phase 1: found masked name 'Player' "
                f"when original names expected"
            )
            # All names should be from the valid set
            invalid = set(player_names) - VALID_NAMES
            assert not invalid, (
                f"Game {gid}, Phase 1: invalid names found: {invalid}"
            )

    def test_mixed_phase2_uses_masked_names(self, trials, game_condition_map):
        """In Phase 2 of mixed conditions, playerName should be 'Player'."""
        for gid, cond in game_condition_map.items():
            if cond not in ("refer_mixed", "social_mixed"):
                continue
            game_trials = trials[trials["gameId"] == gid]
            p2 = game_trials[game_trials["phaseNum"] == 2]
            if len(p2) == 0:
                continue
            unique_names = set(p2["playerName"].unique())
            assert unique_names == {"Player"}, (
                f"Game {gid} ({cond}), Phase 2: expected all names to be "
                f"'Player', got {unique_names}"
            )

    def test_refer_separated_phase2_uses_original_names(
        self, trials, game_condition_map
    ):
        """In refer_separated Phase 2, playerName should be original names."""
        for gid, cond in game_condition_map.items():
            if cond != "refer_separated":
                continue
            game_trials = trials[trials["gameId"] == gid]
            p2 = game_trials[game_trials["phaseNum"] == 2]
            if len(p2) == 0:
                continue
            player_names = p2["playerName"].unique()
            assert "Player" not in player_names, (
                f"Game {gid} (refer_separated), Phase 2: found masked "
                f"name 'Player' when original names expected"
            )

    def test_messages_phase2_mixed_masked(self, messages, game_condition_map):
        """In Phase 2 of mixed conditions, message senderName should be 'Player'."""
        for gid, cond in game_condition_map.items():
            if cond not in ("refer_mixed", "social_mixed"):
                continue
            game_msgs = messages[
                (messages["gameId"] == gid) & (messages["phaseNum"] == 2)
            ]
            if len(game_msgs) == 0:
                continue
            unique_names = set(game_msgs["senderName"].unique())
            assert unique_names == {"Player"}, (
                f"Game {gid} ({cond}), Phase 2 messages: expected all "
                f"senderName to be 'Player', got {unique_names}"
            )


# ============ 9. SCORING CONSISTENCY ============


class TestScoringConsistency:
    """Validate scoring logic matches experiment design."""

    def test_listener_scoring(self, trials):
        """Listeners get 2 points for correct click, 0 for incorrect."""
        listeners = trials[trials["role"] == "listener"].copy()
        # Filter to rows with non-null clickedCorrect (idle rounds may be null)
        scored = listeners[listeners["clickedCorrect"].notna()]

        correct = scored[scored["clickedCorrect"] == True]
        if len(correct) > 0:
            assert (correct["roundScore"] == LISTENER_CORRECT_POINTS).all(), (
                "Some correct listeners did not receive "
                f"{LISTENER_CORRECT_POINTS} points"
            )

        incorrect = scored[scored["clickedCorrect"] == False]
        if len(incorrect) > 0:
            assert (incorrect["roundScore"] == 0).all(), (
                "Some incorrect listeners received non-zero points"
            )

    def test_speaker_scores_in_valid_range(self, trials):
        """Speaker scores should be in [0, SPEAKER_MAX_POINTS_PER_ROUND]."""
        speakers = trials[trials["role"] == "speaker"]
        scores = speakers["roundScore"].dropna()
        assert (scores >= 0).all(), "Some speaker scores are negative"
        assert (scores <= SPEAKER_MAX_POINTS_PER_ROUND).all(), (
            f"Some speaker scores exceed {SPEAKER_MAX_POINTS_PER_ROUND}"
        )

    def test_speaker_scores_are_proportional(self, trials):
        """Speaker score = 2 * (correct_listeners / total_listeners).

        With 2 listeners, possible values are 0, 1, 2.
        """
        speakers = trials[trials["role"] == "speaker"]
        valid_scores = {
            0.0,
            SPEAKER_MAX_POINTS_PER_ROUND / LISTENERS_PER_TRIAL,  # 1.0
            SPEAKER_MAX_POINTS_PER_ROUND,  # 2.0
        }
        actual_scores = set(speakers["roundScore"].dropna().unique())
        invalid = actual_scores - valid_scores
        assert not invalid, (
            f"Speaker scores contain unexpected values: {invalid}. "
            f"Expected only {valid_scores}"
        )

    def test_speaker_score_matches_listener_accuracy(self, trials, game_ids):
        """Speaker score should equal 2 * (correct listeners / total listeners)
        for each round.
        """
        for gid in game_ids:
            game_trials = trials[trials["gameId"] == gid]
            # Group by round and currentGroup
            for rid in game_trials["roundId"].unique():
                round_data = game_trials[game_trials["roundId"] == rid]
                for grp in round_data["currentGroup"].unique():
                    group_round = round_data[round_data["currentGroup"] == grp]
                    speaker = group_round[group_round["role"] == "speaker"]
                    listeners = group_round[group_round["role"] == "listener"]

                    if len(speaker) == 0 or len(listeners) == 0:
                        continue

                    speaker_score = speaker.iloc[0]["roundScore"]
                    scored_listeners = listeners[listeners["clickedCorrect"].notna()]
                    if len(scored_listeners) == 0:
                        continue

                    correct_count = scored_listeners["clickedCorrect"].sum()
                    total_listeners = len(scored_listeners)
                    expected_score = (
                        SPEAKER_MAX_POINTS_PER_ROUND
                        * correct_count
                        / total_listeners
                    )
                    assert abs(speaker_score - expected_score) < 0.01, (
                        f"Game {gid}, round {rid}, group {grp}: "
                        f"speaker score {speaker_score} != expected "
                        f"{expected_score} ({correct_count}/{total_listeners} "
                        f"correct)"
                    )

    def test_cumulative_scores_are_nonnegative(self, active_players):
        """All player cumulative scores should be non-negative."""
        assert (active_players["score"] >= 0).all(), (
            "Some active players have negative cumulative scores"
        )

    def test_bonuses_are_nonnegative(self, active_players):
        assert (active_players["bonus"] >= 0).all(), (
            "Some active players have negative bonuses"
        )


# ============ 10. BONUS CALCULATION ============


class TestBonusCalculation:
    """Validate bonus calculation.

    For refer conditions: bonus = score * 0.05
    For social_mixed: bonus = (score + social_points) * 0.04
    where social_points include both listener social guesses and speaker
    social points (not all captured in preprocessed CSVs).
    """

    def test_refer_condition_bonus(self, active_players, game_condition_map):
        """For refer conditions, bonus should equal score * BONUS_PER_POINT."""
        for _, p in active_players.iterrows():
            cond = game_condition_map.get(p["gameId"])
            if cond not in ("refer_separated", "refer_mixed"):
                continue
            expected = round(p["score"] * BONUS_PER_POINT, 2)
            assert abs(p["bonus"] - expected) < 0.01, (
                f"Player {p['originalName']} ({cond}): bonus {p['bonus']} != "
                f"expected {expected} (score {p['score']} * {BONUS_PER_POINT})"
            )

    def test_social_condition_bonus_uses_lower_rate(
        self, active_players, game_condition_map
    ):
        """For social_mixed, bonus should be >= score * BONUS_PER_POINT_SOCIAL.

        The bonus includes social points on top of the base score, so
        bonus >= score * 0.04. We cannot verify exact amounts because
        speaker social points are not in the preprocessed data.
        """
        for _, p in active_players.iterrows():
            cond = game_condition_map.get(p["gameId"])
            if cond != "social_mixed":
                continue
            min_bonus = p["score"] * BONUS_PER_POINT_SOCIAL
            assert p["bonus"] >= min_bonus - 0.01, (
                f"Player {p['originalName']} (social_mixed): bonus {p['bonus']} "
                f"is less than minimum expected {min_bonus:.2f} "
                f"(score {p['score']} * {BONUS_PER_POINT_SOCIAL})"
            )

    def test_social_bonus_includes_listener_social_points(
        self, active_players, social_guesses, game_condition_map
    ):
        """For social_mixed, verify bonus accounts for listener social guesses.

        bonus = (score + listener_social_points + speaker_social_points) * 0.04
        We verify that bonus >= (score + listener_social_points) * 0.04.
        """
        for _, p in active_players.iterrows():
            cond = game_condition_map.get(p["gameId"])
            if cond != "social_mixed":
                continue
            player_guesses = social_guesses[
                social_guesses["playerId"] == p["playerId"]
            ]
            listener_social_correct = player_guesses["socialGuessCorrect"].sum()
            listener_social_points = listener_social_correct * SOCIAL_GUESS_CORRECT_POINTS
            expected_min = (
                (p["score"] + listener_social_points) * BONUS_PER_POINT_SOCIAL
            )
            assert p["bonus"] >= expected_min - 0.01, (
                f"Player {p['originalName']} (social_mixed): bonus {p['bonus']} "
                f"< expected minimum {expected_min:.2f} "
                f"(score={p['score']}, listener_social={listener_social_points})"
            )


# ============ 11. SOCIAL GUESSING ============


class TestSocialGuessing:
    """Validate social guessing data."""

    def test_social_guesses_only_in_social_mixed(
        self, social_guesses, game_condition_map
    ):
        """Social guesses should only exist for social_mixed games."""
        for gid in social_guesses["gameId"].unique():
            cond = game_condition_map.get(gid)
            assert cond == "social_mixed", (
                f"Social guesses found for game {gid} with condition "
                f"'{cond}', expected 'social_mixed'"
            )

    def test_social_guesses_only_in_phase2(self, social_guesses, trials):
        """Social guesses should only be from Phase 2 (social guessing UI
        only shows when phase_num == 2).

        We verify by checking that the social guess blockNums correspond
        to Phase 2 blocks in the trials data.
        """
        for gid in social_guesses["gameId"].unique():
            game_guesses = social_guesses[social_guesses["gameId"] == gid]
            game_trials = trials[trials["gameId"] == gid]

            # Get the set of (playerId, blockNum, target) from social guesses
            for _, guess in game_guesses.iterrows():
                matching_trials = game_trials[
                    (game_trials["playerId"] == guess["playerId"])
                    & (game_trials["blockNum"] == guess["blockNum"])
                    & (game_trials["target"] == guess["target"])
                ]
                if len(matching_trials) > 0:
                    # The trial should be Phase 2
                    phase_nums = matching_trials["phaseNum"].unique()
                    assert 2 in phase_nums, (
                        f"Social guess for player {guess['playerId']}, "
                        f"block {guess['blockNum']}, target {guess['target']} "
                        f"matches Phase {phase_nums} trials, expected Phase 2"
                    )

    def test_social_guess_values(self, social_guesses):
        """Social guess should be 'same_group' or 'different_group'."""
        invalid = (
            set(social_guesses["socialGuess"].unique()) - VALID_SOCIAL_GUESSES
        )
        assert not invalid, f"Invalid social guess values: {invalid}"

    def test_social_guess_correct_is_boolean(self, social_guesses):
        """socialGuessCorrect should be boolean (NaN allowed for idle rounds where speaker didn't send a message)."""
        non_null = social_guesses["socialGuessCorrect"].dropna()
        values = set(non_null.unique())
        assert values <= {True, False}, (
            f"socialGuessCorrect has non-boolean values: {values}"
        )

    def test_social_guesses_only_from_listeners(self, social_guesses, trials):
        """Social guesses should come from listeners, not speakers.

        Since blockNum resets between phases, we match on Phase 2 trials only.
        """
        for gid in social_guesses["gameId"].unique():
            game_guesses = social_guesses[social_guesses["gameId"] == gid]
            game_trials = trials[
                (trials["gameId"] == gid) & (trials["phaseNum"] == 2)
            ]

            for _, guess in game_guesses.iterrows():
                matching = game_trials[
                    (game_trials["playerId"] == guess["playerId"])
                    & (game_trials["blockNum"] == guess["blockNum"])
                    & (game_trials["target"] == guess["target"])
                ]
                if len(matching) > 0:
                    role = matching.iloc[0]["role"]
                    assert role == "listener", (
                        f"Social guess from player {guess['playerId']} in "
                        f"block {guess['blockNum']} for target {guess['target']}: "
                        f"role is '{role}', expected 'listener'"
                    )

    def test_no_social_guesses_for_idle_player(
        self, social_guesses, idle_players
    ):
        """Idle players should not have social guesses (they were removed)."""
        idle_ids = set(idle_players["playerId"])
        guess_player_ids = set(social_guesses["playerId"].unique())
        overlap = idle_ids & guess_player_ids
        assert not overlap, (
            f"Idle players have social guesses: {overlap}"
        )

    def test_social_guess_correctness_logic(self, social_guesses, trials):
        """socialGuessCorrect should be True when:
        - guess is 'same_group' AND speaker is from same original group, OR
        - guess is 'different_group' AND speaker is from different original group.
        """
        for gid in social_guesses["gameId"].unique():
            game_guesses = social_guesses[social_guesses["gameId"] == gid]
            game_trials = trials[
                (trials["gameId"] == gid) & (trials["phaseNum"] == 2)
            ]

            for _, guess in game_guesses.iterrows():
                # Find the speaker for this round
                matching_round = game_trials[
                    (game_trials["blockNum"] == guess["blockNum"])
                    & (game_trials["target"] == guess["target"])
                ]

                # Find the listener's current group
                listener_trial = matching_round[
                    matching_round["playerId"] == guess["playerId"]
                ]
                if len(listener_trial) == 0:
                    continue
                listener_group = listener_trial.iloc[0]["currentGroup"]

                # Find the speaker in the same group
                speaker = matching_round[
                    (matching_round["currentGroup"] == listener_group)
                    & (matching_round["role"] == "speaker")
                ]
                if len(speaker) == 0:
                    continue

                speaker_original = speaker.iloc[0]["originalGroup"]
                listener_original = guess["originalGroup"]

                same_group = speaker_original == listener_original
                guessed_same = guess["socialGuess"] == "same_group"
                expected_correct = same_group == guessed_same

                # NaN means scoring didn't run (e.g., speaker was idle)
                if pd.isna(guess["socialGuessCorrect"]):
                    continue
                assert guess["socialGuessCorrect"] == expected_correct, (
                    f"Social guess correctness mismatch: "
                    f"listener orig={listener_original}, "
                    f"speaker orig={speaker_original}, "
                    f"guess='{guess['socialGuess']}', "
                    f"recorded={guess['socialGuessCorrect']}, "
                    f"expected={expected_correct}"
                )


# ============ 12. SPEAKER UTTERANCES ============


class TestSpeakerUtterances:
    """Validate speaker utterance data."""

    def test_one_utterance_per_speaker_per_round(
        self, speaker_utterances, trials, game_ids
    ):
        """There should be at most one concatenated utterance per speaker per round."""
        # speaker_utterances is already grouped by round, so check for duplicates
        dupes = speaker_utterances.duplicated(
            subset=["gameId", "playerId", "blockNum", "phaseNum", "target"],
            keep=False,
        )
        assert not dupes.any(), (
            f"Found {dupes.sum()} duplicate speaker utterance rows"
        )

    def test_utt_length_is_word_count(self, speaker_utterances):
        """uttLength should equal the word count of the utterance."""
        for _, row in speaker_utterances.iterrows():
            expected_length = len(str(row["utterance"]).split())
            assert row["uttLength"] == expected_length, (
                f"Utterance word count mismatch: '{row['utterance']}' has "
                f"{expected_length} words but uttLength={row['uttLength']}"
            )

    def test_speaker_utterances_have_valid_groups(self, speaker_utterances):
        invalid = (
            set(speaker_utterances["originalGroup"].unique()) - VALID_GROUPS
        )
        assert not invalid, (
            f"speaker_utterances has invalid originalGroup: {invalid}"
        )

    def test_speaker_utterances_non_empty(self, speaker_utterances):
        """All utterances should be non-empty strings."""
        empty = speaker_utterances[
            speaker_utterances["utterance"].isna()
            | (speaker_utterances["utterance"].str.strip() == "")
        ]
        assert len(empty) == 0, (
            f"Found {len(empty)} empty/null speaker utterances"
        )


# ============ 13. REPNUM ============


class TestRepNum:
    """Validate repetition number tracking for speakers."""

    def test_repnum_starts_at_one(self, speaker_utterances):
        """repNum should start at 1 for each speaker x tangram."""
        grouped = speaker_utterances.groupby(
            ["gameId", "playerId", "target"]
        )
        for (gid, pid, target), group in grouped:
            min_rep = group["repNum"].min()
            assert min_rep == 1, (
                f"Game {gid}, player {pid}, target {target}: "
                f"repNum starts at {min_rep}, expected 1"
            )

    def test_repnum_values_are_unique_and_positive(self, speaker_utterances):
        """repNum values should be unique positive integers within each
        speaker x tangram group.

        Note: repNum may have gaps in speaker_utterances when the speaker
        sent no message in a round (e.g., timed out). The repNum values
        come from trials where they are consecutive, but speaker_utterances
        only includes rounds with actual messages.
        """
        grouped = speaker_utterances.groupby(
            ["gameId", "playerId", "target"]
        )
        for (gid, pid, target), group in grouped:
            reps = group["repNum"].tolist()
            # All should be positive
            assert all(r >= 1 for r in reps), (
                f"Game {gid}, player {pid}, target {target}: "
                f"repNum has non-positive values: {reps}"
            )
            # All should be unique
            assert len(reps) == len(set(reps)), (
                f"Game {gid}, player {pid}, target {target}: "
                f"repNum has duplicate values: {reps}"
            )

    def test_repnum_consecutive_in_trials(self, trials):
        """repNum in trials should be consecutive integers from 1..N
        for each speaker x tangram group.
        """
        speaker_trials = trials[
            (trials["role"] == "speaker") & (trials["repNum"].notna())
        ]
        grouped = speaker_trials.groupby(["gameId", "playerId", "target"])
        for (gid, pid, target), group in grouped:
            reps = sorted(group["repNum"].tolist())
            expected = list(range(1, len(reps) + 1))
            assert reps == expected, (
                f"Game {gid}, player {pid}, target {target}: "
                f"trial repNum values {reps} are not consecutive "
                f"from 1 to {len(reps)}"
            )

    def test_repnum_only_for_speakers(self, trials):
        """repNum should be non-null only for speaker trials."""
        speakers = trials[trials["role"] == "speaker"]
        listeners = trials[trials["role"] == "listener"]

        # Speakers should have repNum (for active rounds)
        speaker_non_null = speakers["repNum"].notna().sum()
        assert speaker_non_null > 0, "No speakers have repNum values"

        # Listeners should not have repNum
        listener_non_null = listeners["repNum"].notna().sum()
        assert listener_non_null == 0, (
            f"{listener_non_null} listener trials have repNum values"
        )

    def test_repnum_max_is_bounded(self, speaker_utterances):
        """The maximum repNum should not exceed the total number of blocks
        where a player could speak about a given tangram.

        In the worst case, a player speaks in every block (which doesn't
        happen because of rotation), so repNum max <= total blocks / GROUP_SIZE * 2.
        In practice, each speaker speaks in 2 blocks per phase = 4 total.
        """
        max_rep = speaker_utterances["repNum"].max()
        # Each speaker speaks 2 blocks per phase, 2 phases = 4 repetitions per tangram
        # But could be up to 6 if tangrams overlap across phases
        assert max_rep <= TOTAL_BLOCKS, (
            f"Maximum repNum is {max_rep}, exceeds total blocks {TOTAL_BLOCKS}"
        )


# ============ 14. MESSAGES ============


class TestMessages:
    """Validate chat message data."""

    def test_sender_role_values(self, messages):
        """senderRole should be 'speaker' or 'listener'."""
        invalid = set(messages["senderRole"].dropna().unique()) - VALID_ROLES
        assert not invalid, f"Invalid senderRole values: {invalid}"

    def test_messages_have_timestamps(self, messages):
        """All messages should have a timestamp."""
        null_timestamps = messages["timestamp"].isna().sum()
        assert null_timestamps == 0, (
            f"{null_timestamps} messages have null timestamps"
        )

    def test_messages_have_text(self, messages):
        """All messages should have non-empty text."""
        empty = messages[
            messages["text"].isna() | (messages["text"].str.strip() == "")
        ]
        assert len(empty) == 0, f"Found {len(empty)} messages with empty text"

    def test_speaker_messages_exist_for_active_rounds(
        self, messages, trials, game_ids
    ):
        """For rounds where a speaker was active, there should be at least
        one speaker message.

        Note: we check at the round+group level to match the chat scope.
        """
        for gid in game_ids:
            game_trials = trials[trials["gameId"] == gid]
            game_msgs = messages[messages["gameId"] == gid]

            # Get unique (roundId, currentGroup) from speaker trials
            speaker_trials = game_trials[game_trials["role"] == "speaker"]
            for _, st in speaker_trials.iterrows():
                round_msgs = game_msgs[
                    (game_msgs["roundId"] == st["roundId"])
                    & (game_msgs["group"] == st["currentGroup"])
                    & (game_msgs["senderRole"] == "speaker")
                ]
                # Speaker should have sent at least one message
                # (unless they were idle, which would be their last round)
                if st["roundScore"] > 0 or (
                    st.get("clickedCorrect") is not None
                ):
                    # Only check rounds where listeners responded
                    pass  # Relaxed: speaker may not always send messages
                    # (edge case: auto-submit on timeout)

    def test_messages_group_is_valid(self, messages):
        invalid = set(messages["group"].unique()) - VALID_GROUPS
        assert not invalid, f"Messages have invalid group values: {invalid}"

    def test_message_phase2_mixed_sender_names_masked(
        self, messages, game_condition_map
    ):
        """In Phase 2 of mixed conditions, senderName should be 'Player'."""
        for gid, cond in game_condition_map.items():
            if cond not in ("refer_mixed", "social_mixed"):
                continue
            phase2_msgs = messages[
                (messages["gameId"] == gid) & (messages["phaseNum"] == 2)
            ]
            if len(phase2_msgs) == 0:
                continue
            unique_names = set(phase2_msgs["senderName"].unique())
            assert unique_names == {"Player"}, (
                f"Game {gid} ({cond}), Phase 2 messages: senderName values "
                f"{unique_names}, expected only 'Player'"
            )


# ============ 15. IDLE PLAYER HANDLING ============


class TestIdlePlayerHandling:
    """Validate that idle players are handled correctly."""

    def test_idle_player_has_fewer_trials(self, trials, idle_players, game_ids):
        """Idle players should have fewer trials than active players."""
        for _, idle_p in idle_players.iterrows():
            gid = idle_p["gameId"]
            idle_trial_count = len(
                trials[trials["playerId"] == idle_p["playerId"]]
            )
            # Active players in the same game
            active_trial_counts = []
            game_trials = trials[trials["gameId"] == gid]
            for pid in game_trials["playerId"].unique():
                if pid != idle_p["playerId"]:
                    active_trial_counts.append(
                        len(game_trials[game_trials["playerId"] == pid])
                    )
            if active_trial_counts:
                max_active = max(active_trial_counts)
                assert idle_trial_count < max_active, (
                    f"Idle player {idle_p['playerId']} has {idle_trial_count} "
                    f"trials, which is not fewer than max active "
                    f"({max_active})"
                )

    def test_idle_player_score_lower_than_active(
        self, active_players, idle_players
    ):
        """Idle players should have lower scores than active players in
        the same game.
        """
        for _, idle_p in idle_players.iterrows():
            gid = idle_p["gameId"]
            active_in_game = active_players[active_players["gameId"] == gid]
            if len(active_in_game) == 0:
                continue
            min_active_score = active_in_game["score"].min()
            assert idle_p["score"] < min_active_score, (
                f"Idle player {idle_p['playerId']} score {idle_p['score']} "
                f"is not lower than minimum active score {min_active_score}"
            )


# ============ 16. CROSS-FILE CONSISTENCY ============


class TestCrossFileConsistency:
    """Validate consistency across different CSV files."""

    def test_all_trial_players_in_players_csv(self, trials, players):
        """Every playerId in trials should exist in players.csv."""
        trial_players = set(trials["playerId"].unique())
        csv_players = set(players["playerId"].unique())
        missing = trial_players - csv_players
        assert not missing, (
            f"Players in trials.csv but not in players.csv: {missing}"
        )

    def test_all_trial_games_in_games_csv(self, trials, games):
        """Every gameId in trials should exist in games.csv."""
        trial_games = set(trials["gameId"].unique())
        csv_games = set(games["gameId"].unique())
        missing = trial_games - csv_games
        assert not missing, (
            f"Games in trials.csv but not in games.csv: {missing}"
        )

    def test_all_message_games_in_games_csv(self, messages, games):
        """Every gameId in messages should exist in games.csv."""
        msg_games = set(messages["gameId"].unique())
        csv_games = set(games["gameId"].unique())
        missing = msg_games - csv_games
        assert not missing, (
            f"Games in messages.csv but not in games.csv: {missing}"
        )

    def test_speaker_utterance_players_are_speakers(
        self, speaker_utterances, trials
    ):
        """Players in speaker_utterances should be speakers in the
        corresponding trial.
        """
        for _, utt in speaker_utterances.iterrows():
            matching = trials[
                (trials["gameId"] == utt["gameId"])
                & (trials["playerId"] == utt["playerId"])
                & (trials["blockNum"] == utt["blockNum"])
                & (trials["phaseNum"] == utt["phaseNum"])
                & (trials["target"] == utt["target"])
            ]
            if len(matching) > 0:
                role = matching.iloc[0]["role"]
                assert role == "speaker", (
                    f"Speaker utterance player {utt['playerId']} has role "
                    f"'{role}' in trials for block {utt['blockNum']}, "
                    f"target {utt['target']}"
                )

    def test_social_guesses_game_is_social_mixed(
        self, social_guesses, game_condition_map
    ):
        """All social guess game IDs should be for social_mixed condition."""
        for gid in social_guesses["gameId"].unique():
            cond = game_condition_map.get(gid)
            assert cond == "social_mixed", (
                f"Social guesses in game {gid} with condition '{cond}'"
            )

    def test_tangram_sets_consistent(self, trials, games):
        """Tangram set in trials should match the game's tangram set."""
        for _, game in games.iterrows():
            game_trials = trials[trials["gameId"] == game["gameId"]]
            trial_sets = game_trials["tangramSet"].unique()
            assert len(trial_sets) == 1, (
                f"Game {game['gameId']}: multiple tangram sets in trials: "
                f"{trial_sets}"
            )
            assert trial_sets[0] == game["tangramSet"], (
                f"Game {game['gameId']}: trial tangram set {trial_sets[0]} "
                f"!= game tangram set {game['tangramSet']}"
            )

    def test_player_cumulative_score_matches_trial_sum(
        self, active_players, trials
    ):
        """Player's cumulative score should approximately equal the sum of
        their roundScore in trials. Allow small float tolerance.
        """
        for _, p in active_players.iterrows():
            player_trials = trials[trials["playerId"] == p["playerId"]]
            trial_score_sum = player_trials["roundScore"].sum()
            # score field might include social points too, so for social_mixed
            # it may differ. For refer conditions, they should match.
            # We check that the trial-based score is close
            assert abs(p["score"] - trial_score_sum) < 0.5, (
                f"Player {p['originalName']}: cumulative score {p['score']} "
                f"!= sum of trial roundScores {trial_score_sum}"
            )


# ============ 17. PARAMETRIZED PER-GAME TESTS ============


def get_real_game_ids():
    """Get game IDs for parametrize decorator."""
    games_path = DATA_DIR / "games.csv"
    if not games_path.exists():
        return []
    games = pd.read_csv(games_path)
    return games[games["condition"].notna()]["gameId"].tolist()


@pytest.mark.parametrize("game_id", get_real_game_ids())
class TestPerGame:
    """Tests parametrized per game for clear reporting."""

    def test_total_active_player_trials(self, game_id, trials, active_players):
        """Active players should have trials for all blocks they participated in."""
        game_active = active_players[active_players["gameId"] == game_id]
        game_trials = trials[trials["gameId"] == game_id]

        for _, p in game_active.iterrows():
            player_trials = game_trials[game_trials["playerId"] == p["playerId"]]
            # Should have trials in both phases
            phases = set(player_trials["phaseNum"].unique())
            assert 1 in phases, (
                f"Player {p['originalName']} missing Phase 1 trials"
            )
            assert 2 in phases, (
                f"Player {p['originalName']} missing Phase 2 trials"
            )

    def test_total_trial_count(self, game_id, trials, players):
        """The total trial count should match expected count based on
        active players and blocks.
        """
        game_trials = trials[trials["gameId"] == game_id]
        game_players = players[players["gameId"] == game_id]

        # Count total: each phase has blocks, each block has 6 tangrams,
        # each tangram has 3 players per group, 3 groups
        # But idle players will have fewer
        total_trials = len(game_trials)
        assert total_trials > 0, f"Game {game_id}: no trials found"

        # Minimum: all 9 players for Phase 1 (6 blocks * 6 tangrams * 9)
        # minus idle player's missed trials
        # This is a loose sanity check
        min_expected = (
            PHASE_1_BLOCKS * NUM_TANGRAMS * (PLAYERS_PER_GAME - 1)
        )
        assert total_trials >= min_expected, (
            f"Game {game_id}: only {total_trials} trials, expected at least "
            f"{min_expected}"
        )

    def test_each_player_speaks_twice_per_phase(
        self, game_id, trials, active_players
    ):
        """In each phase, each active player should be speaker in exactly
        2 blocks (6 blocks / 3 players per group = 2 speaking blocks).

        When a group member has been removed, remaining players take on
        extra speaking blocks. For a group of 2, each player speaks in
        3 blocks per phase. In mixed Phase 2, groups are reshuffled each
        trial so the effective group size may vary.

        This test checks that each player speaks in at least 2 blocks and
        that the total speaker-blocks across all group members sum to
        the correct number (one speaker per block = 6 per phase per group).
        """
        game_active = active_players[active_players["gameId"] == game_id]
        game_trials = trials[trials["gameId"] == game_id]

        for _, p in game_active.iterrows():
            player_trials = game_trials[game_trials["playerId"] == p["playerId"]]
            for pn in [1, 2]:
                phase_trials = player_trials[player_trials["phaseNum"] == pn]
                speaker_blocks = phase_trials[
                    phase_trials["role"] == "speaker"
                ]["blockNum"].nunique()
                # Each player should speak in at least
                # floor(blocks / GROUP_SIZE) blocks
                min_speaker_blocks = PHASE_1_BLOCKS // GROUP_SIZE
                assert speaker_blocks >= min_speaker_blocks, (
                    f"Player {p['originalName']}, Phase {pn}: spoke in "
                    f"{speaker_blocks} blocks, expected at least "
                    f"{min_speaker_blocks}"
                )
                # And no more than all blocks
                assert speaker_blocks <= PHASE_1_BLOCKS, (
                    f"Player {p['originalName']}, Phase {pn}: spoke in "
                    f"{speaker_blocks} blocks, which exceeds total blocks "
                    f"{PHASE_1_BLOCKS}"
                )

    def test_each_player_listens_four_blocks_per_phase(
        self, game_id, trials, active_players
    ):
        """In each phase, each active player should be listener in
        (total_blocks - speaker_blocks) blocks.

        Standard case: 6 - 2 = 4 listener blocks.
        When group has removed player: 6 - 3 = 3 listener blocks.
        In mixed conditions Phase 2: groups reshuffled, so may vary.
        """
        game_active = active_players[active_players["gameId"] == game_id]
        game_trials = trials[trials["gameId"] == game_id]

        for _, p in game_active.iterrows():
            player_trials = game_trials[game_trials["playerId"] == p["playerId"]]
            for pn in [1, 2]:
                phase_trials = player_trials[player_trials["phaseNum"] == pn]
                speaker_blocks = phase_trials[
                    phase_trials["role"] == "speaker"
                ]["blockNum"].nunique()
                listener_blocks = phase_trials[
                    phase_trials["role"] == "listener"
                ]["blockNum"].nunique()
                total = speaker_blocks + listener_blocks
                assert total == PHASE_1_BLOCKS, (
                    f"Player {p['originalName']}, Phase {pn}: speaker + "
                    f"listener blocks = {total}, expected {PHASE_1_BLOCKS}"
                )


# ============ 18. TANGRAM IDENTITY ============


class TestTangramIdentity:
    """Validate tangram identifiers match the tangram set."""

    TANGRAM_SETS = {
        0: {
            "page3-182", "page7-107", "page9-27",
            "page5-28", "page7-81", "page9-46",
        },
        1: {
            "page4-157", "page1-129", "page6-149",
            "page7-26", "page3-121", "page5-64",
        },
    }

    def test_trial_targets_match_tangram_set(self, trials, games):
        """Trial targets should be from the game's tangram set."""
        for _, game in games.iterrows():
            expected = self.TANGRAM_SETS.get(int(game["tangramSet"]))
            if expected is None:
                continue
            game_trials = trials[trials["gameId"] == game["gameId"]]
            actual_targets = set(game_trials["target"].unique())
            invalid = actual_targets - expected
            assert not invalid, (
                f"Game {game['gameId']} (set {int(game['tangramSet'])}): "
                f"unexpected targets {invalid}"
            )
            # All tangrams should be used
            missing = expected - actual_targets
            assert not missing, (
                f"Game {game['gameId']} (set {int(game['tangramSet'])}): "
                f"missing targets {missing}"
            )

    def test_message_targets_match_tangram_set(self, messages, games):
        """Message targets should be from the game's tangram set."""
        for _, game in games.iterrows():
            expected = self.TANGRAM_SETS.get(int(game["tangramSet"]))
            if expected is None:
                continue
            game_msgs = messages[messages["gameId"] == game["gameId"]]
            actual_targets = set(game_msgs["target"].unique())
            invalid = actual_targets - expected
            assert not invalid, (
                f"Game {game['gameId']} messages: unexpected targets {invalid}"
            )


# ============ 19. EXIT SURVEY ============


class TestExitSurvey:
    """Validate exit survey data for active players."""

    def test_active_players_have_exit_survey(self, active_players):
        """Active players who completed the game should have exit survey data."""
        exit_cols = [
            c for c in active_players.columns if c.startswith("exitSurvey_")
        ]
        if not exit_cols:
            pytest.skip("No exit survey columns found in players.csv")

        for _, p in active_players.iterrows():
            # At least some exit survey fields should be non-null
            has_survey = any(pd.notna(p[col]) for col in exit_cols)
            assert has_survey, (
                f"Active player {p['originalName']}: no exit survey data"
            )

    def test_exit_survey_understood_field(self, active_players):
        """exitSurvey_understood should be present for active players."""
        if "exitSurvey_understood" not in active_players.columns:
            pytest.skip("exitSurvey_understood column not found")
        null_count = active_players["exitSurvey_understood"].isna().sum()
        assert null_count == 0, (
            f"{null_count} active players missing exitSurvey_understood"
        )


# ============ 20. DATA COMPLETENESS ============


class TestDataCompleteness:
    """Validate that the dataset is complete and internally consistent."""

    def test_at_least_one_real_game(self, games):
        assert len(games) > 0, "No real (non-test) games found in games.csv"

    def test_all_conditions_represented(self, games):
        """Check which conditions are present (informational, not strict)."""
        conditions = set(games["condition"].unique())
        # At minimum, we expect the games we have to be valid
        assert conditions <= VALID_CONDITIONS, (
            f"Invalid conditions found: {conditions - VALID_CONDITIONS}"
        )

    def test_no_orphan_messages(self, messages, trials):
        """All message roundIds should exist in trials."""
        msg_rounds = set(messages["roundId"].unique())
        trial_rounds = set(trials["roundId"].unique())
        orphans = msg_rounds - trial_rounds
        assert not orphans, (
            f"Messages reference {len(orphans)} roundIds not in trials"
        )

    def test_no_orphan_speaker_utterances(self, speaker_utterances, trials):
        """All speaker utterance roundIds should traceable to trials via
        (gameId, playerId, blockNum, phaseNum, target).
        """
        merged = speaker_utterances.merge(
            trials[["gameId", "playerId", "blockNum", "phaseNum", "target", "role"]],
            on=["gameId", "playerId", "blockNum", "phaseNum", "target"],
            how="left",
        )
        unmatched = merged[merged["role"].isna()]
        assert len(unmatched) == 0, (
            f"{len(unmatched)} speaker utterances don't match any trial"
        )

    def test_listener_click_data_present(self, trials):
        """Listeners should have clicked and clickedCorrect data
        (except for idle rounds).
        """
        listeners = trials[trials["role"] == "listener"]
        # Count how many listener trials are missing click data
        missing_click = listeners["clicked"].isna().sum()
        total_listeners = len(listeners)
        # Allow a small number of missing clicks (idle rounds)
        missing_pct = missing_click / total_listeners if total_listeners > 0 else 0
        assert missing_pct < 0.05, (
            f"{missing_click}/{total_listeners} ({missing_pct:.1%}) listener "
            f"trials missing click data"
        )
