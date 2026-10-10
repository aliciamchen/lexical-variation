# Dataset codebook

This directory holds the pilot dataset: the analysis-ready tables at this level are produced from the anonymized Empirica exports in `raw_anonymized/` by the pipeline described in the project README. Every dataset in `data/<name>/` has the same files and columns, so this file is also the codebook for the full sample (`data/full/`, not committed until its public release). Columns whose instrumentation came after the pilot are empty in the pilot, and the descriptions say so.

Timestamps come from two clocks. The columns recorded in the participant's browser (`selectionRenderedAt`, `tangramSelectedAt`, `clickedAt`, `socialGuessSelectedAt`, `composeStartedAt` and the message `timestamp`) are comparable only within that participant, because browser clocks differ by seconds and occasionally by hours; the response times derived from them (`selectionRt`, `socialGuessRt`, `composeMs`) are within-participant differences and are safe. The columns recorded by the server (`selectionStartedAt`, `selectionEndedAt`, `gameStartTime`, `gameEndTime`) are comparable across everyone.

## Provenance and input files

| File | Written by | Contents |
|------|-----------|----------|
| `runs.txt` | `extract_run.py`, or by hand | The Empirica export timestamps combined into the dataset, one per line, with `#` comments. Exports are cumulative snapshots of one server, so listing several from the same server is safe: `combine_runs.py` keeps the newest version of each record |
| `manifest.json` | `combine_runs.py` | The provenance of `raw_anonymized/`: the source runs, per-table row counts, the lobby-timeout games that were filtered out (`filtered_failed_games`), the games dropped through `exclude_games.txt` (`excluded_games`), the number of dropout records, and the records seen in more than one export |
| `exclude_games.txt` | by hand, optional | Game ids that ran on the production server but are not data: rehearsals, deploy checks, and games with a participant who had already played a full game in an earlier session. One id per line, with its reason as a `#` comment. `combine_runs.py` drops them with every dependent row and records the ids in the manifest. The pilot has none |
| `participant_exclusions.csv` | by hand, optional | `playerId,reason`, both required. `preprocessing.py` drops the player's messages from `messages.csv` and both utterance files, so every derived measure excludes them; flags `excluded` and `exclusionReason` on their rows and on the rows of the listeners they spoke to in `trials.csv` and `social_guesses.csv`; and blanks their `exitSurvey_*` answers in `players.csv` (the answers stay in `raw_anonymized/`). `responseOpportunity` is left as computed. The pilot has none |
| `technical_exclusions.csv` | by hand, optional | `gameId,playerId,roundId,outcome,reason`: listener failures documented as technical, which the analysis treats as missing rather than unsuccessful |
| `dropouts.csv` | `combine_runs.py` | One row per player record that never played a real game: quiz failures (`exitReason` = `quiz failed`, with the number of attempts), lobby timeouts (`ended` = `game failed`) and arrivals after the games were full (`ended` = `no more games`). `batchId` is the batch the record was attached to; `condition` and `tangramSet` come from that batch's treatment when the batch had exactly one, and are empty when the batch listed several or the participant never reached one. These records are removed from `raw_anonymized/player.csv`, so this file is what the attrition report counts. The pilot's file has the first five columns only |
| `integrity_exceptions.csv` | by hand, optional | `invariant,gameId,playerId,roundId,reason`: documented cases where an invariant checked by `analysis/test_data_integrity.py` does not hold (`roundId` is empty for a player-level case). The tests require the cases they find to be exactly the documented ones, so an undocumented case fails and so does a documented case that has disappeared. It records data loss and instrumentation races, never analytic choices. In the full sample: exit surveys lost to the server crash of 2026-09-23 (`exit_survey_missing`, and `exit_survey_page_two_missing` where only the second page was lost) and commit times written before the choice time by a double click (`commit_before_choice`). The pilot has none |
| `messages_classified.csv` | `filter_nonreferential.py classify` | `messages.csv` plus the classifier's verdict on each speaker message: `llm_label` (`R` or `NR`) and `is_referential`; listener messages are `True` with no label. It is also the label cache, keyed on game, round, sender, timestamp and text, so `classify` sends only the speaker messages that have no label here |
| `speaker_utterances_filtered.source.json` | `filter_nonreferential.py apply` | The sha256 and row count of the `messages.csv` the filtered utterances were built from. `compute_derived.py` and `config.R` refuse a filtered file whose record is missing or stale, and `preprocessing.py` deletes a stale one when it rewrites `messages.csv`, so a filtered file left over from an earlier `messages.csv` is never analyzed |

