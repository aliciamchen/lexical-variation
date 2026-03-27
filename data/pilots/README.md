# Pilot dataset

This directory contains preprocessed analysis-ready CSVs from the pilot experiment sessions. The anonymized raw Empirica exports are in `raw_anonymized/`; the CSVs at this level are produced by the analysis pipeline (see the project README for details).

## games.csv

One row per game session.

| Column | Description |
|--------|-------------|
| `gameId` | Unique game session identifier |
| `condition` | Experimental condition: `refer_separated`, `refer_mixed`, `social_mixed`, or `social_first` |
| `tangramSet` | Which tangram image set was used |
| `numPlayers` | Number of players in the game |
| `activeGroups` | Number of groups that remained active throughout the game |
| `phase1Blocks` | Number of blocks in Phase 1 |
| `phase2Blocks` | Number of blocks in Phase 2 |

## players.csv

One row per player.

| Column | Description |
|--------|-------------|
| `playerId` | Unique player identifier |
| `gameId` | Game session the player was in |
| `name` | Anonymized player name |
| `originalGroup` | Group assigned at game start (A, B, or C) |
| `originalName` | Player's original display name |
| `score` | Total points earned |
| `bonus` | Monetary bonus (score × bonus rate) |
| `isActive` | Whether the player remained active throughout |
| `idleRounds` | Number of rounds the player was idle |
| `exitSurvey_age` | Self-reported age |
| `exitSurvey_gender` | Self-reported gender |
| `exitSurvey_education` | Self-reported education level |
| `exitSurvey_understood` | Free-text: did they understand the game |
| `exitSurvey_fair` | Free-text: was the game fair |
| `exitSurvey_strength` | Free-text: their communication strategy |
| `exitSurvey_feedback` | Free-text: additional comments |

## trials.csv

One row per player per reference game round.

| Column | Description |
|--------|-------------|
| `gameId` | Game session identifier |
| `playerId` | Player identifier |
| `playerName` | Player's display name |
| `originalGroup` | Player's initial group (A, B, or C) |
| `currentGroup` | Player's group at time of this trial (changes in mixed conditions) |
| `role` | `speaker` or `listener` |
| `blockNum` | Block number within the phase |
| `phase` | Always `refgame` (transition stages are excluded) |
| `phaseNum` | 1 or 2 |
| `target` | Target tangram identifier (e.g., `page5-28`) |
| `clicked` | Which tangram the listener clicked (empty for speakers or timeouts) |
| `clickedCorrect` | Whether the listener clicked correctly (NaN for speakers) |
| `roundScore` | Points awarded this round |
| `roundId` | Unique round identifier |
| `timeout` | Whether the round timed out before the listener clicked |
| `trialNum` | Sequential trial number within the game |
| `tangramSet` | Which tangram set was used |
| `repNum` | How many times this speaker has described this target within the current phase (1st, 2nd, etc.). Only present for speakers. |

## messages.csv

One row per chat message, deduplicated across players in a group.

| Column | Description |
|--------|-------------|
| `gameId` | Game session identifier |
| `roundId` | Round the message was sent in |
| `blockNum` | Block number |
| `phase` | Always `refgame` |
| `phaseNum` | 1 or 2 |
| `target` | Target tangram for this round |
| `group` | Group of the sender |
| `senderId` | Player ID of the sender |
| `senderName` | Display name of the sender |
| `senderRole` | `speaker` or `listener` |
| `text` | Message content |
| `timestamp` | Unix millisecond timestamp |
| `trialNum` | Sequential trial number |
| `tangramSet` | Which tangram set |

## messages_classified.csv

Same as `messages.csv` with two additional columns from LLM classification. Only speaker messages are classified; listener messages default to `is_referential = True`.

| Column | Description |
|--------|-------------|
| *(all columns from messages.csv)* | |
| `is_referential` | Whether the message contains information that helps identify the target tangram |
| `llm_label` | Raw LLM output: `R` (referential) or `NR` (non-referential). Empty for listener messages. |

## speaker_utterances.csv

Speaker messages concatenated per round. One row per speaker per round.

| Column | Description |
|--------|-------------|
| `gameId` | Game session identifier |
| `playerId` | Speaker's player ID |
| `originalGroup` | Speaker's initial group |
| `currentGroup` | Speaker's group at time of utterance |
| `tangramSet` | Which tangram set |
| `blockNum` | Block number |
| `trialNum` | Sequential trial number |
| `phase` | Always `refgame` |
| `phaseNum` | 1 or 2 |
| `target` | Target tangram identifier |
| `repNum` | Repetition number for this speaker × target within the phase |
| `utterance` | All speaker messages for this round, joined with ", " |
| `uttLength` | Word count of the utterance |

## speaker_utterances_filtered.csv

Same structure as `speaker_utterances.csv`, but non-referential messages are removed before concatenation. Some rows may have empty utterances if all messages in that round were non-referential.

## social_guesses.csv

Listener guesses about whether the speaker belongs to their original group. Only present in `social_mixed` and `social_first` conditions.

| Column | Description |
|--------|-------------|
| `gameId` | Game session identifier |
| `playerId` | Listener who made the guess |
| `originalGroup` | Listener's initial group |
| `blockNum` | Block number |
| `phase` | Always `refgame` |
| `target` | Target tangram being described |
| `socialGuess` | `same_group` or `different_group` |
| `socialGuessCorrect` | Whether the guess was correct |
| `socialRoundScore` | Points awarded for the guess |
| `tangramSet` | Which tangram set |
