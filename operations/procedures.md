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

Eight commands, used in this order every session:

| Step | Command | What it does |
|------|---------|--------------|
| 1 | `setup` | creates the screening survey and both study drafts |
| 2 | `open` | publishes the screening survey so responses start |
| 3 | `prepare` | turns the "yes" responses into an allowlist group and attaches it to the game draft |
| 4 | `close` | stops the screening survey, once the allowlist is built |
| 5 | `message` | sends the reminder to that group |
| 6 | `publish` | publishes the game study, at the announced time if you like |
| 7 | `approve` | approves the finishers' submissions |
| 8 | `pay` | pays bonuses, partial pay and lobby-timeout pay, and sends the explanatory notes |

Four read-only lookups sit beside them: `tally` counts the games so far in each of the eight
(condition, tangram set) cells and marks the emptiest, which is the treatment the next session
should run; `sessions` lists the saved sessions; `surveys` and `studies` find Prolific ids.
`tally` and `sessions` read local files only and need no API token.

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

**Money is guarded at every step that spends it.** `setup` prints a cost ceiling for the
session before it creates anything, records it as the session's budget (or the figure you
give `--budget`), and refuses a template study whose reward, completion codes or code actions
have drifted from `experiment/shared/constants.js`. `pay` pays a removed player or lobby
timeout only if their submission is returned or awaiting review, never one already approved
or rejected; refuses a total larger than the number of people being paid could plausibly be
owed; refuses anyone another run already paid; refuses to pay a bulk payment whose rows or
amount no longer match what was set up; refuses to take the session past its budget; and
refuses to retry a payment it cannot prove failed.

## Before your first session

**1. [CLI] Environment.** Run `uv sync`, and make sure the repository-root `.env` has
`PROLIFIC_TOKEN` (your API token from Prolific's settings) and `PROLIFIC_WORKSPACE` (the id
of the Lexical Variation workspace); `.env.example` documents both.

Two optional variables are worth setting once you have a session you are happy with:
`PROLIFIC_TEMPLATE_SURVEY` and `PROLIFIC_TEMPLATE_STUDY`. Without them, `setup` copies the
*most recent* screening survey and game study, which means each session is copied from the
one before it and any one-off change to a study propagates forever. Pinning the two ids
breaks that chain, and `setup` still checks the reward and completion codes against the
experiment either way.

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
build"), and **wipe the server's `tajriba.json` first**. The server still holds the final
pilot session, and because `empirica export` is cumulative, the first full-sample export
would otherwise carry that pilot game into `data/full/`. The pilot is already exported and
committed, so nothing is lost.

**5. [CLI + Prolific] Rehearse once with a test participant.** Four of the commands publish
or spend -- `open`, `publish`, `approve`, `pay` -- and the only safe way to exercise them is
against a participant who is you. Prolific provides one: `POST /api/v1/researchers/participants/`
with an email address that is not yet registered creates a participant tied to your
researcher account that skips onboarding and fraud checks and cannot cash out. The feature
has to be enabled on the workspace; ask Prolific support if the call is refused.

```bash
# once: make the test participant (any unregistered email you control)
curl -s -X POST -H "Authorization: Token $PROLIFIC_TOKEN" -H "Content-Type: application/json" \
     -d '{"email": "you+prolifictest@example.edu"}' https://api.prolific.com/api/v1/researchers/participants/
# → {"participant_id": "…"}   keep this id
```

Then run a whole session against it. `--rehearsal` makes both studies visible to that one
participant only, with one place each, so no real participant can ever see them:

```bash
S=rehearsal
uv run python operations/session.py setup --session $S --rehearsal <test_participant_id> \
    --time "6pm PT / 9pm ET" --title-time "9pm ET" --condition refer_mixed --set 0 --places 1
uv run python operations/session.py open --session $S
# [Prolific, logged in as the test participant] take the screening survey, answer Yes ×3
uv run python operations/session.py prepare --session $S          # 1 eligible → group of 1
uv run python operations/session.py close --session $S            # stops the screening survey
uv run python operations/session.py message --session $S          # arrives in the test inbox
uv run python operations/session.py publish --session $S          # visible to the test participant only
# [Prolific, as the test participant] accept the study and click through to the game
```

With one player the game never forms, so after ten minutes the lobby times out and the
participant reaches the lobby-timeout code. That is the path worth rehearsing first, because
it is the one the data pipeline cannot see: `pay` finds that submission on Prolific, pays
the lobby-timeout amount, and sends the note.

