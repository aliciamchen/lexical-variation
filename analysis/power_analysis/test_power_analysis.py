import pytest
import numpy as np
import pandas as pd
import random


def generate_subgroups(speaker_data, min_players=4, seed=42):
    """
    Generate subgroups from speaker_data by splitting players within each game
    and pairing subgroups from different games.

    Returns:
        speaker_data_separate: DataFrame with new gameId and groupID columns
        paired_groups: List of paired group info (for testing)
        subgroups: List of all subgroups created (for testing)
    """
    np.random.seed(seed)
    random.seed(seed)

    games = speaker_data['gameId'].unique()

    # Step 1: For each game with min_players+ players, partition into two subgroups
    subgroups = []
    for game in games:
        game_data = speaker_data[speaker_data['gameId'] == game]
        players = game_data['speaker'].unique()

        if len(players) < min_players:
            continue

        players_shuffled = np.random.permutation(players)
        mid = len(players_shuffled) // 2
        subgroup_0_players = list(players_shuffled[:mid + len(players_shuffled) % 2])
        subgroup_1_players = list(players_shuffled[mid + len(players_shuffled) % 2:])

        if len(subgroup_0_players) > 0:
            subgroups.append({'original_game': game, 'players': subgroup_0_players})
        if len(subgroup_1_players) > 0:
            subgroups.append({'original_game': game, 'players': subgroup_1_players})

    # Step 2: Randomly pair subgroups from different games
    random.shuffle(subgroups)

    paired_groups = []
    used = set()
    new_game_id = 0

    for i in range(len(subgroups)):
        if i in used:
            continue
        for j in range(i + 1, len(subgroups)):
            if j in used:
                continue
            if subgroups[i]['original_game'] != subgroups[j]['original_game']:
                paired_groups.append({
                    'new_game_id': new_game_id,
                    'subgroup_0': subgroups[i],
                    'subgroup_1': subgroups[j]
                })
                used.add(i)
                used.add(j)
                new_game_id += 1
                break

    # Step 3: Create the new dataframe
    rows = []
    for group in paired_groups:
        new_gid = group['new_game_id']

        for group_id, subgroup_key in enumerate(['subgroup_0', 'subgroup_1']):
            subgroup = group[subgroup_key]
            for player in subgroup['players']:
                mask = ((speaker_data['gameId'] == subgroup['original_game']) &
                        (speaker_data['speaker'] == player))
                player_data = speaker_data[mask].copy()
                player_data['new_gameId'] = new_gid
                player_data['groupID'] = group_id
                rows.append(player_data)

    if rows:
        speaker_data_separate = pd.concat(rows, ignore_index=True)
        speaker_data_separate['gameId'] = speaker_data_separate['new_gameId']
        speaker_data_separate = speaker_data_separate.drop(columns=['new_gameId'])
    else:
        speaker_data_separate = pd.DataFrame()

    return speaker_data_separate, paired_groups, subgroups


@pytest.fixture
def mock_speaker_data():
    """Create mock speaker data with games of varying player counts."""
    rows = []

    # Game A: 6 players (should be included)
    for player in ['A1', 'A2', 'A3', 'A4', 'A5', 'A6']:
        for trial in range(3):
            rows.append({
                'gameId': 'game_A',
                'speaker': player,
                'trialNum': trial,
                'repNum': 0,
                'target': 'X',
                'speaker_utt': f'utterance from {player}',
                'countCorrect': 5
            })

    # Game B: 6 players (should be included)
    for player in ['B1', 'B2', 'B3', 'B4', 'B5', 'B6']:
        for trial in range(3):
            rows.append({
                'gameId': 'game_B',
                'speaker': player,
                'trialNum': trial,
                'repNum': 0,
                'target': 'X',
                'speaker_utt': f'utterance from {player}',
                'countCorrect': 5
            })

    # Game C: 4 players (should be included, edge case)
    for player in ['C1', 'C2', 'C3', 'C4']:
        for trial in range(3):
            rows.append({
                'gameId': 'game_C',
                'speaker': player,
                'trialNum': trial,
                'repNum': 0,
                'target': 'X',
                'speaker_utt': f'utterance from {player}',
                'countCorrect': 5
            })

    # Game D: 3 players (should be excluded)
    for player in ['D1', 'D2', 'D3']:
        for trial in range(3):
            rows.append({
                'gameId': 'game_D',
                'speaker': player,
                'trialNum': trial,
                'repNum': 0,
                'target': 'X',
                'speaker_utt': f'utterance from {player}',
                'countCorrect': 5
            })

    # Game E: 1 player (should be excluded)
    for trial in range(3):
        rows.append({
            'gameId': 'game_E',
            'speaker': 'E1',
            'trialNum': trial,
            'repNum': 0,
            'target': 'X',
            'speaker_utt': 'utterance from E1',
            'countCorrect': 5
        })

    return pd.DataFrame(rows)