## games.csv

One row per game.

| Column | Description |
|--------|-------------|
| `gameId` | Game identifier |
| `condition` | `refer_separated`, `refer_mixed`, `social_mixed` or `social_first` |
| `tangramSet` | Which of the two tangram image sets was used |
| `numPlayers` | Number of players in the game |
| `activeGroups` | Number of original groups still viable when the game ended (0 if every group was disbanded) |
| `activeGroupsMin` | The fewest groups any Phase 2 trial was played with: per Phase 2 round, the server's `reshuffle_groups` count where the export has it (September 2026 onward), otherwise the number of groups with a speaker in that round, minimized over rounds. It is below `activeGroups` in the mixed conditions when a reduced roster formed fewer groups than there were viable original groups |
| `phase1Blocks`, `phase2Blocks` | Number of blocks in each phase |
| `ended` | Whether Empirica marked the game as ended |
| `endedReason` | `end of game` when the game ran to completion, `all players removed` when it ended early |
| `gameTerminated` | Whether the researcher stopped the game from the admin panel. Full sample only |
| `batchId` | The Empirica batch the game was started from |
| `sourceRun` | The export timestamp (an entry of `runs.txt`) the game's records were read from: the newest export that contained it |

## players.csv

One row per player.

| Column | Description |
|--------|-------------|
| `playerId` | Player identifier |
| `gameId` | The player's game |
| `name` | Display name at the end of the game |
| `originalName` | Display name assigned at the start |
| `originalGroup` | Group assigned at game start (A, B or C) |
| `playerIndex` | Speaker-rotation index within the original group (0, 1 or 2). The designated speaker of block b is the member with index b mod 3, and the Phase 2 reshuffle places one player of each index in every group |
| `score` | Total points earned |
| `bonus` | Monetary bonus (score times the bonus rate) |
| `isActive` | Whether the player stayed in the game to the end |
| `idleRounds` | Number of rounds the player was idle |
| `exitReason` | Why a player left early: `player timeout` (idle for three rounds), `low accuracy` (failed the Phase 1 accuracy check), `group disbanded`, `insufficient groups after accuracy check` or `quiz failed`; empty for players who finished |
| `ended` | Empirica's end status, `game ended` for everyone once the game has ended, removed players included; `exitReason` carries the information about removal |
| `gameStartTime`, `gameEndTime` | When the player started and ended, in ms since the epoch on the server's clock; the difference gives the time-prorated base pay. In the pilot only removed players have an end time |
| `minutesSpent` | Whole minutes between start and end. Recorded for everyone from September 2026; in the pilot only removed players have one |
| `quizAttempts` | How many attempts the player took to pass the comprehension quiz, out of three. Empty in the pilot |
| `shuffledTangrams` | The order the 16 tangrams appeared in on this player's own grid, as a JSON list. Every player sees a different order, which is what makes position-based descriptions fail |
| `partialPay`, `partialBasePay`, `partialBonus` | Compensation of a removed player: the total, the time-prorated base pay and the bonus (zero for idle removals); empty for players who finished |
| `phase1LengthChange` | Mean word count of the player's descriptions in their last Phase 1 block as speaker minus that in their first, from the unfiltered utterances; empty if they spoke in fewer than two Phase 1 blocks |
| `lengthIncreaseFlag` | Whether `phase1LengthChange` exceeds 5 words. Lengthening descriptions are the signature of the simulated LLM agents, so flagged players' chat logs are inspected for AI use; the flag triggers an inspection, not an exclusion |
| `exitSurvey_understood` | Understood the instructions (`yes`/`no`) |
| `exitSurvey_groupIdentification` | "How much did you feel a sense of being a part of your Phase 1 group?" (1 to 7). Full sample only |
| `exitSurvey_groupCloseness` | "How close did you feel to the people in your Phase 1 group?" (1 to 7). Full sample only |
| `exitSurvey_groupLanguage` | Noticed the group developing its own way of describing the pictures (`yes`/`no`). Full sample only |
| `exitSurvey_strategy` | Free text: their strategy in the game. The pilot stored this as `exitSurvey_strength` |
| `exitSurvey_feltHuman` | Felt they were playing with other humans (`yes`/`no`). Full sample only; games with any `no` are inspected |
| `exitSurvey_age` | Self-reported age |
| `exitSurvey_gender` | `male`, `female`, `non-binary`, `other` or `prefer-not-to-say` |
| `exitSurvey_education` | Education level. The pilot offered `high-school`, `bachelor`, `master` and `other`; the full sample offers RefBank's five (`less-than-high-school`, `high-school`, `some-college`, `bachelors`, `advanced-degree`), so the two are not directly comparable |
| `exitSurvey_nativeLanguage`, `exitSurvey_race` | First language and race or ethnicity, free text, optional. Full sample only; collected because RefBank records them |
| `exitSurvey_fair` | Free text: whether the pay was fair. Optional, so empty when left blank |
| `exitSurvey_feedback` | Free text: additional comments |
| `clientViewportWidth`, `clientViewportHeight` | Size of the browser viewport at the start of the session, in CSS pixels. The task is a 4 by 4 grid of tangrams, so this bears on visual search. Full sample only |
| `clientScreenWidth`, `clientScreenHeight`, `clientDevicePixelRatio`, `clientTouch` | Screen size, pixel density and whether the device reports touch input. Full sample only |
| `clientTimezoneOffsetMin`, `clientLanguage` | Timezone offset from UTC in minutes and the browser's language. Full sample only |
| `tabHiddenCount`, `tabHiddenMs` | How many times the participant switched away from the tab and the total time it was hidden. A trailing switch with no return counts but adds no time. Full sample only |
| `offlineCount`, `resizeCount` | How many times the browser lost its network connection and came back, and how many times the window was resized. An outage is recorded once the connection returns, so a participant who never came back contributes no count. Full sample only |
| `engagementLogTruncated` | Whether the engagement log hit its 200-event cap. Full sample only |
| `disconnectCount`, `disconnectMs` | How many times the connection to the game server (the websocket, not the network) dropped during the game, and the total time it was down. Only the part of a drop between the player's `gameStartTime` and `gameEndTime` counts, so a drop in the lobby or on the final page adds nothing; the window is moved onto the participant's clock with the offset estimated from their own trials, the median of `selectionRenderedAt` minus `selectionStartedAt`. The browser raises no event when only the websocket drops, which is the common case on a busy server, so these are the record of the drops participants reported. Sessions from 2026-09-25 only |
| `pageLoadCount`, `reloadCount` | How many times the game page was loaded, and how many of those loads were reloads. Sessions from 2026-09-25 only |
| `connectionLogTruncated` | Whether the connection log hit its event cap. Sessions from 2026-09-25 only |
| `excluded`, `exclusionReason` | Whether the player is listed in `participant_exclusions.csv`, and why. Their survey answers above are blank when so |

