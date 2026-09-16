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
| `ended` | Whether Empirica marked the game as ended |
| `endedReason` | Why the game ended: `end of game` when it ran to completion, `all players removed` when it terminated early |

## players.csv

One row per player.

| Column | Description |
|--------|-------------|
| `playerId` | Unique player identifier |
| `gameId` | Game session the player was in |
| `name` | Anonymized player name |
| `originalGroup` | Group assigned at game start (A, B, or C) |
| `playerIndex` | Speaker-rotation index within the original group (0, 1, or 2). The designated speaker of block b is the member with index b mod 3, and the Phase 2 reshuffle places one player of each index in every group, so two players with the same index are never in the same group |
| `originalName` | Player's original display name |
| `score` | Total points earned |
| `bonus` | Monetary bonus (score × bonus rate) |
| `isActive` | Whether the player remained active throughout |
| `idleRounds` | Number of rounds the player was idle |
| `exitReason` | Why a player left early: `player timeout` (idle for three rounds), `low accuracy` (failed the Phase 1 accuracy check), `group disbanded`, `insufficient groups after accuracy check`, or `quiz failed`; empty for players who finished |
| `ended` | Empirica's end status for the player (`game ended`, or the removal reason) |
| `gameStartTime`, `gameEndTime` | Timestamps (ms since epoch) of the player's start and end; the difference gives the time-prorated base pay. In the pilot only removed players have an end time, because the server did not record one for players who finished until September 2026 |
| `minutesSpent` | Whole minutes between the player's start and end. Recorded for everyone from September 2026; in the pilot only removed players have one |
| `quizAttempts` | How many attempts the player took to pass the comprehension quiz, out of three. Full sample only |
| `shuffledTangrams` | The order the 16 tangrams appeared in on this player's own grid, as a JSON list. Every player sees a different order, which is what makes position-based descriptions ("the one on the left") fail |
| `partialPay`, `partialBasePay`, `partialBonus` | Compensation of a removed player: total, the time-prorated base pay, and the bonus (zero for idle removals); empty for players who finished |
| `phase1LengthChange` | Mean word count of the player's descriptions in their last Phase 1 block as speaker minus that in their first (from the unfiltered utterances); empty if they spoke in fewer than two Phase 1 blocks |
| `lengthIncreaseFlag` | Whether `phase1LengthChange` exceeds 5 words. Lengthening descriptions are the signature of the simulated LLM agents, so flagged players' chat logs are inspected for AI use; the flag is a trigger for inspection, not an exclusion by itself. No pilot player is flagged |
| `exitSurvey_understood` | Understood the instructions (`yes`/`no`) |
| `exitSurvey_groupIdentification` | "How much did you feel a sense of being a part of your Phase 1 group?" (1-7); full sample only |
| `exitSurvey_groupCloseness` | "How close did you feel to the people in your Phase 1 group?" (1-7); full sample only |
| `exitSurvey_groupLanguage` | Noticed the group developing its own way of describing the pictures (`yes`/`no`); full sample only |
| `exitSurvey_strategy` | Free-text: their strategy in the game (the pilot stored this as `exitSurvey_strength`) |
| `exitSurvey_feltHuman` | Felt they were playing with other humans (`yes`/`no`); full sample only. Games with any `no` are flagged for inspection |
| `exitSurvey_age` | Self-reported age |
| `exitSurvey_gender` | Self-reported gender (`male`, `female`, `non-binary`, `other`, `prefer-not-to-say`) |
| `exitSurvey_education` | Self-reported education level (`high-school`, `bachelor`, `master`, `other`) |
| `exitSurvey_fair` | Free-text: was the pay fair |
| `exitSurvey_feedback` | Free-text: additional comments |
| `clientViewportWidth`, `clientViewportHeight` | Size of the browser viewport at the start of the session, in CSS pixels. The task is a 4x4 grid of 16 tangrams, so this bears on how much visual search a selection takes. Full sample only |
| `clientScreenWidth`, `clientScreenHeight`, `clientDevicePixelRatio`, `clientTouch` | The rest of the display context: screen size, pixel density, and whether the device reports touch input. Full sample only |
| `clientTimezoneOffsetMin`, `clientLanguage` | Timezone offset from UTC in minutes (enough to read a session's local time of day, which bears on fatigue) and the browser's language. Full sample only |
| `tabHiddenCount`, `tabHiddenMs` | How many times the participant switched away from the tab and the total time it spent hidden. A trailing switch with no return counts but adds no time, since it has no defensible end. Full sample only |
| `offlineCount`, `resizeCount` | How many times the browser lost its connection and came back, and how many times the window was resized. An outage is recorded only once the connection returns, since nothing can be sent while it is down, so a participant who dropped out for good contributes no count. Full sample only |
| `engagementLogTruncated` | Whether the engagement log hit its 200-event cap, so a short log is never mistaken for a quiet session. Full sample only |

The raw user agent is recorded during a session so a live problem can be debugged against the real browser, but it is a fingerprinting vector and is stripped during anonymization, so it never reaches this directory. The coarse `client*` fields above are what the analysis uses. The per-event engagement log stays in `raw_anonymized/player.csv`; the columns here are its summary.

The survey was revamped after the pilot (2026-03): the pilot data have `exitSurvey_strength` and none of the group or felt-human items. Players removed at the Phase 1 accuracy check complete both survey pages too, so the demographics are available for the attrition report.

## trials.csv

One row per player per reference game round. Grouping rows by `gameId`, `roundId`, and `currentGroup` recovers every group as it was played, and `speakerId` and `inGroupSpeaker` make each listener's speaker explicit, so the full interaction history of a game can be reconstructed from this table alone.

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
| `timeout` | Whether the listener had no scored selection at the deadline (no click, or a click that arrived late) |
| `lateClick` | Whether the listener's selection reached the server after the Selection deadline (unscored, but not counted as idle). Always `False` in the pilot, which predates this flag |
| `clickedAt` | When the listener's selection was committed to the server (ms since epoch, participant's own clock); empty in the pilot. This is the commit time, which is what the late-arrival audit needs -- for a response time use `tangramSelectedAt` |
| `tangramSelectedAt` | When the listener actually chose a tangram (ms since epoch, participant's own clock). The same moment as `clickedAt` in the referential conditions, where a click commits at once, but earlier in the social conditions, where both answers are held locally until submit. This is the only selection time comparable across conditions. Full sample only |
| `selectionRenderedAt` | When the Selection stage first appeared on this participant's screen (ms since epoch, their own clock). Full sample only |
| `selectionRt` | `tangramSelectedAt` minus `selectionRenderedAt`: the listener's response time in milliseconds. Both ends come from the same browser, so clock differences between participants cannot contaminate it -- but for the same reason none of the participant-clock columns above may be compared *across* participants. Full sample only |
| `socialGuessSelectedAt`, `socialGuessRt` | The same pair for the social-identification answer: when it was chosen, and how long after the stage rendered. Social conditions, full sample only |
| `selectionStartedAt`, `selectionEndedAt` | When the Selection stage started and ended, on the *server's* clock (ms since epoch), so unlike the columns above these are comparable across everyone |
| `selectionDurationMs` | How long the Selection stage actually ran. Shorter than the timer whenever every listener answered early |
| `trialNum` | Sequential trial number within the game |
| `tangramSet` | Which tangram set was used |
| `repNum` | How many times this speaker has described this target within the current phase (1st, 2nd, etc.). Only present for speakers. |
| `speakerId` | Player ID of the speaker in this player's group on this trial (equals `playerId` on speaker rows) |
| `inGroupSpeaker` | For listeners, whether the speaker came from the listener's original group; empty on speaker rows |
| `groupSize` | Number of players in this player's group on this trial: 3, or 2 after dropout |
| `speakerReassigned` | Whether the group's speaker was not the block's designated one (the member with rotation index `blockNum` mod 3), which happens after a removal. Recorded by the server from September 2026 and derived from `playerIndex` for earlier exports such as the pilot |
| `reshuffleMode` | In Phase 2 of the mixed conditions, the server's record of that trial's reshuffle: `constrained` when every group was a trio with exactly one in-group listener, `reduced` otherwise. Empty in Phase 1, in the separated condition, and throughout the pilot, whose exports predate the record |

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
| `timestamp` | When the message was sent (ms since epoch, sender's own clock) |
| `composeStartedAt` | When the sender typed the first character of this message (ms since epoch, their own clock). Reset whenever the box is emptied, so it describes the message actually sent. Full sample only |
| `composeMs` | `timestamp` minus `composeStartedAt`: how long the message took to compose. A production-effort measure alongside word count, and the clearest signal of pasted text when a long message has a near-zero interval. Both ends come from the same browser, so this is valid within a sender but not across senders. Full sample only |
| `pasted` | Whether any part of the message was pasted rather than typed. Full sample only |
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

Same structure as `speaker_utterances.csv`, but non-referential messages are removed before concatenation. Rounds in which every speaker message was non-referential are dropped rather than kept as empty utterances, matching how rounds with no speaker message are handled, so this file can have fewer rows than the unfiltered one (two fewer in the pilot). The `apply` command reports how many rounds it dropped.

## social_guesses.csv

Listener guesses about whether the speaker belongs to their original group. Only present in `social_mixed` and `social_first` conditions.

| Column | Description |
|--------|-------------|
| `gameId` | Game session identifier |
| `playerId` | Listener who made the guess |
| `originalGroup` | Listener's initial group |
| `blockNum` | Block number |
| `phase` | Always `refgame` |
| `phaseNum` | Always 2 (social guesses are made in Phase 2) |
| `roundId` | Round identifier, shared by all groups in a game |
| `currentGroup` | The listener's group in this round (groups are reshuffled every Phase 2 trial) |
| `speakerId` | The speaker the guess was about: the speaker of the listener's current group in that round |
| `target` | Target tangram being described |
| `socialGuess` | `same_group` or `different_group` |
| `socialGuessCorrect` | Whether the guess was correct |
| `socialRoundScore` | Points awarded for the guess |
| `socialGuessSelectedAt` | When the listener chose their answer (ms since epoch, their own clock). The answer is held locally until submit, so this is earlier than the moment it reached the server. Full sample only |
| `socialGuessRt` | How long after the Selection stage rendered the answer was chosen, in milliseconds. Comparable with `selectionRt` in `trials.csv`, which shows which of the two decisions the listener made first. Full sample only |
| `tangramSet` | Which tangram set |