```bash
mkdir -p data/runs/rehearsal                                            # pay reads a run directory, even an empty one
uv run python operations/session.py pay --session $S --run rehearsal   # lobby pay only
```

To rehearse the finisher path instead, have the test participant submit the finished code by
hand at `https://app.prolific.com/submissions/complete?cc=C2I8XDMC`, then:

```bash
uv run python operations/session.py approve --session $S          # approves the one submission
printf 'prolific_id,bonus\n<test_participant_id>,0.05\n' > data/runs/rehearsal/bonuses.csv
uv run python operations/session.py pay --session $S --run rehearsal   # set up → cost preview → pay
```

Add an `early_ended.csv` (`prolific_id,partial_pay,exit_reason`) the same way to rehearse
the partial-payment notes; the test participant's submission has to be returned or awaiting
review for `pay` to pay it, which is what the partial and lobby codes leave it as. Because
`pay` reads the run directory rather than an export, a hand-written `bonuses.csv` needs no
`run_meta.json`; it will say the batch is unknown, which is correct for a rehearsal.
Afterwards delete `data/runs/rehearsal/` and leave the rehearsal studies as they are; they
hold no real data.

What this costs is not documented: Prolific says the test participant cannot cash out, but
not whether your wallet is charged for its rewards, so assume the $12 base reward plus the
$0.30 survey and cents of bonus are spent. That is the price of knowing every write path
works before thirty real people are waiting on it.

The read-only half of the tooling is covered by tests instead, which need no API and no
data: `make test-ops` runs them. They cover who is counted eligible, what each population is
owed, what each person is told, when a study goes live, and the batch scoping of the payment
files.

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

# T-60   which treatment? one per batch, the emptiest of the eight cells
uv run python operations/session.py tally

# T-45
uv run python operations/session.py setup --session $S \
    --time "6pm PT / 9pm ET" --title-time "9pm ET" \
    --condition social_first --set 1 --places 30 --survey-places 60

# T-30   [Empirica] create and start the batch, then:
bash operations/copy_tajriba.sh

# T-25
uv run python operations/session.py open --session $S
uv run python operations/session.py surveys --session $S    # watch it fill

# T-15
uv run python operations/session.py prepare --session $S
uv run python operations/session.py close --session $S      # stop paying for responses

# T-10
uv run python operations/session.py message --session $S

# T
uv run python operations/session.py publish --session $S --at 21:00

# afterwards
uv run python analysis/extract_run.py       # scoped to this session's batch
uv run python analysis/combine_runs.py
uv run python analysis/process_data.py
make test
uv run python operations/session.py approve --session $S
uv run python operations/session.py pay --session $S
```

### T-45: create everything

**1. [CLI] Pick the treatment with `tally`.** You need 10 complete games in each of the
eight (condition, tangram set) cells, so the next session runs whichever cell has the fewest.
`tally` counts the games in `data/<dataset>/games.csv` per cell, adds the saved sessions that
have not been processed yet, and marks the emptiest:

```bash
uv run python operations/session.py tally
```

```text
7 complete game(s) in data/full/games.csv; 1 saved session(s):
  condition          set  games  incomplete  sessions
  refer_separated      0      1           0         0
  refer_separated      1      1           0         0
  refer_mixed          0      1           0         0
  refer_mixed          1      0           0         1 (1 pending)
  social_mixed         0      1           0         0
  social_mixed         1      0           0         0   <- emptiest
  ...
