# Running a data-collection session

This is the runbook for one session of the reference game: recruiting nine (or eighteen, or
twenty-seven) people on Prolific to be online at the same moment, running the game, and
paying everyone afterwards. `operations/session.py` does the Prolific side; you do the
Empirica side in the admin panel. The procedure and the numbers in it come from the pilot
sessions of February and March 2026.

The game needs everyone online at once, so recruitment happens in two stages a few minutes
apart: participants first answer a three-question screening survey saying they can make the
session, then the game study is delivered to exactly those people at the announced time. The
manuscript describes this in the Recruitment paragraph of `writing/preregistration/main.tex`.

## How the commands work

Seven commands, used in this order every session:

| Step | Command | What it does |
|------|---------|--------------|
| 1 | `setup` | creates the screening survey and both study drafts |
| 2 | `open` | publishes the screening survey so responses start |
| 3 | `prepare` | turns the "yes" responses into an allowlist group and attaches it to the game draft |
| 4 | `message` | sends the reminder to that group |
| 5 | `publish` | publishes the game study, at a set clock time if you like |
| 6 | `approve` | approves the finishers' submissions |
| 7 | `pay` | sets up and pays bonuses and partial pay, and sends the explanatory notes |

Three things are true of all of them:

**Every command that changes anything shows its plan and asks first.** Read what it is
about to do, then answer `y`. Answering `n` (or Ctrl-C) leaves everything untouched. `--yes`
skips the question for scripting.

**Every step takes the same session name, and they share ids through it.** Pick any name --
a date and time is easiest -- and pass it as `--session`. `setup` saves the ids it creates
under that name in `operations/.sessions/`, `prepare` adds the group it makes, `pay` adds the
run it processed, and each command prints what it read back, like
`[2026-09-15-2100] game_study_id = 6aa4…`.

**Nothing is published until you say so.** `setup` creates drafts only. `open` and `publish`
are the two commands that make something visible to participants, and each asks
separately.

## Before your first session

**1. [CLI] Environment.** Run `uv sync`, and make sure the repository-root `.env` has
`PROLIFIC_TOKEN` (your API token from Prolific's settings) and `PROLIFIC_WORKSPACE` (the id
of the Lexical Variation workspace); `.env.example` documents both.

**2. [CLI] Seed the blocklist group** with everyone who has already played, pilot
participants included, so none of them can join the full sample:

```bash
uv run python operations/session.py blocklist --from-prolific
```