The raw user agent, which the client records so a live problem can be debugged against the real browser, is a fingerprinting vector and is stripped at anonymization. The per-event engagement and connection logs stay in `raw_anonymized/player.csv`; the columns here are their summaries. The survey was revamped after the pilot: the pilot has `exitSurvey_strength` and none of the group or felt-human items. Players removed at the Phase 1 accuracy check complete both survey pages too.

## trials.csv

One row per player per reference-game round. Grouping rows by `gameId`, `roundId` and `currentGroup` recovers every group as it was played, and `speakerId` and `inGroupSpeaker` make each listener's speaker explicit, so the interaction history of a game can be reconstructed from this table alone.

| Column | Description |
|--------|-------------|
| `gameId`, `playerId`, `playerName` | The game, the player and the player's display name on this trial |
| `originalGroup` | The player's initial group (A, B or C) |
| `currentGroup` | The player's group on this trial; it changes every Phase 2 trial in the mixed conditions |
| `role` | `speaker` or `listener` |
| `blockNum` | Block number within the phase, from 0 |
| `phase` | Always `refgame`; the transition screens have no rows |
| `phaseNum` | 1 or 2 |
| `target` | The target tangram, for example `page5-28` |
| `trialNum` | Sequential trial number within the game |
| `tangramSet` | Which tangram set was used |
| `repNum` | How many times this speaker has described this target within the phase, counting this trial. Speaker rows only |
| `clicked` | Which tangram the listener clicked; empty for speakers and timeouts |
| `clickedCorrect` | Whether the listener's click was correct; empty for speakers |
| `roundScore` | Points awarded on this trial |
| `timeout` | Whether the listener had no scored selection at the deadline, through no click or a late one |
| `lateClick`, `lateSocialGuess` | Whether the listener's selection, or their social guess, reached the server after the Selection deadline: unscored, but not counted as idle. Always `False` in the pilot, which predates the flags |
| `hasSpeakerMessage`, `responseOpportunity` | Whether this trial's speaker sent a message, and whether the row is an eligible listener response opportunity (a listener whose speaker sent a message), which is the accuracy denominator |
| `clickedAt` | When the listener's selection was committed to the server, on the participant's clock. In the social conditions this is the submit time, so use `tangramSelectedAt` for a response time. Empty in the pilot |
| `tangramSelectedAt` | When the listener chose a tangram, on the participant's clock: the same moment as `clickedAt` in the referential conditions, earlier in the social conditions, where both answers are held until submit. The only selection time comparable across conditions. Empty in the pilot |
| `selectionRenderedAt` | When the Selection stage first appeared on this participant's screen, on their clock. Empty in the pilot |
| `selectionRt` | `tangramSelectedAt` minus `selectionRenderedAt`, the listener's response time in ms. Empty in the pilot |
| `socialGuessSelectedAt`, `socialGuessRt` | The same pair for the social-identification answer. Social conditions only; empty in the pilot |
| `selectionStartedAt`, `selectionEndedAt` | When the Selection stage started and ended on the server's clock, so comparable across everyone |
| `selectionDurationMs` | How long the Selection stage ran, in ms; shorter than the configured duration when every player responded early. Empty where the recorded endpoints are unusable, because they come from Empirica's last-changed timestamps, which a rewrite can put out of order |
| `speakerId` | The speaker of this player's group on this trial; equals `playerId` on speaker rows |
| `inGroupSpeaker` | For listeners, whether the speaker came from the listener's original group; empty on speaker rows |
| `groupSize` | Number of players in this player's group on this trial: 3, or 2 after a dropout |
| `speakerReassigned` | Whether the group's speaker was not the block's designated one (the member with rotation index `blockNum` mod 3), which happens after a removal. Recorded by the server from September 2026 and derived from `playerIndex` for the pilot |
| `reshuffleMode` | In Phase 2 of the mixed conditions, the server's record of the trial's reshuffle: `constrained` when every group was a trio with exactly one in-group listener, `reduced` otherwise. Empty in Phase 1, in `refer_separated` and in the pilot |
| `serverSpeakerId`, `serverInGroupListener`, `serverGroupSize` | The server's own record of the speaker, the listener's in-group status and the group size, written at role assignment from September 2026. The three columns above them are derived from the trio membership in this table, and the integrity suite checks that the two agree. Empty in the pilot |
| `reshuffleGroups`, `reshuffleTrios`, `reshuffleTriosOk`, `reshufflePairs` | The reshuffle's tally for a mixed Phase 2 trial: how many groups it formed, how many were trios, how many trios had exactly one in-group listener, and how many were pairs. The same for every player in the round; empty in Phase 1, in `refer_separated` and in the pilot |
| `excluded`, `exclusionReason` | Whether the row is excluded through `participant_exclusions.csv` and why: the participant's own reason on their rows, `speaker excluded: <reason>` on the rows of listeners they described to |