```

Run one treatment per batch -- every game in the batch is the same condition and tangram
set -- so that everyone who arrives can fill any game in it. Before the first session there
are no games yet, and `tally` says so.

**2. [CLI] `setup`.** It prints the same table and says whether the treatment you gave it is
the emptiest cell. Then it copies the questions from your most recent screening survey and
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

It then prints a cost ceiling, records it as the session's budget, and asks:

```text
Cost ceiling for this session (Prolific's fee is approximate):
  screening  60 responses x $0.30      $   18.00
  base pay   30 places x $12.00        $  360.00
  bonuses    30 players x $8.00        $  240.00   at the cap
  fee        ~33% of the above         $  203.94
  ---------------------------------------------
  total                                $  821.94
  Session budget: $821.94 (the ceiling; --budget to change); `pay` refuses to take the session past it.
```

`--time` is the wording that goes into the availability question; `--title-time` is the
shorter form for the titles. `--places` is how many players you expect on the game study.
`--survey-places` is the ceiling on screening responses, and you pay for each one, so set it
to roughly what you need rather than leaving it at the default -- 60 is about right when you
want 40 eligible. `--budget` sets the session's budget in dollars when the ceiling is not the
figure you want; `pay` adds up what the session has paid through Prolific and refuses to go
past it. If the blocklist line says `none`, stop and seed the blocklist group (step 2 of
"Before your first session") -- otherwise past players could sign up.

`setup` stops rather than asks if the template game study's reward is not the `BASE_PAY` the
experiment promises participants, if its completion codes are not the three in
`shared/constants.js`, or if the codes' actions are wrong: the finished code must not
approve itself (`approve` does that, after the cross-check against the game data), the
partial and lobby-timeout codes must request a return, and the finished and partial codes
must add the player to the blocklist group. All of it would otherwise be copied silently
into every later session, and the reward is what every removed player's partial pay is
prorated from.

Both studies come back `UNPUBLISHED`. Open them in the Prolific UI if you want to look; the
values to expect are in "Reference: what the studies look like". A mistake at this point is
just a deleted draft. The session file is written as each object is created, so a failure
part-way leaves the ids made so far in `operations/.sessions/`.

### T-30: bring up Empirica

**3. [Empirica] Confirm the server is alive**, open the admin panel and Sentry, and **create
and start the batch before any participant can arrive**, sized for all the games you intend
to run, all of one treatment, with `preferUnderassignedGames: true`. Empirica cannot move
players between games of different treatments, so a batch created after assignment has begun
kicks players out of a game already in progress. This has to be done before step 5 (`open`),
because responses arrive within seconds of the survey opening.

**4. [CLI] Start the backup loop.** Every five minutes it takes an export and copies it into
its own `experiment/data/<timestamp>/` directory, named by the export's timestamp, in case
the session dies partway. A failed copy is simply retried at the next interval; the loop
gives up only after three failures in a row.

```bash
bash operations/copy_tajriba.sh
```

### T-25: open the survey and watch it fill

**5. [CLI] `open`.** Shows the survey study's reward, places and filters -- check the
blocklist is listed -- and asks. Answer `y`, and responses begin within seconds.

**6. [CLI] Watch the count** until you have what you need. For three games you want about
40 eligible responses, since roughly 75% of the people who say they can make it turn up:

```bash
uv run python operations/session.py surveys --session $S
```

With `--session` this is a single request for the one survey you care about. Without it,
`--counts` costs a request per survey listed and the list grows by one every session, which
is worth avoiding when you are polling in the minutes before a session and Prolific is
rate-limiting.

### T-15: build the allowlist

**7. [CLI] `prepare`.** Reads the responses, keeps the people who answered "Yes" to all
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

Re-running `prepare` because more responses arrived tops up the same group rather than
building a second one, so it is safe to do, even after `publish`: a study that already
allowlists the group is left alone (`already allowlisted`) rather than patched.

Two things it will tell you about rather than paper over. A response that does not carry
exactly three questions is set aside as malformed and named, instead of being counted
eligible -- a response with no answers at all has no failing answers, which used to make it
look like a "yes" to everything. And if the expected turnout is below the nine players one
game needs, it says so before you build the group.

### T-15: close the survey

**8. [CLI] `close`.** The allowlist is now fixed, so every further response costs its
reward and tells someone they are expected at a session they will not be sent. Nothing used
to stop the survey, so it ran on through the session and overnight.

```bash
uv run python operations/session.py close --session $S
```

Once the survey is stopped, `close` lists the screening submissions by status and asks to
approve the ones awaiting review, so the respondents are paid their $0.30 the same day
rather than when Prolific's automatic approval gets to them. Approved and returned
submissions are left alone, so re-running `close` on an already-stopped survey only approves
whatever has arrived since.

### T-10: send the reminder

**9. [CLI] `message`.** Renders the reminder with the session time filled in, shows it and
the recipient count, and asks. The wording is in `operations/messages/reminder.txt`.

### T: publish

**10. [CLI] `publish --at 21:00`.** Shows the study's status and allowlist, asks once, then
holds the timer itself and publishes at the minute you named -- so leave it running in the
foreground. It refuses a study that is not `UNPUBLISHED`, and refuses one with no allowlist,
which would otherwise open at full reward to all of Prolific.

`--at` is read in the timezone the session's announced time names, not this machine's. With
`--time "6pm PT / 9pm ET"`, both `--at 18:00` and `--at 21:00` mean the same instant and
both are accepted; a time that resolves to any other instant is refused and names the gap,
because it would publish hours away from what the reminder promised. Pass an explicit zone
(`--at "21:00 ET"`) to be unambiguous, or `--force-time` if the gap is deliberate.

The publish call itself retries a few times on a timeout or a Prolific 5xx. It is the one
call in the session worth retrying: it fires after a countdown that cannot be repeated, with
the participants already waiting. If a retry is refused because an earlier attempt already
went through, `publish` (like `open` and `close`) checks the study's status and counts the
transition as done rather than reporting a failure.

**11. Monitor** the Empirica admin panel for arrivals and game progress, and Sentry for
client errors. A few participants will message asking where the study is; the reminder told
them it appears exactly at the announced time.

### After the session

**12. [Empirica] Stop the batch**, take one more export with `copy_tajriba.sh --once`, then
stop the backup loop with Ctrl-C. That last export is the one that matters; it has its own
`experiment/data/<timestamp>/` directory like every other.

**13. [CLI] Run the export through the pipeline.** Four commands, no flags needed once
`DATASET=full` is set. `extract_run.py` registers the run for you and prints the next
command each time:

```bash
uv run python analysis/extract_run.py       # anonymize; write bonuses.csv, early_ended.csv
uv run python analysis/combine_runs.py      # union the registered exports
uv run python analysis/process_data.py      # preprocess, filter, derived metrics
make test                                   # integrity suite
```

(`process_data.py --skip-filter` skips the one step that spends Vertex AI credit.)

`extract_run.py` prints the batch it scoped the payment files to, and how many earlier
sessions' games it left out. Check that line: it should name this session's batch. Pass
`--batch <id>` to pay a different one. The batch is recorded in `run_meta.json` and shown
again by `pay`.

**14. [CLI] `approve`.** Lists the submissions by status and asks to approve every one that
is awaiting review with the finished code. Anything awaiting review *without* that code is
listed separately, with participant and submission ids, for you to look at by hand.

It also cross-checks the finishers against the run's `bonuses.csv`, since approving pays the
base reward on the strength of a completion code alone. A submission carrying the finished
code that the game data has no completed game for is named and worth checking before you
approve; so is a player in `bonuses.csv` who never submitted a code at all. If no run has
been registered yet it says `no run to cross-check against`, which is your cue to run step
13 first.

Finally it names any partial or lobby-timeout submission still sitting in *awaiting review*
rather than *returned*. Those are paid by bonus and asked to return; if they are left,
Prolific eventually approves them anyway and pays the full base reward on top of the partial
payment already sent.

**15. [CLI] `pay`.** One command, three questions, each for an irreversible step:

```text
Run:   20260915_213012   (pass --run to choose another)
Study: 6aa4…
Batch: 01KJP22PWG1Y2G4YMBC8YXBSPW   (24 finishers, 4 removed)

removed early: 1 of 4 not paid:
  5f3a…  $  9.22  low accuracy  -- APPROVED: already paid the full base reward, so a partial payment on top would pay twice
finishers       24 people  $ 153.88  -- not set up
removed early    3 people  $  18.59  -- not set up
lobby timeouts   5 people  $  10.00  -- not set up
Set these up with Prolific? This charges nothing yet. [y/N] y
Prolific's totals (fees and VAT included):
  finishers       $ 205.17  unpaid
  removed early   $  24.79  unpaid
  lobby timeouts  $  13.33  unpaid
Session budget: $604.29 of $821.94 after this payment.
Pay $243.29 now? This cannot be undone. [y/N] y
Notes for the 8 people who did not finish:
  RETURNED         $  9.22  group disbanded  -> note only [others-left]
  AWAITING REVIEW  $  6.10  player timeout   -> request return + note [inactive]
  RETURNED         $  2.00  lobby timeout    -> note only [lobby]
  …
Send these notes to 8 people? [y/N] y
```

(The fee-inclusive totals above are illustrative -- Prolific's fee on bonuses is about 33% --
the real ones come back from Prolific at the set-up step.)

It picks the most recent extracted run (say `--run <timestamp>` to choose), keeps a ledger
under the run directory so nothing is ever paid twice, and words each person's note from
their recorded exit reason. Stopping at any question leaves everything before it done and
everything after it not; re-running picks up where you stopped. Notes are recorded per
person as they are sent, so a re-run after a failure part-way messages only the people who
have not heard from you.

It also reads the run's game table and warns if the games' condition or tangram set is not
what the session was set up for, which means either the batch was created with the wrong
treatment or you are paying the wrong run.

There are three populations, not two. Alongside the finishers and the removed players,
`pay` reads the lobby timeouts straight from Prolific: they never reach a game, so they
appear in no export, and until this existed nothing ever paid them the amount the Sorry page
promises. `--skip-lobby` leaves them out.

**Removed players and lobby timeouts are paid only if their submission is returned or
awaiting review.** Every one of those rows is joined to its Prolific submission first. One
that is already `APPROVED` was paid the full base reward when it was approved, so the partial
payment is skipped and named, as is a `REJECTED` one or a row with no submission at all. The
skipped rows are printed with the reason before anything is set up.

Six refusals are worth knowing about, because each stops the whole command:

- **A total that is too large.** Each population has a ceiling derived from how many people
  are in it, so a scoring bug that inflates everyone is caught even though no single amount
  looks wrong. `--max-total` overrides it; `--max-each` (default `BASE_PAY + MAX_BONUS`, so
  $20) refuses any single amount above a whole game's pay.
- **Someone another run already paid.** Exports are cumulative, so this usually means the
  payment files were not scoped to one batch, or that this is a second export of a session
  already paid. It names the people and the run that paid them.
- **Rows that changed after set-up.** A bulk payment pays what it was set up with. If the
  CSV was re-extracted, or someone was approved in the meantime and dropped out of the
  payable rows, `pay` names the difference and stops; cancel the bulk payment in the Prolific
  UI, remove that population's entry from the ledger, and re-run to set it up afresh.
- **A bulk payment for the wrong amount.** Prolific's reply to the set-up call carries the
  amount it understood, in cents; if that is not the total requested, nothing is paid.
- **Over budget.** `setup` records the session's cost ceiling (or `--budget`) in the session
  file, and `pay` adds this payment to what the session has already paid; going past the
  budget stops the command unless `--force-budget` is passed, and then it asks again.
- **A pay call that was started and never confirmed.** The attempt is written to the ledger
  *before* the call, so a request that timed out after Prolific processed it cannot look
  unpaid. Resolving it means checking the bulk payment in the Prolific UI and editing the
  ledger, not re-running.

**16. Nothing else.** This session's players were added to the blocklist group as they
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

**`pay` says someone was already paid by another run.** Look at `run_meta.json` in both run
directories. If the older run's export covered this session too, you are about to pay it
twice and the refusal is correct. If the payment files were written before they were scoped
to a batch, re-extract with `analysis/extract_run.py --batch <id>`.

**`publish` refuses the time you gave it.** `--at` is read in the timezone your announced
`--time` names. The message says what `--at` resolved to and what participants were told;
one of the two is wrong. `--force-time` overrides it if the gap is deliberate.

**`setup` refuses because the template has drifted.** The reward, the completion codes or
the codes' actions on the study it copied no longer match what `experiment/shared/constants.js`
and this runbook expect. Fix that study in Prolific, or pin a good one with
`PROLIFIC_TEMPLATE_STUDY`. If the message says a code lacks `ADD_TO_PARTICIPANT_GROUP`, the
usual cause is that no blocklist group was found: seed it first.

**`pay` skipped someone as APPROVED.** Their submission was approved -- by `approve`, by
hand, or by Prolific's automatic approval -- so they were already paid the full base reward.
The partial payment is not sent, because it would pay them twice. If they were owed a bonus
on top, pay it by hand in the Prolific UI.

**`pay` says the rows have changed since set-up.** The bulk payment was created from an
earlier version of the CSV or of the submissions. Cancel it in the Prolific UI, remove that
population's entry from `data/runs/<run>/prolific_payments.json`, and re-run `pay`.

**`pay` refuses because the session is over budget.** The budget is the cost ceiling
`setup` printed (or `--budget`). Check the amounts first; if the overrun is real and right,
`--force-budget` lets you confirm it.

**`pay` warns that the run's treatment is not the session's.** Either the Empirica batch was
created with a different treatment from the one `setup` was told, or this is another
session's run. Look at `run_meta.json` and the admin panel before paying.

**`prepare` sets responses aside as malformed.** A response that does not carry three
questions is not counted eligible. If most responses have a different number, the survey
itself has changed; re-run with `--expect-questions N` once you have checked why.

## Reference: what the studies look like

Values from the final pilot, which is the session that produced the committed pilot data.
`setup` copies them from the most recent game study; pin a specific one with
`--template-study`, or permanently with `PROLIFIC_TEMPLATE_STUDY` in `.env`. The reward and
the three completion codes are checked against `experiment/shared/constants.js` and a
mismatch stops `setup`, so the chain of copies cannot quietly change what participants are
paid.

| | Screening survey study | Game study |
|--|--|--|
| reward | $0.30 (`30`) per response | $12.00 (`1200`) |
| places | `--survey-places`, a ceiling; you pay per response, so size it to need (60 for 40 eligible) and run `close` once `prepare` has run | the players you expect |
| time | 1 min | 50 min estimated, 123 max |
| device | desktop | desktop |
| URL | `https://prolific.com/surveys/<survey_id>` | the server, with `?PROLIFIC_PID={{%PROLIFIC_PID%}}&STUDY_ID={{%STUDY_ID%}}&SESSION_ID={{%SESSION_ID%}}` |
| filters | US, fluent English, `participant_group_blocklist` | `participant_group_allowlist` (added by `prepare`) |
| completion codes | one, `COMPLETED` | `C2I8XDMC` finished (`MANUALLY_REVIEW` + add to blocklist) · `CMZUY3MK` lobby timeout (`REQUEST_RETURN`) · `CFTYDMIY` removed early (`REQUEST_RETURN` + add to blocklist) |

The three codes are defined in `experiment/shared/constants.js`, and the ones quoted in this
document are copied from it; `setup` checks the template study's codes against that file,
not against this page, so if the two ever disagree the file is right and this page is stale.
`setup` also checks the actions on each code: the finished code must not carry
`AUTOMATICALLY_APPROVE`, the partial and lobby-timeout codes must carry `REQUEST_RETURN`,
and the finished and partial codes must carry `ADD_TO_PARTICIPANT_GROUP`. Prolific requires
a `privacy_notice` on any survey-backed study; `setup` copies it from the template and
refuses to proceed without one.

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

**Removed players** -- disbanded group, failed accuracy check, too few groups, a batch the
researcher stopped, or idling out -- are paid by **returning the submission and receiving
their partial pay as a bonus**, never by approval. `computePartialPay` in `experiment/server/src/compensation.js` already bundles
prorated base pay together with the earned bonus into one number, so approving would pay the
full base reward on top of that. This is also exactly what Prolific recommends for
participants who cannot be matched in live studies: partial payment by bonus, a return
request, and a message explaining it. The return request is automatic through the
completion-code action; `pay` sends the message.

**Lobby timeouts** -- people who arrived on time but for whom no game could be formed -- are
paid the `LOBBY_TIMEOUT_PAY` their Sorry page promises, the same way: a bonus plus a return
request plus a note. They are the one group the data pipeline cannot see, because Empirica
creates a player record only once someone is placed in a game, so they appear in neither
`bonuses.csv` nor `early_ended.csv`. `pay` finds them by looking for their completion code
among the study's submissions instead. They stay eligible for later sessions, and their
note says so.

Two facts about the bonus API that shape `pay`:

- **Paying is a two-step call, and the first step is free.** Setting up a bulk payment
  charges nothing and returns Prolific's total including its fee (about 33% on bonuses).
  That is why `pay` shows you that total before asking to pay.
- **The pay call is not idempotent.** Sending it twice pays everyone twice. `pay` records
  each bulk payment id and its paid time in `data/runs/<run>/prolific_payments.json` and
  refuses to pay a population that already has a paid time. Do not delete that file to
  "retry".

Amounts are sent as decimals (`1.50` means $1.50) and come back in cents; `pay` checks that
the cents Prolific echoes back are the total it asked for. `--max-each` (default
`BASE_PAY + MAX_BONUS`, so $20, read from `shared/constants.js`) and `--max-total` refuse
anything that looks wrong before it is sent. A partial or lobby-timeout bonus goes only to a
submission that is returned or awaiting review; an approved one already received the base
reward.

## Reference: the data

`copy_tajriba.sh` leaves each export as
`experiment/data/<timestamp>/empirica-export-<timestamp>.zip`, one directory per export
named by the zip's own timestamp, which is the layout `extract_run.py` and the `Makefile`
look for, so every backup taken during a session is a usable export. `extract_run.py`
unzips one, strips the Prolific ids from the raw CSVs, writes `bonuses.csv` and
`early_ended.csv` (which keep the ids, for `pay`) into the gitignored
`data/runs/<timestamp>/`, and registers the timestamp in `data/<dataset>/runs.txt`. `combine_runs.py` stacks the registered runs into
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

The five messages `session.py` sends are in `operations/messages/`; edit the wording
there. `{time}` and `{amount}` are filled in per session and per person. Which note a
removed player gets is decided by the exit reason the server recorded, from the
`EXIT_REASONS` list in `experiment/shared/constants.js`; `session.py` refuses to start if
that list holds a reason it has no wording for.

### `reminder.txt` -- sent by `message`, about ten minutes before the session

> Hello! Thank you for signing up for our study. Just a reminder that the study will show up on your Prolific dashboard in a few minutes, at exactly {time}. This experiment depends on synchronous and real-time participation, so please join as soon as you see it. If it doesn't appear after refreshing, please let us know.

### `partial_payment.txt` -- sent by `pay` to removed players

Used when the removal was recorded as `low accuracy`, or with no reason at all: the wording
is neutral about whose doing it was.

> Hello, and thank you for taking part in our study today.
>
> Unfortunately the session ended before the game could be completed. This kind of study needs enough players to stay online together for the whole game, so sessions sometimes end early.
>
> We have sent you a partial payment of ${amount} through Prolific for the time you spent. You will also see a request to return the submission, since the study was not completed. Returning it does not affect the partial payment.
>
> Thank you again for your time, and sorry for the inconvenience.

### `lobby_payment.txt` -- sent by `pay` to lobby timeouts

Used for participants who arrived but for whom no game could be formed. They were not able
to take part at all, so the note says plainly that nothing went wrong on their end and that
they remain eligible for a later session.

> Hello, and thank you for signing up for our study today.
>
> Unfortunately we were not able to form a complete group at the scheduled time, so the game could not start and you were not able to take part. Nothing went wrong on your end -- this kind of study needs everyone in a group online at the same moment, and sometimes too few people arrive.
>
> We have sent you ${amount} through Prolific for the time you spent waiting. You will also see a request to return the submission, since the study itself did not run. Returning it does not affect the payment.
>
> You are still eligible for this study, and we would be glad to have you in a future session.
>
> Thank you again for your time, and sorry for the inconvenience.

### `partial_payment_inactive.txt` -- sent by `pay` to players removed for idling

Used when the removal was recorded as `player timeout`. The game removes a player after
`MAX_IDLE_ROUNDS` rounds without a response, and pays base pay prorated to the time spent
with no bonus (`compensation.js`). The note says so plainly, without blame, and asks for the
submission to be returned.

> Hello, and thank you for taking part in our study today.
>
> The game removes a player after several rounds without a response, so that the other players in the group are not left waiting, and that is why your session ended early.
>
> We have sent you ${amount} through Prolific: the study's base pay, prorated to the time you spent in the game. The bonus for correct answers is not included. You will also see a request to return the submission, since the study was not completed. Returning it does not affect the payment.
>
> Thank you again for your time.

### `partial_payment_stopped.txt` -- sent by `pay` when the researcher stopped the batch

Used when the removal was recorded as `game terminated`, which Empirica writes when a batch
is stopped from the admin panel mid-game. The pay is the same as for a disbanded group (base
prorated to time spent plus the bonus earned so far), but the note says that the session was
stopped on our side rather than that other players left, and that the participant remains
eligible.

> Hello, and thank you for taking part in our study today.
>
> We had to stop this session early on our side, so your game could not continue. Nothing went wrong on your end.
>
> We have sent you a partial payment of ${amount} through Prolific: the study's base pay, prorated to the time you spent in the game, plus the bonus you had earned so far. You will also see a request to return the submission, since the study was not completed. Returning it does not affect the payment.
>
> You are still eligible for this study, and we would be glad to have you in a future session. Thank you again for your time, and sorry for the inconvenience.

### `partial_payment_others_left.txt` -- sent by `pay` to removed players

Used when the removal was recorded as `group disbanded`, `insufficient groups` or
`insufficient groups after accuracy check`, where the participant can be told plainly that
nothing went wrong on their end.

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
  into a game are good candidates to add to a group and invite to a later session. `pay`
  now sends them the lobby-timeout payment and a note saying they are still eligible, so
  the invitation is not the first they hear from you.