@pytest.fixture
def mock_speaker_data_minimal():
    """Create minimal mock data with exactly 2 games of 4 players each."""
    rows = []

    for game_id, game_prefix in [('game_1', 'P1'), ('game_2', 'P2')]:
        for i in range(4):
            player = f'{game_prefix}_{i}'
            for trial in range(2):
                rows.append({
                    'gameId': game_id,
                    'speaker': player,
                    'trialNum': trial,
                    'repNum': 0,
                    'target': 'X',
                    'speaker_utt': f'utterance from {player}',
                    'countCorrect': 5
                })

    return pd.DataFrame(rows)


class TestOnlyGamesWithMinPlayersUsed:
    """Test that only games with 4+ players are used."""

    def test_games_with_fewer_than_4_players_excluded(self, mock_speaker_data):
        result, paired_groups, subgroups = generate_subgroups(mock_speaker_data)

        # Get original games that made it into subgroups
        original_games_used = set(s['original_game'] for s in subgroups)

        # Games D and E should be excluded (3 and 1 players respectively)
        assert 'game_D' not in original_games_used
        assert 'game_E' not in original_games_used

    def test_games_with_4_or_more_players_included(self, mock_speaker_data):
        result, paired_groups, subgroups = generate_subgroups(mock_speaker_data)

        original_games_used = set(s['original_game'] for s in subgroups)

        # Games A, B, C should be included (6, 6, 4 players)
        assert 'game_A' in original_games_used
        assert 'game_B' in original_games_used
        assert 'game_C' in original_games_used

    def test_edge_case_exactly_4_players(self, mock_speaker_data):
        result, paired_groups, subgroups = generate_subgroups(mock_speaker_data)

        # Find subgroups from game_C (4 players)
        game_c_subgroups = [s for s in subgroups if s['original_game'] == 'game_C']

        assert len(game_c_subgroups) == 2
        # With 4 players, should split 2+2
        assert len(game_c_subgroups[0]['players']) == 2
        assert len(game_c_subgroups[1]['players']) == 2


class TestSubgroupPlayerCounts:
    """Test that each subgroup has at least 2 players."""

    def test_all_subgroups_have_at_least_2_players(self, mock_speaker_data):
        result, paired_groups, subgroups = generate_subgroups(mock_speaker_data)

        for subgroup in subgroups:
            assert len(subgroup['players']) >= 2, \
                f"Subgroup from {subgroup['original_game']} has only {len(subgroup['players'])} players"

    def test_6_player_game_splits_into_3_and_3(self, mock_speaker_data):
        result, paired_groups, subgroups = generate_subgroups(mock_speaker_data)

        game_a_subgroups = [s for s in subgroups if s['original_game'] == 'game_A']

        assert len(game_a_subgroups) == 2
        player_counts = sorted([len(s['players']) for s in game_a_subgroups])
        assert player_counts == [3, 3]


class TestPairedSubgroupsFromDifferentGames:
    """Test that paired subgroups come from different original games."""

    def test_no_same_game_pairings(self, mock_speaker_data):
        result, paired_groups, subgroups = generate_subgroups(mock_speaker_data)

        for group in paired_groups:
            game_0 = group['subgroup_0']['original_game']
            game_1 = group['subgroup_1']['original_game']
            assert game_0 != game_1, \
                f"Paired subgroups are from the same game: {game_0}"

    def test_minimal_case_two_games(self, mock_speaker_data_minimal):
        result, paired_groups, subgroups = generate_subgroups(mock_speaker_data_minimal)

        # With 2 games, we should get 2 paired groups
        assert len(paired_groups) == 2

        for group in paired_groups:
            assert group['subgroup_0']['original_game'] != group['subgroup_1']['original_game']


class TestGroupIDValues:
    """Test that groupID values are 0 and 1."""

    def test_group_id_values_are_0_and_1(self, mock_speaker_data):
        result, paired_groups, subgroups = generate_subgroups(mock_speaker_data)

        unique_group_ids = set(result['groupID'].unique())
        assert unique_group_ids == {0, 1}

    def test_each_new_game_has_both_group_ids(self, mock_speaker_data):
        result, paired_groups, subgroups = generate_subgroups(mock_speaker_data)

        for game_id in result['gameId'].unique():
            game_data = result[result['gameId'] == game_id]
            group_ids = set(game_data['groupID'].unique())
            assert group_ids == {0, 1}, \
                f"Game {game_id} does not have both groupID 0 and 1"