## messages.csv

One row per chat message. The server copies each message onto every group member's round, and the copies are collapsed here.

| Column | Description |
|--------|-------------|
| `gameId`, `roundId`, `trialNum`, `blockNum`, `phase`, `phaseNum`, `target`, `tangramSet` | The round the message was sent in, as in `trials.csv` |
| `group` | The sender's group on that trial |
| `senderId`, `senderName`, `senderRole` | The sender, their display name at the time (masked in mixed Phase 2) and their role, `speaker` or `listener` |
| `text` | The message |
| `timestamp` | When the message was sent, on the sender's clock |
| `composeStartedAt` | When the sender typed the first character of this message, on their clock; reset whenever the box is emptied. Empty in the pilot |
| `composeMs` | `timestamp` minus `composeStartedAt`: how long the message took to compose. A production-effort measure beside word count, and near zero for pasted text. Empty in the pilot |
| `pasted` | Whether any part of the message was pasted rather than typed. Empty in the pilot |

## speaker_utterances.csv and speaker_utterances_filtered.csv

One row per speaker per round: the speaker's messages of that round joined in time order with ", ". The filtered file is built the same way from the messages the classifier labeled referential, and a round in which every speaker message was non-referential has no row, as a round with no speaker message has none. The pilot's filtered file has two rows fewer than the unfiltered one.