It reports who it will add -- 129 players from the pilot, with the 42 lobby timeouts and 38
no-code dropouts left eligible -- and asks. Answer `y`. This is a one-time step: every game
study created by `setup` adds its own players to the group as they submit (see "Reference:
eligibility").

**3. [CLI] Point the pipeline at the full sample** so none of the data commands need a
flag. Put this in your shell profile:

```bash
export DATASET=full
```

**4. [Empirica] Deploy the current bundle** to the server (`README.md`, "Deploying a new
build").

## The session, step by step

### Lead time: almost none

In the pilot, screening responses arrived within 4 to 15 minutes of the survey going live --
one survey collected 43 responses in under 4 minutes -- and the surveys went up only 12 to
20 minutes before the session they recruited for. A whole session fits inside about an hour,
so this is written as time before the session start, `T`. A short window is arguably better
than a long one: the people answering are at their computers right now.

### Every command, in order

Set the session name, then work down the list. Each command asks before acting.

```bash
S=2026-09-15-2100                       # any name; a date and time is easiest

# T-45
uv run python operations/session.py setup --session $S \
    --time "6pm PT / 9pm ET" --title-time "9pm ET" \
    --condition social_first --set 1 --places 30

# T-30   [Empirica] create and start the batch, then:
bash operations/copy_tajriba.sh

# T-25
uv run python operations/session.py open --session $S
uv run python operations/session.py surveys --counts        # watch it fill

# T-15
uv run python operations/session.py prepare --session $S

# T-10
uv run python operations/session.py message --session $S

# T
uv run python operations/session.py publish --session $S --at 21:00

# afterwards
uv run python analysis/extract_run.py
uv run python analysis/combine_runs.py
uv run python analysis/process_data.py
make test
uv run python operations/session.py approve --session $S
uv run python operations/session.py pay --session $S
```

### T-45: create everything

**5. Pick the treatment.** You need 10 games per condition per tangram set, so choose
whichever of the eight cells has the fewest games so far. Run one treatment per session, so
that everyone who arrives can fill any game in the batch.

**6. [CLI] `setup`.** It copies the questions from your most recent screening survey and
the game settings from your most recent game study, substitutes the session time, finds the
blocklist group by name, and shows you the plan:

```text
Template survey:  Screening survey: Group communication game [starts 8:30pm ET]
Template study:   final pilot  (69a475f5…)
Blocklist group:  'Played the game' (129 members, 6aa4…)
New survey title: Screening survey: Group communication game [starts 9pm ET]
Retimed question: Are you available at 6pm PT / 9pm ET to participate in a 45-60 minute …
Game study draft: social_first set 1 2026-09-15
  reward 1200 | est 50 min | desktop | url_parameters | places 30
  code C2I8XDMC   MANUALLY_REVIEW, ADD_TO_PARTICIPANT_GROUP
  code CMZUY3MK   REQUEST_RETURN
  code CFTYDMIY   REQUEST_RETURN, ADD_TO_PARTICIPANT_GROUP
Create the survey and both study drafts? Nothing is published. [y/N]
```

`--time` is the wording that goes into the availability question; `--title-time` is the
shorter form for the titles. `--places` is how many players you expect on the game study.
If the blocklist line says `none`, stop and run step 2 -- otherwise past players could sign
up.

Both studies come back `UNPUBLISHED`. Open them in the Prolific UI if you want to look; the
values to expect are in "Reference: what the studies look like". A mistake at this point is
just a deleted draft.

### T-30: bring up Empirica

**7. [Empirica] Confirm the server is alive**, open the admin panel and Sentry, and **create
and start the batch before any participant can arrive**, sized for all the games you intend
to run, with `preferUnderassignedGames: true`. Empirica cannot move players between games of
different treatments, so a batch created after assignment has begun kicks players out of a
game already in progress. This has to be done before step 8, because responses arrive
within seconds of the survey opening.

**8. [CLI] Start the backup loop.** It copies an export every five minutes into
`experiment/data/`, in case the session dies partway:

```bash
bash operations/copy_tajriba.sh
```

### T-25: open the survey and watch it fill

**9. [CLI] `open`.** Shows the survey study's reward, places and filters -- check the
blocklist is listed -- and asks. Answer `y`, and responses begin within seconds.

**10. [CLI] Watch the count** until you have what you need. For three games you want about
40 eligible responses, since roughly 75% of the people who say they can make it turn up:

```bash
uv run python operations/session.py surveys --counts
```

### T-15: build the allowlist

**11. [CLI] `prepare`.** Reads the responses, keeps the people who answered "Yes" to all
three questions, and shows the count, the reasons the others were excluded, and the expected
turnout at 75%:

```text
43 responses
Eligible (answered 'Yes' to every question): 40
Excluded: 3
    3 did not answer 'Yes' to: This study is a real-time multiplayer game lasting …
Expected to show up at 75%: about 30
Create group '2026-09-15-2100' with these 40 people and allowlist it on study 6aa4…? [y/N]
```

Answer `y`. It creates the group, attaches it to the game draft as
`participant_group_allowlist`, and saves the group id to the session. Because the study
points at a group rather than a fixed list, a late sign-up added to the group becomes
eligible without touching the study.

### T-10: send the reminder

**12. [CLI] `message`.** Renders the reminder with the session time filled in, shows it and
the recipient count, and asks. The wording is in `operations/messages/reminder.txt`.

### T: publish

**13. [CLI] `publish --at 21:00`.** Shows the study's status and allowlist, asks once, then
holds the timer itself and publishes at the minute you named -- so leave it running in the
foreground. It refuses a study that is not `UNPUBLISHED`, and refuses one with no allowlist,
which would otherwise open at full reward to all of Prolific.

**14. Monitor** the Empirica admin panel for arrivals and game progress, and Sentry for
client errors. A few participants will message asking where the study is; the reminder told
them it appears exactly at the announced time.

### After the session

**15. [Empirica] Stop the batch**, take one more export with `copy_tajriba.sh`, then stop the
backup loop with Ctrl-C. That last export is the one that matters.

**16. [CLI] Run the export through the pipeline.** Four commands, no flags needed once
`DATASET=full` is set. `extract_run.py` registers the run for you and prints the next
command each time:

```bash
uv run python analysis/extract_run.py       # anonymize; write bonuses.csv, early_ended.csv
uv run python analysis/combine_runs.py      # union the registered exports
uv run python analysis/process_data.py      # preprocess, filter, derived metrics
make test                                   # integrity suite
```

(`process_data.py --skip-filter` skips the one step that spends Vertex AI credit.)

**17. [CLI] `approve`.** Lists the submissions by status and asks to approve every one that
is awaiting review with the finished code. Anything awaiting review *without* that code is
listed separately for you to look at by hand.

**18. [CLI] `pay`.** One command, three questions, each for an irreversible step:

```text
finishers       24 people  $ 153.88  -- not set up
removed early    3 people  $  27.81  -- not set up
Set these up with Prolific? This charges nothing yet. [y/N] y
Prolific's totals (fees and VAT included):
  finishers       $ 205.17  unpaid
  removed early   $  37.08  unpaid
Pay $242.25 now? This cannot be undone. [y/N] y
Notes for the 3 removed players:
  RETURNED  $ 9.22  low accuracy  -> note only [neutral]
  …
Send these notes to 3 people? [y/N] y
```

(The fee-inclusive totals above are illustrative -- Prolific's fee on bonuses is about 33% --
the real ones come back from Prolific at the set-up step.)

It picks the most recent extracted run (say `--run <timestamp>` to choose), keeps a ledger
under the run directory so nothing is ever paid twice, and words each removed player's note
from their recorded exit reason. Stopping at any question leaves everything before it done
and everything after it not; re-running picks up where you stopped.

**19. Nothing else.** This session's players were added to the blocklist group as they
submitted, so the next session's survey already excludes them.

## If something goes off script

**You lost the session name.** `session.py sessions` lists every saved session and what it
holds.

**The survey `setup` made is wrong, or you want to reuse another.** Pass a survey id to
`prepare` explicitly -- `prepare <survey_id> --session $S` -- and it uses that survey while
still taking the game study from the session. Explicit ids always win over the session.
`surveys --counts` lists them; duplicates keep a "Copy" suffix and are usually the empty
ones.

**`publish` refuses because there is no allowlist.** `prepare` has not run, or you ran it
against a different session. Run it; the refusal is what stops a $12 study opening to
everyone on Prolific.

**`setup` failed partway.** It creates the survey first, then the two studies, so a failure
can leave a stray. `surveys` and `studies` show anything unpublished you did not mean to
keep; drafts and surveys can be deleted in the UI.

**Someone asks to be added after `prepare` ran.** Add them to the group in the Prolific UI.
The study allowlists the group, so they become eligible immediately, no republish.

**A participant should not have been paid.** `pay` will not pay a population twice, but it
also cannot un-pay. Fix the CSV before running it, not after.

## Reference: what the studies look like

Values from the final pilot, which is the session that produced the committed pilot data.
`setup` copies them from the most recent game study; pin a specific one with
`--template-study`.

| | Screening survey study | Game study |
|--|--|--|
| reward | $0.30 (`30`) per response | $12.00 (`1200`) |
| places | 100 (a ceiling; you pay per response) | the players you expect |
| time | 1 min | 50 min estimated, 123 max |
| device | desktop | desktop |
| URL | `https://prolific.com/surveys/<survey_id>` | the server, with `?PROLIFIC_PID={{%PROLIFIC_PID%}}&STUDY_ID={{%STUDY_ID%}}&SESSION_ID={{%SESSION_ID%}}` |
| filters | US, fluent English, `participant_group_blocklist` | `participant_group_allowlist` (added by `prepare`) |
| completion codes | one, `COMPLETED` | `C2I8XDMC` finished (`MANUALLY_REVIEW` + add to blocklist) · `CMZUY3MK` lobby timeout (`REQUEST_RETURN`) · `CFTYDMIY` removed early (`REQUEST_RETURN` + add to blocklist) |

The three codes are defined in `experiment/shared/constants.js`. Prolific requires a
`privacy_notice` on any survey-backed study; `setup` copies it from the template and refuses
to proceed without one.

## Reference: eligibility, and why lobby timeouts stay eligible

The design is between subjects, so nobody may play twice. Two filters, both pointing at
participant groups rather than lists of people:

- **`participant_group_allowlist`** on the game study -- the group `prepare` builds for this
  session. Only they can see the study.
- **`participant_group_blocklist`** on the screening survey -- one standing group,
  `Played the game`, of everyone who has ever been placed in a game.

**The blocklist maintains itself.** `setup` attaches an `ADD_TO_PARTICIPANT_GROUP` action to
the two completion codes that mean "saw the task", `C2I8XDMC` and `CFTYDMIY`, so Prolific
adds each player to the group the instant they submit. The `CMZUY3MK` lobby-timeout code
carries no such action, and that is what keeps those participants eligible: they never saw
a tangram, they are already screened, and they have proved they turn up on time, so they
are the best people to invite to a later session.

`blocklist` exists to seed the group before the first session and to repair it if you ever
suspect drift. It can read who played from the extracted runs (precise, but only covers runs
you have extracted) or from Prolific submissions (`--from-prolific`, covers every session).
The 38 pilot submissions with no completion code at all -- people who consented and never
reached an exit screen -- stay eligible by default on the same reasoning as the lobby
timeouts; `--include-unknown` blocks them instead.

## Reference: how people are paid

**Finishers** are approved (`approve`), which pays the $12 base reward, and then receive
their earned bonus (`pay`).

**Removed players** -- disbanded group, failed accuracy check, too few groups, or idling out
-- are paid by **returning the submission and receiving their partial pay as a bonus**, never
by approval. `computePartialPay` in `experiment/server/src/compensation.js` already bundles
prorated base pay together with the earned bonus into one number, so approving would pay the
full base reward on top of that. This is also exactly what Prolific recommends for
participants who cannot be matched in live studies: partial payment by bonus, a return
request, and a message explaining it. The return request is automatic through the
completion-code action; `pay` sends the message.

Two facts about the bonus API that shape `pay`:

- **Paying is a two-step call, and the first step is free.** Setting up a bulk payment
  charges nothing and returns Prolific's total including its fee (about 33% on bonuses).
  That is why `pay` shows you that total before asking to pay.
- **The pay call is not idempotent.** Sending it twice pays everyone twice. `pay` records
  each bulk payment id and its paid time in `data/runs/<run>/prolific_payments.json` and
  refuses to pay a population that already has a paid time. Do not delete that file to
  "retry".

Amounts are sent as decimals (`1.50` means $1.50) and come back in cents; `--max-each`
(default $30) and `--max-total` refuse anything that looks wrong before it is sent.

## Reference: the data

`copy_tajriba.sh` leaves a zip in `experiment/data/<timestamp>/`. `extract_run.py` unzips
it, strips the Prolific ids from the raw CSVs, writes `bonuses.csv` and `early_ended.csv`
(which keep the ids, for `pay`) into the gitignored `data/runs/<timestamp>/`, and registers
the timestamp in `data/<dataset>/runs.txt`. `combine_runs.py` stacks the registered runs into
the committed `data/<dataset>/raw_anonymized/`; `process_data.py` produces the analysis
tables and derived metrics.

**Exports are cumulative and that is handled.** `empirica export` dumps the whole server,
not just the last session, so if you leave the server running the newest export contains
every earlier one. `combine_runs.py` unions the registered exports on record id and keeps the
newest version of each record, so listing one export, or all of them, gives the same correct
result. It also repairs the case where a five-minute backup caught rounds in progress that
the final export has completed. Overlaps are reported and recorded in `manifest.json`, so an
unexpected one -- the wrong server, say -- is visible.

The full sample is its own dataset, `data/full/`, never an edit of `data/pilots/`. Nothing
needs creating in advance: `extract_run.py` makes `runs.txt` on first use.

## Message templates

The three messages `session.py` sends live in `operations/messages/`; edit the wording
there. `{time}` and `{amount}` are filled in per session and per person.

### `reminder.txt` -- sent by `message`, about ten minutes before the session

> Hello! Thank you for signing up for our study. Just a reminder that the study will show up on your Prolific dashboard in a few minutes, at exactly {time}. This experiment depends on synchronous and real-time participation, so please join as soon as you see it. If it doesn't appear after refreshing, please let us know.

### `partial_payment.txt` -- sent by `pay` to removed players

Used when the removal was recorded as `low accuracy`, `player timeout`, or no reason: the
wording is neutral about whose doing it was.

> Hello, and thank you for taking part in our study today.
>
> Unfortunately the session ended before the game could be completed. This kind of study needs enough players to stay online together for the whole game, so sessions sometimes end early.
>
> We have sent you a partial payment of ${amount} through Prolific for the time you spent. You will also see a request to return the submission, since the study was not completed. Returning it does not affect the partial payment.
>
> Thank you again for your time, and sorry for the inconvenience.

### `partial_payment_others_left.txt` -- sent by `pay` to removed players

Used when the removal was recorded as `group disbanded` or `insufficient groups after
accuracy check`, where the participant can be told plainly that nothing went wrong on their
end.

> Hello, and thank you for taking part in our study today.
>
> Unfortunately the other players in your group left the game, so your session could not continue. Nothing went wrong on your end -- this kind of study needs everyone in a group to stay online together for the whole game.
>
> We have sent you a partial payment of ${amount} through Prolific for the time you spent. You will also see a request to return the submission, since the study was not completed. Returning it does not affect the partial payment.
>
> Thank you again for your time, and sorry for the inconvenience.

## What the pilots showed

The show-up rate held steady at roughly 75% across sessions, which is the figure quoted in
`README.md`. "Invited" below means the people who said on the form that they could make
the session.

| Session | Invited | Logged on | Rate | Notes |
|---------|---------|-----------|------|-------|
| Feb 22, `social_mixed` | 17 | 17 | -- | 20 completed the form; 9 started, 1 timed out, 8 finished |
| Feb 22, `refer_mixed` | 23 | 18 | 78% | 26 completed the form; 9 started and all finished |
| Feb 25 (Wed, 6pm) | 15 | 11 | 73% | Only ~5 replied to the confirmation request |
| `refer_separated` + `social_mixed` | 25 | 18 | 72% | First run where the form itself counted as signing up; aimed at two games |
| Feb 26 | 15 | 9 | 60% | |
| Feb 28 (Sat, 11:30am) | 36 | 28 | 77% | Aimed at two games |
| Repeat of the above | 36 | 28 | 78% | |
| Mar 1 | 40 | 31 | 75% | |
| Mar 1 (PM, experiment 2 pilot) | 28 | -- | -- | Not everyone found a game; 28 was too few for two games |

For a single nine-player game, inviting about 15 people has been enough. For two
concurrent games, 35--40 invitations worked and 28 did not.

## Operational lessons

- **Say that the study appears exactly at the announced time.** Participants go looking for
  it on their dashboard several minutes early and message you when they cannot find it.
- **Do not require a reply to confirm.** Some participants miss the instruction and message
  anyway, and unconfirmed participants show up regardless, so the confirmation step adds
  monitoring work without improving attendance.
- **Weeknight evening sessions were harder to fill** than the weekend late-morning session.
  The Wednesday 6pm session was the weakest of the pilots.
- **Longer instructions cost you players.** The experiment 2 pilot, which has longer
  instructions, lost more participants between logging on and being placed in a game.
- **Tell participants to keep their sound on** and to watch for the sound that plays when
  the game starts.
- **Overflow participants need the right screen.** Someone assigned to a batch whose game
  starts without them should see a recruitment message rather than the waiting-room timeout
  screen, and should be told they are paid for their time rather than for their waiting
  time.
- **Consider re-contacting the near misses.** Participants who logged on but did not get
  into a game are good candidates to add to a group and invite to a later session.