class TestPlayerDataPreserved:
    """Test that all original player data is preserved."""

    def test_all_rows_for_included_players_preserved(self, mock_speaker_data):
        result, paired_groups, subgroups = generate_subgroups(mock_speaker_data)

        # Get all players that should be in the result
        included_players = set()
        for subgroup in subgroups:
            if any(subgroup == g['subgroup_0'] or subgroup == g['subgroup_1']
                   for g in paired_groups):
                included_players.update(subgroup['players'])

        # For each included player, check all their original rows are present
        for player in included_players:
            original_rows = mock_speaker_data[mock_speaker_data['speaker'] == player]
            result_rows = result[result['speaker'] == player]

            assert len(result_rows) == len(original_rows), \
                f"Player {player} has {len(result_rows)} rows but expected {len(original_rows)}"

    def test_original_columns_preserved(self, mock_speaker_data):
        result, paired_groups, subgroups = generate_subgroups(mock_speaker_data)

        original_cols = set(mock_speaker_data.columns)
        result_cols = set(result.columns)

        # Result should have all original columns plus groupID
        assert original_cols.issubset(result_cols)
        assert 'groupID' in result_cols

    def test_utterance_content_unchanged(self, mock_speaker_data):
        result, paired_groups, subgroups = generate_subgroups(mock_speaker_data)

        # Check a sample of utterances
        for _, row in result.head(10).iterrows():
            speaker = row['speaker']
            expected_utt = f'utterance from {speaker}'
            assert row['speaker_utt'] == expected_utt


class TestNewGameIdValues:
    """Test that new gameId values are integers starting from 0."""

    def test_game_ids_are_integers(self, mock_speaker_data):
        result, paired_groups, subgroups = generate_subgroups(mock_speaker_data)

        for game_id in result['gameId'].unique():
            assert isinstance(game_id, (int, np.integer)), \
                f"gameId {game_id} is not an integer"

    def test_game_ids_start_from_0(self, mock_speaker_data):
        result, paired_groups, subgroups = generate_subgroups(mock_speaker_data)

        assert 0 in result['gameId'].values

    def test_game_ids_are_consecutive(self, mock_speaker_data):
        result, paired_groups, subgroups = generate_subgroups(mock_speaker_data)

        game_ids = sorted(result['gameId'].unique())
        expected = list(range(len(game_ids)))
        assert game_ids == expected


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_input(self):
        empty_df = pd.DataFrame(columns=['gameId', 'speaker', 'trialNum', 'repNum',
                                          'target', 'speaker_utt', 'countCorrect'])
        result, paired_groups, subgroups = generate_subgroups(empty_df)

        assert len(result) == 0
        assert len(paired_groups) == 0
        assert len(subgroups) == 0

    def test_single_game_no_pairing_possible(self):
        """With only one game, no cross-game pairing is possible."""
        rows = []
        for player in ['P1', 'P2', 'P3', 'P4']:
            rows.append({
                'gameId': 'only_game',
                'speaker': player,
                'trialNum': 0,
                'repNum': 0,
                'target': 'X',
                'speaker_utt': f'utterance from {player}',
                'countCorrect': 5
            })
        single_game_df = pd.DataFrame(rows)

        result, paired_groups, subgroups = generate_subgroups(single_game_df)

        # Subgroups should be created but no pairing possible
        assert len(subgroups) == 2
        assert len(paired_groups) == 0
        assert len(result) == 0

    def test_reproducibility_with_same_seed(self, mock_speaker_data):
        result1, _, _ = generate_subgroups(mock_speaker_data, seed=42)
        result2, _, _ = generate_subgroups(mock_speaker_data, seed=42)

        pd.testing.assert_frame_equal(result1.reset_index(drop=True),
                                       result2.reset_index(drop=True))

    def test_different_seeds_produce_different_results(self, mock_speaker_data):
        result1, _, _ = generate_subgroups(mock_speaker_data, seed=42)
        result2, _, _ = generate_subgroups(mock_speaker_data, seed=123)

        # Results should differ (player assignments or pairings)
        # Check if the groupID assignments differ for at least some players
        merged = result1.merge(result2, on=['speaker', 'trialNum'], suffixes=('_1', '_2'))
        different_assignments = (merged['groupID_1'] != merged['groupID_2']).any()
        different_games = (merged['gameId_1'] != merged['gameId_2']).any()

        assert different_assignments or different_games