| Column | Description |
|--------|-------------|
| `gameId`, `playerId` | The game and the speaker |
| `originalGroup`, `currentGroup` | The speaker's initial group and their group on this trial |
| `tangramSet`, `blockNum`, `trialNum`, `phase`, `phaseNum`, `target`, `repNum` | As in `trials.csv` |
| `utterance` | The joined messages |
| `uttLength` | Word count of the utterance |

## social_guesses.csv

One row per eligible listener per Phase 2 trial in the two social conditions: each listener's guess about whether the speaker belonged to their original group, with an empty guess where nobody answered.

| Column | Description |
|--------|-------------|
| `gameId`, `playerId`, `originalGroup` | The game, the listener and the listener's initial group |
| `roundId`, `blockNum`, `phase`, `phaseNum`, `target`, `tangramSet` | The round, as in `trials.csv`; `phaseNum` is always 2 |
| `currentGroup` | The listener's group on this trial |
| `speakerId` | The speaker the guess was about: the speaker of the listener's group on that trial |
| `socialGuess` | `same_group` or `different_group`; empty when no guess was submitted |
| `socialGuessCorrect` | Whether the guess was correct |
| `socialRoundScore` | Points awarded for the guess |
| `speakerWasSameGroup` | The server's record, written when it scored the guess, of whether the speaker belonged to the listener's original group: the ground truth `socialGuessCorrect` is judged against. Empty where no guess was scored |
| `socialTimeout`, `lateSocialGuess` | Whether no guess was submitted, and whether the guess arrived after the Selection deadline (unscored) |
| `hasSpeakerMessage`, `responseOpportunity` | Whether the speaker sent a message, and whether the row counts in the social-guess accuracy denominator |
| `socialGuessSelectedAt`, `socialGuessRt` | When the listener chose the answer, on their clock, and how long after the Selection stage rendered; comparable with `selectionRt` in `trials.csv`, which shows which of the two decisions came first. Empty in the pilot |
| `excluded`, `exclusionReason` | As in `trials.csv`: the guesser's own exclusion or their speaker's |
