"""
Data integrity tests for preprocessed experiment data.

Validates the preprocessed CSV files of one dataset (data/<dataset>/, the
pilot sessions by default) against the preregistered specifications and the
experiment's server-side logic.

Run with:
    uv run pytest analysis/test_data_integrity.py -v
    DATASET=full uv run pytest analysis/test_data_integrity.py -v
"""

import numpy as np
import pandas as pd
import pytest

from dataset_paths import dataset_dirs

# ============ CONSTANTS (from experiment design) ============

GROUP_SIZE = 3
NUM_TANGRAMS = 6
PHASE_1_BLOCKS = 6
PHASE_2_BLOCKS = 6
TOTAL_BLOCKS = PHASE_1_BLOCKS + PHASE_2_BLOCKS
LISTENERS_PER_TRIAL = 2
PLAYERS_PER_GAME = 9
NUM_GROUPS = PLAYERS_PER_GAME // GROUP_SIZE  # 3
VALID_CONDITIONS = {"refer_separated", "refer_mixed", "social_mixed", "social_first"}
VALID_GROUPS = {"A", "B", "C"}
VALID_ROLES = {"speaker", "listener"}
VALID_SOCIAL_GUESSES = {"same_group", "different_group"}
MIXED_CONDITIONS = {"refer_mixed", "social_mixed", "social_first"}
SOCIAL_CONDITIONS = {"social_mixed", "social_first"}

# Scoring
LISTENER_CORRECT_POINTS = 2
SPEAKER_MAX_POINTS_PER_ROUND = 2
SOCIAL_GUESS_CORRECT_POINTS = 6
SOCIAL_SPEAKER_POINTS_PER_CORRECT = 6
# Data directory for the dataset under test ($DATASET, default pilots)
DATASET = dataset_dirs()
DATA_DIR = DATASET.data

# The pilot runs were collected with BONUS_PER_POINT = 0.05; every later
# dataset uses the production rate in experiment/shared/constants.js.
BONUS_PER_POINT = 0.05 if DATASET.name == "pilots" else 0.0556
BONUS_PER_POINT_SOCIAL = 0.023

# Names from constants.js
VALID_NAMES = {"Repi", "Minu", "Laju", "Hera", "Zuda", "Bavi", "Lika", "Felu", "Nori"}


# ============ FIXTURES ============