# ============================================================================
# Tests for compute_pairwise_similarities
# ============================================================================

from itertools import combinations


def compute_pairwise_similarities(df, embeddings, model):
    """
    For each game and tangram, compute similarity between all pairs of speakers
    who described that tangram.

    Returns a DataFrame with columns:
    - gameId, target
    - speaker_1, speaker_2
    - repNum_1, repNum_2
    - groupID_1, groupID_2
    - same_group (1 if both speakers in same group, 0 otherwise)
    - similarity (cosine similarity)
    - participant_pair (unique identifier for the pair)
    """
    rows = []

    for (game, target), group_data in df.groupby(['gameId', 'target']):
        speakers = group_data['speaker'].unique()

        if len(speakers) < 2:
            continue

        for s1, s2 in combinations(speakers, 2):
            s1_data = group_data[group_data['speaker'] == s1].iloc[0]
            s2_data = group_data[group_data['speaker'] == s2].iloc[0]

            emb1 = embeddings[s1_data['embedding_idx']]
            emb2 = embeddings[s2_data['embedding_idx']]
            sim = model.similarity(emb1, emb2).item()

            same_group = 1 if s1_data['groupID'] == s2_data['groupID'] else 0

            pair = tuple(sorted([s1, s2]))
            participant_pair = f"{pair[0]}_{pair[1]}"

            rows.append({
                'gameId': game,
                'target': target,
                'speaker_1': s1,
                'speaker_2': s2,
                'repNum_1': s1_data['repNum'],
                'repNum_2': s2_data['repNum'],
                'groupID_1': s1_data['groupID'],
                'groupID_2': s2_data['groupID'],
                'same_group': same_group,
                'similarity': sim,
                'participant_pair': participant_pair
            })

    return pd.DataFrame(rows)


class MockSBERTModel:
    """Mock SBERT model for testing."""
    def similarity(self, emb1, emb2):
        # Simple dot product similarity for testing
        sim = np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2))
        return MockTensor(sim)


class MockTensor:
    """Mock tensor with .item() method."""
    def __init__(self, value):
        self.value = value

    def item(self):
        return self.value


@pytest.fixture
def pairwise_test_data():
    """Create test data with known structure for pairwise similarity testing."""
    rows = []
    embedding_idx = 0

    # Game 1: 4 speakers, 2 targets, each speaker describes each target once
    for speaker_idx, speaker in enumerate(['S1', 'S2', 'S3', 'S4']):
        group_id = 0 if speaker_idx < 2 else 1  # S1, S2 in group 0; S3, S4 in group 1
        for target in ['A', 'B']:
            rows.append({
                'gameId': 'game_1',
                'speaker': speaker,
                'target': target,
                'repNum': speaker_idx,  # Each speaker has different repNum
                'groupID': group_id,
                'embedding_idx': embedding_idx,
                'speaker_utt': f'utterance from {speaker} for {target}'
            })
            embedding_idx += 1

    # Game 2: 3 speakers, 2 targets
    for speaker_idx, speaker in enumerate(['P1', 'P2', 'P3']):
        group_id = 0 if speaker_idx < 2 else 1
        for target in ['A', 'B']:
            rows.append({
                'gameId': 'game_2',
                'speaker': speaker,
                'target': target,
                'repNum': speaker_idx,
                'groupID': group_id,
                'embedding_idx': embedding_idx,
                'speaker_utt': f'utterance from {speaker} for {target}'
            })
            embedding_idx += 1

    return pd.DataFrame(rows)


@pytest.fixture
def mock_embeddings(pairwise_test_data):
    """Create mock embeddings - same group speakers have more similar embeddings."""
    n_embeddings = len(pairwise_test_data)
    dim = 10
    embeddings = np.random.randn(n_embeddings, dim)

    # Make embeddings more similar within groups
    for game_id in pairwise_test_data['gameId'].unique():
        game_data = pairwise_test_data[pairwise_test_data['gameId'] == game_id]
        for group_id in [0, 1]:
            group_indices = game_data[game_data['groupID'] == group_id]['embedding_idx'].values
            if len(group_indices) > 1:
                # Add a common component to same-group embeddings
                common = np.random.randn(dim) * 2
                for idx in group_indices:
                    embeddings[idx] += common

    # Normalize embeddings
    embeddings = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)
    return embeddings