@pytest.fixture(scope="session", autouse=True)
def _dataset_present():
    if not (DATA_DIR / "games.csv").exists():
        pytest.exit(
            f"No processed data for dataset '{DATASET.name}' at {DATA_DIR}; "
            "run the pipeline first (make process DATASET=<name>).",
            returncode=1,
        )


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

    def test_players_length_increase_flag(self, players, speaker_utterances):
        """The AI-use trigger: a boolean flag with its numeric basis.

        `phase1LengthChange` is the mean word count in a player's last Phase 1
        block as speaker minus their first; `lengthIncreaseFlag` is True only
        when that exceeds 5 words. Players who spoke in fewer than two Phase 1
        blocks have no change and are never flagged.
        """
        for col in ("phase1LengthChange", "lengthIncreaseFlag"):
            assert col in players.columns, f"players.csv missing column: {col}"
        flag = players["lengthIncreaseFlag"]
        assert set(flag.dropna().unique()) <= {True, False}
        change = pd.to_numeric(players["phase1LengthChange"])
        assert ((change > 5) == flag).all(), "lengthIncreaseFlag disagrees with phase1LengthChange > 5"
        p1 = speaker_utterances[speaker_utterances["phaseNum"] == 1]
        blocks = p1.groupby(["gameId", "playerId"])["blockNum"].nunique()
        two_plus = players.set_index(["gameId", "playerId"]).index.map(
            lambda k: blocks.get(k, 0) >= 2
        )
        assert change.notna().to_numpy().tolist() == list(two_plus), (
            "phase1LengthChange should be present exactly for players with two or more Phase 1 speaker blocks"
        )

    def test_players_required_columns(self, players):
        required = [
            "playerId", "gameId", "name", "originalGroup", "originalName",
            "score", "bonus", "isActive", "idleRounds", "playerIndex",
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
            "speakerId", "inGroupSpeaker", "groupSize", "speakerReassigned",
            "reshuffleMode",
            # the server's own record of the network, empty in older exports
            "serverSpeakerId", "serverInGroupListener", "serverGroupSize",
            "reshuffleGroups", "reshuffleTrios", "reshuffleTriosOk", "reshufflePairs",
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
            "speakerWasSameGroup",
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
        """Groups can be disbanded mid-game, so a finished game can have fewer
        than 3 active groups -- but never more, and at least 2 unless the game
        was terminated early."""
        for _, game in games.iterrows():
            assert game["activeGroups"] <= NUM_GROUPS, (
                f"Game {game['gameId']}: expected at most {NUM_GROUPS} active "
                f"groups, got {game['activeGroups']}"
            )
            terminated = (
                bool(game["gameTerminated"])
                if "gameTerminated" in games.columns
                and pd.notna(game.get("gameTerminated"))
                else False
            )
            if not terminated:
                assert game["activeGroups"] >= 2, (
                    f"Game {game['gameId']}: only {game['activeGroups']} active "
                    f"group(s) but the game was not terminated"
                )

    def test_active_groups_min_is_the_smallest_phase2_roster(self, games, trials):
        """activeGroupsMin is the fewest groups any Phase 2 trial was played
        with. It is bounded by the design, and where the server recorded no
        reshuffle count (the pilot) it must equal what the trials show."""
        assert "activeGroupsMin" in games.columns
        assert games["activeGroupsMin"].notna().all()
        assert games["activeGroupsMin"].between(1, NUM_GROUPS).all()
        p2_speakers = trials[(trials["phaseNum"] == 2) & (trials["role"] == "speaker")]
        from_trials = (
            p2_speakers.groupby(["gameId", "roundId"])["currentGroup"].nunique()
            .groupby("gameId").min()
        )
        if "reshuffleGroups" in trials.columns and trials["reshuffleGroups"].notna().any():
            pytest.skip("the server's reshuffle counts take precedence in this dataset")
        for _, game in games.iterrows():
            if game["gameId"] in from_trials.index:
                assert game["activeGroupsMin"] == from_trials[game["gameId"]], (
                    f"Game {game['gameId']}: activeGroupsMin={game['activeGroupsMin']} but the "
                    f"Phase 2 trials show a minimum of {from_trials[game['gameId']]} groups"
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
        """Players removed FOR IDLING should have hit exactly MAX_IDLE_ROUNDS.

        Inactive players can also be removed for low accuracy or a disbanded
        group (exitReason distinguishes these), so only check the idle ones.
        """
        MAX_IDLE_ROUNDS = 3
        if "exitReason" not in idle_players.columns:
            pytest.skip("exitReason column not present in players.csv")
        timed_out = idle_players[idle_players["exitReason"] == "player timeout"]
        for _, p in timed_out.iterrows():
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
            is_mixed = condition in MIXED_CONDITIONS

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

    def test_trials_per_block_per_group(
        self, trials, game_ids, game_condition_map, active_players
    ):
        """Each group should have the right number of trials per block.

        In stable groups (Phase 1, or Phase 2 refer_separated), each active
        player should have NUM_TANGRAMS trials per (block, group); players
        removed mid-block may have fewer.

        In mixed Phase 2, groups are reshuffled each trial, so we check
        per (roundId, currentGroup) that each player appears exactly once.
        """
        active_ids = set(active_players["playerId"])
        for gid in game_ids:
            game_trials = trials[trials["gameId"] == gid]
            condition = game_condition_map.get(gid)
            is_mixed = condition in MIXED_CONDITIONS

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
                    # Stable groups: check per (block, group, player).
                    # A player removed mid-block (idle timeout, disband) can
                    # legitimately have a partial block, so require the full
                    # NUM_TANGRAMS only for players who finished the game.
                    for bn in phase_trials["blockNum"].unique():
                        block = phase_trials[phase_trials["blockNum"] == bn]
                        for grp in block["currentGroup"].unique():
                            group_block = block[block["currentGroup"] == grp]
                            for pid in group_block["playerId"].unique():
                                player_block = group_block[
                                    group_block["playerId"] == pid
                                ]
                                n_trials = len(player_block)
                                if pid in active_ids:
                                    assert n_trials == NUM_TANGRAMS, (
                                        f"Game {gid}, phase {pn}, block {bn}, "
                                        f"group {grp}, player {pid}: expected "
                                        f"{NUM_TANGRAMS} trials, got {n_trials}"
                                    )
                                else:
                                    assert n_trials <= NUM_TANGRAMS, (
                                        f"Game {gid}, phase {pn}, block {bn}, "
                                        f"group {grp}, removed player {pid}: "
                                        f"{n_trials} trials exceeds {NUM_TANGRAMS}"
                                    )


# ============ 6. TARGET COVERAGE ============


class TestTargetCoverage:
    """Validate that each block covers all tangrams."""

    def test_six_tangrams_per_block_per_group(
        self, trials, game_ids, active_players
    ):
        """Each player should see all 6 tangrams exactly once per block.

        Checked per player per block, NOT per (block, currentGroup): in mixed
        Phase 2 a player's currentGroup changes every trial, so their six
        block targets are spread across groups. Players removed mid-block may
        have fewer targets; duplicates are never allowed.
        """
        active_ids = set(active_players["playerId"])
        for gid in game_ids:
            game_trials = trials[trials["gameId"] == gid]
            for pn in game_trials["phaseNum"].unique():
                phase_trials = game_trials[game_trials["phaseNum"] == pn]
                for bn in phase_trials["blockNum"].unique():
                    block = phase_trials[phase_trials["blockNum"] == bn]
                    for pid in block["playerId"].unique():
                        player_block = block[block["playerId"] == pid]
                        targets = player_block["target"].tolist()
                        assert len(set(targets)) == len(targets), (
                            f"Game {gid}, phase {pn}, block {bn}, "
                            f"player {pid}: duplicate targets found in {targets}"
                        )
                        if pid in active_ids:
                            assert len(targets) == NUM_TANGRAMS, (
                                f"Game {gid}, phase {pn}, block {bn}, "
                                f"player {pid}: expected {NUM_TANGRAMS} targets, "
                                f"got {len(targets)}"
                            )

    def test_all_players_in_group_see_same_targets(self, trials, game_ids):
        """Within a group, all players should see the same target each round.

        Checked per (roundId, currentGroup) in all conditions -- this is the
        true invariant, and unlike a per-block target-set comparison it also
        holds when a player was removed mid-block (partial blocks) or when
        groups reshuffle every trial in mixed Phase 2.
        """
        for gid in game_ids:
            game_trials = trials[trials["gameId"] == gid]
            for rid in game_trials["roundId"].unique():
                round_data = game_trials[game_trials["roundId"] == rid]
                for grp in round_data["currentGroup"].unique():
                    group_round = round_data[round_data["currentGroup"] == grp]
                    targets = group_round["target"].unique()
                    assert len(targets) == 1, (
                        f"Game {gid}, round {rid}, group {grp}: "
                        f"players see different targets: {targets}"
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
            if cond not in MIXED_CONDITIONS:
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
            if cond not in MIXED_CONDITIONS:
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
            if cond not in MIXED_CONDITIONS:
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
            if cond not in MIXED_CONDITIONS:
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


def _truthy(series):
    """Exported booleans read back as True/False or 'True'/'true' strings."""
    return series.isin([True, "True", "true"])


class TestReshuffleNetwork:
    """The interaction structure recorded in trials.csv.

    Every group has one player per rotation index (in Phase 1 because the
    original trios were built that way, in Phase 2 because the reshuffle
    enforces it), the speaker and in-group columns agree with the trio
    membership, a full roster is never split into pairs, and the server's
    reshuffle record, where present, agrees with what the trios show.
    """

    def test_each_original_group_has_indices_0_1_2(self, players, game_ids):
        for gid in game_ids:
            game_players = players[players["gameId"] == gid]
            for grp in VALID_GROUPS:
                idx = sorted(
                    game_players[game_players["originalGroup"] == grp]["playerIndex"]
                    .dropna().astype(int).tolist()
                )
                assert idx == [0, 1, 2], (
                    f"Game {gid}, group {grp}: rotation indices {idx}, expected [0, 1, 2]"
                )

    def test_one_player_per_index_in_every_current_group(self, trials, players):
        idx = players.set_index("playerId")["playerIndex"]
        t = trials.assign(playerIndex=trials["playerId"].map(idx))
        assert t["playerIndex"].notna().all(), "every trial row needs a rotation index"
        dup = t.groupby(["gameId", "roundId", "currentGroup"])["playerIndex"].apply(
            lambda s: s.duplicated().any()
        )
        assert not dup.any(), (
            f"{int(dup.sum())} group-trials have two players with the same rotation index"
        )

    def test_speaker_id_matches_the_group_speaker(self, trials):
        speakers = trials[trials["role"] == "speaker"].groupby(
            ["gameId", "roundId", "currentGroup"]
        )["playerId"].agg(list)
        assert speakers.apply(len).eq(1).all(), "every group-trial should have exactly one speaker"
        expected = speakers.apply(lambda ids: ids[0]).rename("expectedSpeaker")
        merged = trials.join(expected, on=["gameId", "roundId", "currentGroup"])
        assert merged["expectedSpeaker"].notna().all(), "a group-trial without a speaker row"
        mismatch = merged[merged["speakerId"] != merged["expectedSpeaker"]]
        assert mismatch.empty, f"{len(mismatch)} rows whose speakerId is not the group's speaker"

    def test_in_group_speaker_flag_matches_original_groups(self, trials):
        og = trials.drop_duplicates("playerId").set_index("playerId")["originalGroup"]
        listeners = trials[trials["role"] == "listener"]
        expected = listeners["originalGroup"] == listeners["speakerId"].map(og)
        actual = _truthy(listeners["inGroupSpeaker"])
        assert (expected == actual).all(), "inGroupSpeaker disagrees with the speaker's original group"
        assert trials[trials["role"] == "speaker"]["inGroupSpeaker"].isna().all(), (
            "inGroupSpeaker should be empty on speaker rows"
        )

    def test_group_size_counts_the_group_members(self, trials):
        sizes = trials.groupby(["gameId", "roundId", "currentGroup"])["playerId"].transform("nunique")
        assert (trials["groupSize"] == sizes).all()
        assert (trials["groupSize"] >= 2).all(), "no player should be in a group alone"
        assert (trials["groupSize"] <= GROUP_SIZE).all()

    def test_full_roster_is_never_split_into_pairs(self, trials, game_condition_map):
        for gid, cond in game_condition_map.items():
            if cond not in MIXED_CONDITIONS:
                continue
            p2 = trials[(trials["gameId"] == gid) & (trials["phaseNum"] == 2)]
            active = p2.groupby("roundId")["playerId"].nunique()
            full_rounds = active[active == PLAYERS_PER_GAME].index
            sizes = p2[p2["roundId"].isin(full_rounds)]["groupSize"]
            assert (sizes == GROUP_SIZE).all(), (
                f"Game {gid}: a Phase 2 round with all nine players active has a group smaller than three"
            )

    def test_speaker_reassigned_matches_the_rotation_index(self, trials, players):
        idx = players.set_index("playerId")["playerIndex"]
        known = trials[trials["speakerReassigned"].notna()]
        if known.empty:
            pytest.skip("speakerReassigned is empty in this dataset")
        expected = known["speakerId"].map(idx).astype(int) != (known["blockNum"].astype(int) % GROUP_SIZE)
        actual = _truthy(known["speakerReassigned"])
        assert (expected == actual).all(), "speakerReassigned disagrees with the speaker's rotation index"

    def test_server_speaker_record_matches_the_derived_speaker(self, trials):
        """Where the server wrote speaker_id (September 2026 onward), it must
        name the same player the trio membership does."""
        recorded = trials[trials["serverSpeakerId"].notna()]
        if recorded.empty:
            pytest.skip("serverSpeakerId is empty in this dataset (the pilot exports predate it)")
        mismatch = recorded[recorded["serverSpeakerId"] != recorded["speakerId"]]
        assert mismatch.empty, f"{len(mismatch)} rows where the server's speaker_id is not the derived speakerId"

    def test_server_in_group_record_matches_the_derived_flag(self, trials):
        listeners = trials[(trials["role"] == "listener") & trials["serverInGroupListener"].notna()]
        if listeners.empty:
            pytest.skip("serverInGroupListener is empty in this dataset (the pilot exports predate it)")
        server = _truthy(listeners["serverInGroupListener"])
        derived = _truthy(listeners["inGroupSpeaker"])
        assert (server == derived).all(), (
            f"{int((server != derived).sum())} listener rows where in_group_listener disagrees with inGroupSpeaker"
        )

    def test_server_group_size_matches_the_derived_size(self, trials):
        recorded = trials[trials["serverGroupSize"].notna()]
        if recorded.empty:
            pytest.skip("serverGroupSize is empty in this dataset (the pilot exports predate it)")
        assert (recorded["serverGroupSize"].astype(int) == recorded["groupSize"].astype(int)).all(), (
            "the server's group_size disagrees with the number of players in the group"
        )

    def test_reshuffle_counts_agree_with_the_trios(self, trials):
        """The reshuffle's own tally (groups, trios, trios with one in-group
        listener, pairs) must describe the groups the trials show."""
        recorded = trials[trials["reshuffleGroups"].notna()]
        if recorded.empty:
            pytest.skip("reshuffle counts were not recorded in this dataset (the pilot exports predate them)")
        for (gid, rid), r in recorded.groupby(["gameId", "roundId"]):
            groups = [g for _, g in r.groupby("currentGroup")]
            trios = [g for g in groups if len(g) == GROUP_SIZE]
            trios_ok = [
                g for g in trios
                if _truthy(g[g["role"] == "listener"]["inGroupSpeaker"]).sum() == 1
            ]
            pairs = [g for g in groups if len(g) == 2]
            first = r.iloc[0]
            expected = (len(groups), len(trios), len(trios_ok), len(pairs))
            actual = tuple(
                int(first[c]) for c in ("reshuffleGroups", "reshuffleTrios", "reshuffleTriosOk", "reshufflePairs")
            )
            assert actual == expected, (
                f"Game {gid}, round {rid}: reshuffle counts (groups, trios, ok, pairs) = {actual}, "
                f"but the trials show {expected}"
            )

    def test_reshuffle_mode_agrees_with_the_trio_composition(self, trials):
        """Where the server recorded a reshuffle mode (full sample), 'constrained'
        must mean every group that trial was a trio with exactly one in-group
        listener, and 'reduced' must mean at least one was not."""
        recorded = trials[trials["reshuffleMode"].notna()]
        if recorded.empty:
            pytest.skip("reshuffleMode was not recorded in this dataset (pilot exports predate it)")
        for (gid, rid), r in recorded.groupby(["gameId", "roundId"]):
            all_ok = all(
                len(g) == GROUP_SIZE
                and _truthy(g[g["role"] == "listener"]["inGroupSpeaker"]).sum() == 1
                for _, g in r.groupby("currentGroup")
            )
            mode = r["reshuffleMode"].iloc[0]
            assert mode in {"constrained", "reduced"}, f"Game {gid}, round {rid}: unknown mode {mode}"
            assert (mode == "constrained") == all_ok, (
                f"Game {gid}, round {rid}: reshuffleMode={mode} but the trios say {'constrained' if all_ok else 'reduced'}"
            )


class TestParticipantExclusions:
    """`excluded` / `exclusionReason` on trials.csv and social_guesses.csv.

    An exclusion is never silent: every flagged row has a reason, an unflagged
    row has none, every listener of an excluded speaker is flagged with them,
    and the opportunity frame agrees with the trials it was built from.
    """

    def test_columns_are_consistent_on_trials(self, trials):
        assert set(trials["excluded"].dropna().unique()) <= {True, False}
        reason = trials["exclusionReason"].fillna("")
        assert (_truthy(trials["excluded"]) == (reason != "")).all(), (
            "every excluded row needs a reason and no other row may have one"
        )
        excluded_players = set(trials.loc[_truthy(trials["excluded"]) & ~reason.str.startswith("speaker excluded"), "playerId"])
        listeners = trials[(trials["role"] == "listener") & trials["speakerId"].isin(excluded_players)]
        assert _truthy(listeners["excluded"]).all(), "a listener of an excluded speaker is not flagged"
        own = trials[trials["playerId"].isin(excluded_players)]
        assert _truthy(own["excluded"]).all()

    def test_social_guesses_agree_with_trials(self, social_guesses, trials):
        if social_guesses.empty:
            pytest.skip("no social-guessing games in this dataset")
        keys = ["gameId", "playerId", "roundId"]
        merged = social_guesses[keys + ["excluded"]].merge(
            trials[keys + ["excluded"]], on=keys, suffixes=("", "Trial")
        )
        assert len(merged) == len(social_guesses)
        assert (_truthy(merged["excluded"]) == _truthy(merged["excludedTrial"])).all()

    def test_excluded_players_have_no_messages_or_utterances(
        self, trials, messages, speaker_utterances
    ):
        reason = trials["exclusionReason"].fillna("")
        excluded_players = set(
            trials.loc[_truthy(trials["excluded"]) & ~reason.str.startswith("speaker excluded"), "playerId"]
        )
        if not excluded_players:
            pytest.skip("no participant exclusions in this dataset")
        assert not messages["senderId"].isin(excluded_players).any()
        assert not speaker_utterances["playerId"].isin(excluded_players).any()


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
            if cond not in MIXED_CONDITIONS:
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
            if cond not in MIXED_CONDITIONS:
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
    For social conditions: bonus = (score + social_points) * 0.023
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
        """For social conditions, bonus should be >= score * BONUS_PER_POINT_SOCIAL.

        The bonus includes social points on top of the base score, so
        bonus >= score * BONUS_PER_POINT_SOCIAL. We cannot verify exact
        amounts because speaker social points are not in the preprocessed data.
        """
        for _, p in active_players.iterrows():
            cond = game_condition_map.get(p["gameId"])
            if cond not in SOCIAL_CONDITIONS:
                continue
            min_bonus = p["score"] * BONUS_PER_POINT_SOCIAL
            assert p["bonus"] >= min_bonus - 0.01, (
                f"Player {p['originalName']} ({cond}): bonus {p['bonus']} "
                f"is less than minimum expected {min_bonus:.2f} "
                f"(score {p['score']} * {BONUS_PER_POINT_SOCIAL})"
            )

    def test_social_condition_bonus_exact(
        self, active_players, game_condition_map
    ):
        """For social conditions, bonus should equal score * BONUS_PER_POINT_SOCIAL.

        The server adds social-guess points directly INTO the cumulative
        score before converting to a bonus, so the score already contains
        them -- the bonus is exactly score * rate, same as refer conditions.
        """
        for _, p in active_players.iterrows():
            cond = game_condition_map.get(p["gameId"])
            if cond not in SOCIAL_CONDITIONS:
                continue
            expected = p["score"] * BONUS_PER_POINT_SOCIAL
            assert abs(p["bonus"] - expected) < 0.01, (
                f"Player {p['originalName']} ({cond}): bonus {p['bonus']} != "
                f"expected {expected:.3f} (score {p['score']} * "
                f"{BONUS_PER_POINT_SOCIAL})"
            )


# ============ 11. SOCIAL GUESSING ============


class TestSocialGuessing:
    """Validate social guessing data."""

    def test_social_guesses_only_in_social_conditions(
        self, social_guesses, game_condition_map
    ):
        """Social guesses should only exist for social_mixed or social_first games."""
        for gid in social_guesses["gameId"].unique():
            cond = game_condition_map.get(gid)
            assert cond in SOCIAL_CONDITIONS, (
                f"Social guesses found for game {gid} with condition "
                f"'{cond}', expected 'social_mixed' or 'social_first'"
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
        """A submitted guess is 'same_group' or 'different_group'.

        social_guesses.csv is an opportunity frame, so a listener who never
        answered is a row with an empty guess; those are the denominator's
        unsuccessful responses, not invalid values.
        """
        submitted = social_guesses["socialGuess"].dropna()
        invalid = set(submitted.unique()) - VALID_SOCIAL_GUESSES
        assert not invalid, f"Invalid social guess values: {invalid}"

    def test_social_timeout_matches_missing_guess(self, social_guesses):
        """socialTimeout is exactly the rows with no submitted guess."""
        expected = social_guesses["socialGuess"].isna()
        assert (social_guesses["socialTimeout"] == expected).all(), (
            "socialTimeout disagrees with whether a guess was submitted"
        )

    def test_social_opportunities_cover_eligible_listener_trials(
        self, social_guesses, trials, games
    ):
        """One row per Phase 2 listener trial of every social-guessing game.

        The accuracy denominator is response opportunities, so the frame has
        to hold every eligible listener, answered or not. A missing row would
        silently shrink the denominator.
        """
        social_games = set(
            games.loc[
                games["condition"].isin(["social_mixed", "social_first"]), "gameId"
            ]
        )
        if not social_games:
            pytest.skip("no social-guessing games in this dataset")
        expected = trials[
            (trials["role"] == "listener")
            & (trials["phaseNum"] == 2)
            & (trials["gameId"].isin(social_games))
        ]
        expected_keys = set(
            zip(expected["gameId"], expected["playerId"], expected["roundId"])
        )
        actual_keys = set(
            zip(
                social_guesses["gameId"],
                social_guesses["playerId"],
                social_guesses["roundId"],
            )
        )
        assert actual_keys == expected_keys, (
            f"{len(expected_keys - actual_keys)} eligible listener trials are "
            f"missing from social_guesses.csv and "
            f"{len(actual_keys - expected_keys)} extra rows are present"
        )

    def test_social_response_opportunity_requires_a_speaker_message(
        self, social_guesses
    ):
        """responseOpportunity holds exactly where the speaker spoke."""
        assert (
            social_guesses["responseOpportunity"]
            == social_guesses["hasSpeakerMessage"]
        ).all(), "social responseOpportunity disagrees with hasSpeakerMessage"

    def test_speaker_was_same_group_is_the_ground_truth_the_guess_was_scored_on(
        self, social_guesses, trials
    ):
        """The server's record of whether the speaker shared the listener's
        original group must match the groups in trials.csv, and the scored
        correctness must be exactly guess-versus-record."""
        recorded = social_guesses[social_guesses["speakerWasSameGroup"].notna()]
        if recorded.empty:
            pytest.skip("speakerWasSameGroup is empty in this dataset")
        og = trials.drop_duplicates("playerId").set_index("playerId")["originalGroup"]
        truth = recorded["originalGroup"] == recorded["speakerId"].map(og)
        assert (_truthy(recorded["speakerWasSameGroup"]) == truth).all(), (
            "speakerWasSameGroup disagrees with the speaker's original group"
        )
        guessed_same = recorded["socialGuess"] == "same_group"
        expected_correct = _truthy(recorded["speakerWasSameGroup"]) == guessed_same
        scored = recorded[recorded["socialGuessCorrect"].notna()]
        assert (_truthy(scored["socialGuessCorrect"]) == expected_correct[scored.index]).all(), (
            "socialGuessCorrect is not the guess compared with speakerWasSameGroup"
        )

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

    def test_filtered_utterances_have_text_and_are_a_subset(self, speaker_utterances):
        """The non-referential filter drops rounds with no referential message.

        The preregistration treats a trial whose speaker messages were all
        non-referential like a trial with no message, so the filtered file
        must contain no empty utterances and no rounds absent from the
        unfiltered file.
        """
        path = DATA_DIR / "speaker_utterances_filtered.csv"
        if not path.exists():
            pytest.skip("speaker_utterances_filtered.csv not present")
        filtered = pd.read_csv(path)
        filtered = filtered[filtered["gameId"].isin(speaker_utterances["gameId"].unique())]
        empty = filtered["utterance"].isna() | (filtered["utterance"].astype(str).str.strip() == "")
        assert not empty.any(), f"Found {int(empty.sum())} empty utterances in the filtered file"
        keys = ["gameId", "playerId", "phaseNum", "blockNum", "target"]
        merged = filtered[keys].merge(speaker_utterances[keys], on=keys, how="left", indicator=True)
        assert (merged["_merge"] == "both").all(), "Filtered utterances include rounds missing from the unfiltered file"
        assert len(filtered) <= len(speaker_utterances)


# ============ 13. REPNUM ============


class TestRepNum:
    """Validate repetition number tracking for speakers."""

    def test_repnum_starts_at_one(self, trials):
        """repNum should start at 1 for each speaker x tangram x phase.

        Checked on trials (complete), not speaker_utterances: utterances omit
        rounds where the speaker sent no message, so their minimum repNum can
        legitimately be > 1. repNum also resets each phase, so phaseNum must
        be part of the grouping.
        """
        speaker_trials = trials[
            (trials["role"] == "speaker") & (trials["repNum"].notna())
        ]
        grouped = speaker_trials.groupby(
            ["gameId", "playerId", "target", "phaseNum"]
        )
        for (gid, pid, target, pn), group in grouped:
            min_rep = group["repNum"].min()
            assert min_rep == 1, (
                f"Game {gid}, player {pid}, target {target}, phase {pn}: "
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
            ["gameId", "playerId", "target", "phaseNum"]
        )
        for (gid, pid, target, pn), group in grouped:
            reps = group["repNum"].tolist()
            # All should be positive
            assert all(r >= 1 for r in reps), (
                f"Game {gid}, player {pid}, target {target}, phase {pn}: "
                f"repNum has non-positive values: {reps}"
            )
            # All should be unique
            assert len(reps) == len(set(reps)), (
                f"Game {gid}, player {pid}, target {target}, phase {pn}: "
                f"repNum has duplicate values: {reps}"
            )

    def test_repnum_consecutive_in_trials(self, trials):
        """repNum in trials should be consecutive integers from 1..N
        for each speaker x tangram group.
        """
        speaker_trials = trials[
            (trials["role"] == "speaker") & (trials["repNum"].notna())
        ]
        grouped = speaker_trials.groupby(
            ["gameId", "playerId", "target", "phaseNum"]
        )
        for (gid, pid, target, pn), group in grouped:
            reps = sorted(group["repNum"].tolist())
            expected = list(range(1, len(reps) + 1))
            assert reps == expected, (
                f"Game {gid}, player {pid}, target {target}, phase {pn}: "
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

    def test_clicks_imply_speaker_message(self, messages, trials):
        """Every listener click implies a speaker message in that round+group.

        The client blocks tangram clicks until the speaker has sent at least
        one message, so a recorded click with no speaker message in the same
        (roundId, currentGroup) chat means either the click or the message
        data is corrupted.
        """
        clicked = trials[
            (trials["role"] == "listener") & (trials["clicked"].notna())
        ]
        speaker_msg_keys = set(
            zip(
                messages.loc[messages["senderRole"] == "speaker", "roundId"],
                messages.loc[messages["senderRole"] == "speaker", "group"],
            )
        )
        missing = [
            (row["gameId"], row["roundId"], row["currentGroup"])
            for _, row in clicked.iterrows()
            if (row["roundId"], row["currentGroup"]) not in speaker_msg_keys
        ]
        assert not missing, (
            f"{len(missing)} listener clicks have no speaker message in the "
            f"same round+group (first few: {missing[:3]})"
        )

    def test_messages_group_is_valid(self, messages):
        invalid = set(messages["group"].unique()) - VALID_GROUPS
        assert not invalid, f"Messages have invalid group values: {invalid}"

    def test_message_phase2_mixed_sender_names_masked(
        self, messages, game_condition_map
    ):
        """In Phase 2 of mixed conditions, senderName should be 'Player'."""
        for gid, cond in game_condition_map.items():
            if cond not in MIXED_CONDITIONS:
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


class TestResponseOpportunities:
    """The denominator both accuracy outcomes are computed over.

    An eligible response opportunity is an active listener assigned to the
    task on a played trial with a speaker message available during the
    response period. These tests pin the two structural claims the rule
    depends on: that responseOpportunity means what it says, and that a
    removed player stops producing trial rows (which is why "after
    participant removal" needs no separate exclusion).
    """

    def test_response_opportunity_is_listener_with_a_speaker_message(self, trials):
        expected = (trials["role"] == "listener") & trials["hasSpeakerMessage"]
        assert (trials["responseOpportunity"] == expected).all(), (
            "responseOpportunity is not exactly listener & hasSpeakerMessage"
        )

    def test_speakers_are_never_response_opportunities(self, trials):
        speakers = trials[trials["role"] == "speaker"]
        assert not speakers["responseOpportunity"].any(), (
            "a speaker row was marked as a listener response opportunity"
        )

    def test_has_speaker_message_matches_the_messages_table(self, trials, messages):
        spoke = set(
            zip(
                messages.loc[messages["senderRole"] == "speaker", "roundId"],
                messages.loc[messages["senderRole"] == "speaker", "group"],
            )
        )
        expected = [
            (row["roundId"], row["currentGroup"]) in spoke
            for _, row in trials.iterrows()
        ]
        mismatched = (trials["hasSpeakerMessage"] != expected).sum()
        assert mismatched == 0, (
            f"{mismatched} trials disagree with the messages table about "
            f"whether their group's speaker spoke"
        )

    def test_removed_players_produce_no_later_trials(self, trials, players):
        """A removed player contributes no trial rows after their removal.

        The response-opportunity rule excludes trials "after participant
        removal or game termination" structurally rather than by a filter,
        because Empirica only writes a playerRound record for a player who is
        still in the game and was assigned a role. If that ever stopped being
        true, those rows would be counted as failures instead of excluded.
        """
        removed = players[players["exitReason"].notna()]
        if removed.empty:
            pytest.skip("no removed players in this dataset")
        for _, player in removed.iterrows():
            own = trials[trials["playerId"] == player["playerId"]]
            if own.empty:
                continue
            game_trials = trials[trials["gameId"] == player["gameId"]]
            last_round = own["trialNum"].max()
            # Somebody in the game played on after this player stopped, or the
            # player simply lasted to the end; either way they must not have
            # rows interleaved with a gap.
            played = sorted(own["trialNum"].dropna().unique())
            expected_run = sorted(
                game_trials.loc[
                    game_trials["trialNum"] <= last_round, "trialNum"
                ]
                .dropna()
                .unique()
            )
            assert played == expected_run, (
                f"Player {player['playerId']} ({player['exitReason']}) has "
                f"gaps in their trials: played {len(played)} of "
                f"{len(expected_run)} rounds up to their last"
            )

    def test_late_clicks_are_unscored(self, trials):
        """A selection that arrived after the deadline earns no score.

        The rule counts a late arrival as unsuccessful, which is only right
        if the server really did leave it unscored.
        """
        late = trials[trials["lateClick"] == True]  # noqa: E712
        if late.empty:
            pytest.skip("no late clicks in this dataset")
        scored = late[late["clickedCorrect"].notna()]
        assert scored.empty, (
            f"{len(scored)} late clicks were scored by the server; the "
            f"analysis assumes scoring is final at the deadline"
        )


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

    def test_social_guesses_game_is_social_condition(
        self, social_guesses, game_condition_map
    ):
        """All social guess game IDs should be for social_mixed or social_first."""
        for gid in social_guesses["gameId"].unique():
            cond = game_condition_map.get(gid)
            assert cond in SOCIAL_CONDITIONS, (
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
        self, active_players, trials, game_condition_map
    ):
        """Player's cumulative score should reconcile with trial roundScores.

        For refer conditions, score == sum of roundScore (float tolerance).
        For social conditions the cumulative score also contains social-guess
        points, which are NOT in trials.roundScore (listener social points are
        in social_guesses.csv; speaker social points are not exported at all),
        so only score >= sum of roundScore can be asserted.
        """
        for _, p in active_players.iterrows():
            player_trials = trials[trials["playerId"] == p["playerId"]]
            trial_score_sum = player_trials["roundScore"].sum()
            cond = game_condition_map.get(p["gameId"])
            if cond in SOCIAL_CONDITIONS:
                assert p["score"] >= trial_score_sum - 0.5, (
                    f"Player {p['originalName']} ({cond}): cumulative score "
                    f"{p['score']} < sum of trial roundScores {trial_score_sum}"
                )
            else:
                assert abs(p["score"] - trial_score_sum) < 0.5, (
                    f"Player {p['originalName']} ({cond}): cumulative score "
                    f"{p['score']} != sum of trial roundScores {trial_score_sum}"
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
                # Count unique blocks with ANY role rather than summing
                # speaker blocks + listener blocks: after a dropout, speaker
                # reassignment can make a player both speak and listen within
                # the same block, which would double-count it.
                total = phase_trials["blockNum"].nunique()
                assert total == PHASE_1_BLOCKS, (
                    f"Player {p['originalName']}, Phase {pn}: participated in "
                    f"{total} blocks, expected {PHASE_1_BLOCKS}"
                )


# ============ 18. TANGRAM IDENTITY ============


class TestTangramIdentity:
    """Validate tangram identifiers match the tangram set."""

    TANGRAM_SETS = {
        0: {
            "page7-255", "page9-46", "page5-28",
            "page7-107", "page3-35", "page-B",
        },
        1: {
            "page3-121", "page4-157", "page7-26",
            "page5-64", "page6-149", "page3-193",
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

    def test_dropouts_file_exists_and_is_disjoint_from_players(self, players):
        """dropouts.csv (written by combine_runs.py) lists every player record
        with no real game -- quiz failures, lobby timeouts, arrivals after the
        games were full -- so attrition can be reported. It always exists, at
        least as a header, and never overlaps players.csv."""
        path = DATA_DIR / "dropouts.csv"
        assert path.exists(), "dropouts.csv is missing; rerun combine_runs.py"
        dropouts = pd.read_csv(path)
        assert dropouts.columns.tolist() == ["playerId", "batchId", "ended", "exitReason", "quizAttempts"]
        assert not dropouts["playerId"].isin(set(players["playerId"])).any(), (
            "a dropout record is also in players.csv"
        )
        assert dropouts["playerId"].is_unique
        assert pd.to_numeric(dropouts["quizAttempts"], errors="raise").dropna().between(1, 3).all()

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
        # Allow some missing clicks: idle rounds, speaker timeouts (listeners
        # cannot click before the speaker messages), and removals. The pilot
        # runs at 5.2%, so the cap is set with headroom while still catching
        # systematic click-recording failures.
        missing_pct = missing_click / total_listeners if total_listeners > 0 else 0
        assert missing_pct < 0.10, (
            f"{missing_click}/{total_listeners} ({missing_pct:.1%}) listener "
            f"trials missing click data"
        )


# ============ 19. SESSION INSTRUMENTATION ============


class TestSessionInstrumentation:
    """Timing, device, and engagement records added in September 2026.

    The pilot predates all of it, so every check here skips on an empty
    column rather than failing. They exist to catch the full sample going
    wrong: a response time that runs backwards, a clock that jumped, or a
    condition that silently stopped recording.
    """

    def test_the_timing_columns_exist_whatever_the_export_vintage(self, trials, players):
        for column in (
            "tangramSelectedAt",
            "selectionRenderedAt",
            "selectionRt",
            "selectionStartedAt",
            "selectionEndedAt",
            "selectionDurationMs",
        ):
            assert column in trials.columns, f"trials.csv is missing {column}"
        for column in ("minutesSpent", "quizAttempts", "tabHiddenCount"):
            assert column in players.columns, f"players.csv is missing {column}"

    def test_response_times_are_positive(self, trials):
        """A choice cannot precede the stage appearing on the same screen."""
        rt = trials["selectionRt"].dropna()
        if rt.empty:
            pytest.skip("no response times recorded (export predates them)")
        negative = rt[rt < 0]
        assert len(negative) == 0, (
            f"{len(negative)} trials have a negative response time; the "
            "participant's clock moved backwards mid-session"
        )

    def test_response_times_fit_inside_the_selection_stage(self, trials):
        """A response time longer than the stage means the clocks disagree.

        Both ends of selectionRt come from the participant's browser and the
        stage duration from the server, so a gross mismatch is the signal that
        one of those clocks is untrustworthy for that session.
        """
        both = trials[["selectionRt", "selectionDurationMs"]].dropna()
        if both.empty:
            pytest.skip("no response times recorded (export predates them)")
        # One second of slack for the round trip that commits the selection.
        over = both[both["selectionRt"] > both["selectionDurationMs"] + 1000]
        assert len(over) == 0, (
            f"{len(over)} trials have a response time longer than the stage "
            "they were made in"
        )

    def test_the_selection_is_never_committed_before_it_was_made(self, trials):
        """clickedAt is the commit; tangramSelectedAt is the choice."""
        both = trials[["clickedAt", "tangramSelectedAt"]].dropna()
        if both.empty:
            pytest.skip("no selection timestamps recorded")
        early = both[both["clickedAt"] < both["tangramSelectedAt"]]
        assert len(early) == 0, (
            f"{len(early)} trials were committed before the choice was made"
        )

    def test_every_condition_records_the_choice_time(self, trials, game_condition_map):
        """The social conditions commit on submit rather than on click.

        That difference is exactly why tangramSelectedAt exists, so a
        condition missing it would silently break every cross-condition
        response-time comparison.
        """
        clicked = trials[trials["clicked"].notna()].copy()
        if clicked["tangramSelectedAt"].dropna().empty:
            pytest.skip("no selection timestamps recorded")
        clicked["condition"] = clicked["gameId"].map(game_condition_map)
        for condition, rows in clicked.groupby("condition"):
            assert rows["tangramSelectedAt"].notna().any(), (
                f"condition {condition} recorded no choice times at all"
            )

    def test_composition_time_is_positive_and_within_the_round(self, messages):
        if "composeMs" not in messages.columns:
            pytest.skip("messages.csv predates composition timing")
        compose = messages["composeMs"].dropna()
        if compose.empty:
            pytest.skip("no composition times recorded")
        assert (compose >= 0).all(), "a message was sent before it was started"

    def test_hidden_time_is_never_negative(self, players):
        hidden = players["tabHiddenMs"].dropna()
        if hidden.empty:
            pytest.skip("no engagement log recorded")
        assert (hidden >= 0).all(), "negative tab-hidden time"

    def test_time_on_task_is_recorded_for_everyone_who_finished(self, players):
        """Finishers get an end time from onGameEnded, not just removals.

        The pilot has none, which is the gap this checks has not returned.
        """
        finished = players[players["isActive"] == True]
        if finished.empty or finished["minutesSpent"].dropna().empty:
            pytest.skip("export predates end-of-game time on task")
        missing = finished["minutesSpent"].isna().sum()
        assert missing == 0, (
            f"{missing} players who finished have no time on task"
        )