class TestComputePairwiseSimilarities:
    """Tests for the compute_pairwise_similarities function."""

    def test_returns_dataframe_with_correct_columns(self, pairwise_test_data, mock_embeddings):
        model = MockSBERTModel()
        result = compute_pairwise_similarities(pairwise_test_data, mock_embeddings, model)

        expected_cols = {'gameId', 'target', 'speaker_1', 'speaker_2', 'repNum_1', 'repNum_2',
                        'groupID_1', 'groupID_2', 'same_group', 'similarity', 'participant_pair'}
        assert set(result.columns) == expected_cols

    def test_correct_number_of_pairs(self, pairwise_test_data, mock_embeddings):
        model = MockSBERTModel()
        result = compute_pairwise_similarities(pairwise_test_data, mock_embeddings, model)

        # Game 1: 4 speakers, 2 targets -> C(4,2) * 2 = 6 * 2 = 12 pairs
        # Game 2: 3 speakers, 2 targets -> C(3,2) * 2 = 3 * 2 = 6 pairs
        # Total: 18 pairs
        assert len(result) == 18

    def test_same_group_correctly_assigned(self, pairwise_test_data, mock_embeddings):
        model = MockSBERTModel()
        result = compute_pairwise_similarities(pairwise_test_data, mock_embeddings, model)

        for _, row in result.iterrows():
            expected_same = 1 if row['groupID_1'] == row['groupID_2'] else 0
            assert row['same_group'] == expected_same, \
                f"same_group mismatch for {row['speaker_1']}, {row['speaker_2']}"

    def test_repnums_are_different_between_speakers(self, pairwise_test_data, mock_embeddings):
        model = MockSBERTModel()
        result = compute_pairwise_similarities(pairwise_test_data, mock_embeddings, model)

        # All pairs should have different repNums (since each speaker has unique repNum per game)
        for _, row in result.iterrows():
            assert row['repNum_1'] != row['repNum_2'], \
                f"Same repNum for speakers {row['speaker_1']} and {row['speaker_2']}: {row['repNum_1']}"

    def test_participant_pair_is_consistent(self, pairwise_test_data, mock_embeddings):
        model = MockSBERTModel()
        result = compute_pairwise_similarities(pairwise_test_data, mock_embeddings, model)

        for _, row in result.iterrows():
            pair = tuple(sorted([row['speaker_1'], row['speaker_2']]))
            expected = f"{pair[0]}_{pair[1]}"
            assert row['participant_pair'] == expected

    def test_similarity_values_are_valid(self, pairwise_test_data, mock_embeddings):
        model = MockSBERTModel()
        result = compute_pairwise_similarities(pairwise_test_data, mock_embeddings, model)

        # Cosine similarities should be between -1 and 1
        assert (result['similarity'] >= -1.0).all()
        assert (result['similarity'] <= 1.0).all()

    def test_no_self_comparisons(self, pairwise_test_data, mock_embeddings):
        model = MockSBERTModel()
        result = compute_pairwise_similarities(pairwise_test_data, mock_embeddings, model)

        # No speaker should be compared with themselves
        for _, row in result.iterrows():
            assert row['speaker_1'] != row['speaker_2']

    def test_each_pair_appears_once_per_target(self, pairwise_test_data, mock_embeddings):
        model = MockSBERTModel()
        result = compute_pairwise_similarities(pairwise_test_data, mock_embeddings, model)

        # Check no duplicates within each (gameId, target)
        for (game, target), group_data in result.groupby(['gameId', 'target']):
            pairs = group_data['participant_pair'].tolist()
            assert len(pairs) == len(set(pairs)), \
                f"Duplicate pairs in game {game}, target {target}"

    def test_handles_game_with_single_speaker(self):
        """Game with only one speaker for a target should produce no pairs."""
        rows = [
            {'gameId': 'g1', 'speaker': 'S1', 'target': 'A', 'repNum': 0,
             'groupID': 0, 'embedding_idx': 0, 'speaker_utt': 'test'}
        ]
        df = pd.DataFrame(rows)
        embeddings = np.random.randn(1, 10)
        model = MockSBERTModel()

        result = compute_pairwise_similarities(df, embeddings, model)
        assert len(result) == 0

    def test_same_group_higher_similarity_on_average(self, pairwise_test_data, mock_embeddings):
        """Within-group pairs should have higher similarity (given our mock embeddings)."""
        model = MockSBERTModel()
        result = compute_pairwise_similarities(pairwise_test_data, mock_embeddings, model)

        within_group = result[result['same_group'] == 1]['similarity'].mean()
        between_group = result[result['same_group'] == 0]['similarity'].mean()

        # With our mock embeddings that add common component to same-group, within should be higher
        assert within_group > between_group, \
            f"Expected within-group ({within_group:.3f}) > between-group ({between_group:.3f})"
