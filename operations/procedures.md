# Running a data-collection session

This is the runbook for one session of the reference game: recruiting nine (or eighteen, or
twenty-seven) people on Prolific to be online at the same moment, running the game, and
paying everyone afterwards. Recruitment, approvals and payments are done by hand on the
Prolific website, and the game is run from the Empirica admin panel. Two commands help:
`make tally` says which treatment the next session should run, and `make payments` works out
what each Prolific study still owes and writes the lines to paste into Prolific's bulk bonus
form. The procedure and the numbers in it come from the pilot sessions of February and March
2026 and the first full-sample sessions of September 2026.

The game needs everyone online at once, so recruitment happens in two stages a few minutes
apart: participants first answer a three-question screening survey saying they can make the
session, then the game study is delivered to exactly those people at the announced time. The
manuscript describes this in the Recruitment paragraph of `writing/preregistration/main.tex`.

## Before your first session

**1. Environment.** Run `uv sync`, and make sure the repository-root `.env` has
`PROLIFIC_TOKEN` (your API token from Prolific's settings), which `make payments` uses to read
submissions; it never writes to Prolific. Put `export DATASET=full` in your shell profile so
the data commands need no flag.

**2. Create the blocklist group** on Prolific, a participant group named `Played the game`,
and seed it with everyone who has already played, pilot participants included, so none of
them can join the full sample. After that it maintains itself through the completion codes'
actions (see "Reference: eligibility").

**3. Deploy the current bundle** to the server (`experiment/README.md`, "Deploying a new
build"), and wipe the server's database first (see "Before every session").

## Before every session

The evening session of 22 September 2026 showed what an unprepared server costs: with five
games running at once, games ran 64 to 74 minutes instead of 42 to 48, participants saw
freezes of several minutes, and the server finally ran out of memory and crashed while the
last game's players were filling in the exit survey. Empirica v1.12.1 (tajriba v1.7.2) leaks
memory as players disconnect, and the leak kept growing after the session with nobody
playing. Until an upgraded Empirica has run a clean session, do all of this every time:

1. **Back up, wipe and restart.** Copy `~/empirica/.empirica/local/tajriba.json` off the
   server, delete it, and restart the service. Empirica exports are cumulative, so the
   previous session's games otherwise stay loaded (the crashed session started at a quarter
   of the server's memory before anyone arrived) and a restart after a crash has to replay
   them all, which took nine minutes. Everything in the old file is already in the backups.
2. **Run two or three games at a time.** The sessions with two or three games had no
   complaints; the five-game session had freezes throughout. Empirica has an open issue
   about games slowing down as more run concurrently (empiricaly/empirica#593), so this may
   matter even after the memory leak is fixed.
3. **Set a memory alert** in the DigitalOcean monitoring, at 75%. If it fires during a
   session, start no new games until the running ones finish.
4. **Freeze the bundle.** The server restarts whenever `~/empirica/empirica.tar.zst` changes,
   so an upload during a session ends every game in progress. Deploy before anyone is invited.

## The session, step by step

### Lead time: almost none

In the pilot, screening responses arrived within 4 to 15 minutes of the survey going live --
one survey collected 43 responses in under 4 minutes -- and the surveys went up only 12 to
20 minutes before the session they recruited for. A whole session fits inside about an hour,
so the steps below are written as time before the session start, `T`. A short window is
arguably better than a long one: the people answering are at their computers right now.

### T-60: pick the treatment

Run `make tally`. You need 10 intact games in each of the eight (condition, tangram set)
cells, so the next session runs whichever cell has the fewest:

```text
7 intact nine-player game(s) in data/full/games.csv, 3 that lost a player or did not finish:
  condition          set intact  partial  incomplete
  refer_separated      0      0        0           0   <- emptiest
  refer_separated      1      0        0           0
  refer_mixed          0      1        0           0
  ...
  Target: 20 intact games per condition (10 per cell) -- refer_separated 0/20, refer_mixed 3/20, ...
  Cap: 10 of 120 games started, 110 left.
```

**Intact** means the game finished with all nine players still in it, which is what the
preregistered stopping rule counts and what fills a cell. **Partial** games finished a
player short: their data is still used, but they do not count towards the target.
**Incomplete** games never finished. The last two lines are the stopping rule, which ends
recruitment at whichever limit comes first: 20 intact games in every condition, or 120 games
started in total. The cap counts every game that began Phase 1, including partial and
incomplete ones; a lobby that never formed a game does not count. `tally` prints a `STOP`
line when either limit is reached.

Run one treatment per batch, so that everyone who arrives can fill any game in it. Empirica
cannot move players between games of different treatments.

### T-45: create the screening survey and the game study

Duplicate the previous session's screening survey and game study on Prolific, then change
the session time in the survey's availability question and in both titles, the number of
places, and the study's internal name (for example `full sample batch 6`). The public names
are all the same, so the internal name is how you and `make payments` tell studies apart.
Check every value in "Reference: what the studies look like", especially the reward, the
three completion codes and their actions: a wrong code or action is copied silently into
every later session.

Size the survey's places to need, because you pay for every response: 60 places is about
right when you want 40 eligible respondents. For three games you want about 40 eligible
responses, since roughly 75% of the people who say they can make it turn up.

### T-30: bring up Empirica

**Have three windows open**: the admin panel, Sentry filtered to the `production`
environment, and the server's log (`journalctl -u empirica -f`). Server-side callback errors
never reach Sentry, which is browser-only, so the log is the only place they appear. Keep
the DigitalOcean memory graph open as well.

**Create and start the batch before any participant can arrive**, sized for all the games
you intend to run, all of one treatment. A batch created after assignment has begun kicks
players out of a game already in progress, and responses arrive within seconds of the survey
opening.

**Start the backup loop**, under `caffeinate -i` on a laptop so that the machine does not
sleep and stop backing up without saying so:

```bash
caffeinate -i bash operations/copy_tajriba.sh
```

Every five minutes it takes an export into its own `experiment/data/<timestamp>/` directory,
with the server log beside it, and it flags any callback error it finds in the log. A failed
copy is retried at the next interval; the loop gives up only after three failures in a row.

### T-25: open the survey

Publish the screening survey and watch the responses arrive. Check that the blocklist group
is listed in its filters first.

### T-15: build the allowlist and close the survey

Put everyone who answered "Yes" to all three questions into a new participant group, and set
that group as the game study's `participant_group_allowlist`. Because the study points at a
group rather than a list, anyone added to the group later becomes eligible without touching
the study.

Then stop the screening survey: every further response costs its reward and tells someone
they are expected at a session they will not be sent. Approve the screening submissions so
the respondents are paid the same day.

### T-10: send the reminder

Message the allowlist group with the reminder in "Message templates", with the session time
filled in.

### T: publish

Publish the game study at exactly the announced minute, and check that it has the allowlist
before you do: without one, a $12 study opens to everyone on Prolific. Then watch the admin
panel for arrivals and game progress, Sentry for client errors, and the memory graph. A few
participants will message asking where the study is; the reminder told them it appears
exactly at the announced time.

### After the session

**1. Stop the batch** once the last game has ended and its players have had a few minutes
for the exit survey, take one more export with `bash operations/copy_tajriba.sh --once`, and
stop the backup loop.

**2. Run the export through the pipeline** (the `process-new-run` procedure in
`.claude/skills/`, or by hand):

```bash
make smoke ZIP=experiment/data/<ts>/empirica-export-<ts>.zip   # check the export first
uv run python analysis/extract_run.py experiment/data/<ts>/empirica-export-<ts>.zip --dataset full
make combine process-no-filter test DATASET=full   # `process` instead runs the LLM message filter, which costs Vertex AI credit
```

If the server was not wiped since the export already in `runs.txt`, the new export is a later
snapshot of the same server and replaces it: remove the older timestamp from `runs.txt`
before combining, which refuses duplicated records anyway.

**3. Work out what each study owes** with `make payments`. It reads every export in
`runs.txt`, groups the players by the Prolific study recorded from their study link, and asks
Prolific (read-only) for each study's submissions, their status and the bonuses already
paid, which also finds the lobby-timeout participants. It prints a table per study and writes
`data/payments/full/<date>_<internal name>_<id>/`:

```text
full sample batch 4  [6ab3388192c1750e391244c4]  games: 03RTP6 2XQ788 F92CE8
    ready to pay: bonus 26 ($175.59), partial 1 ($10.13), lobby 9 ($18.00)
    folder: 2026-09-23_full-sample-batch-4_1244c4/
```

`bonus.csv`, `partial.csv` and `lobby.csv` hold `participant_id,amount` lines to paste into
that study's bulk bonus form, and `status.csv` lists everyone with the reason anything owed
is not ready (a game still running, or no submission in the study). An approved partial
or lobby submission already received the $12 base, so it is listed only for any amount above
that. The folder is rewritten on every run and contains
Prolific ids, which is why `data/payments/` is gitignored.

**4. On each study's submissions page:**

- **Approve the finishers**, the submissions with the finished code `C2I8XDMC`. Approval pays
  the $12 base reward. Before approving, check that everyone approved appears in that study's
  `bonus.csv` or `status.csv`: a finished code without a completed game in the data is worth a
  look.
- **Make sure removed players and lobby timeouts are returned, not approved.** Their codes
  request a return automatically, but a submission left in *awaiting review* is eventually
  approved by Prolific, which pays the full base reward on top of the partial payment.
- **Paste the bonus files** into the study's bulk bonus form: `bonus.csv`, `partial.csv` and
  `lobby.csv` can go in together or separately. Prolific shows the fee-inclusive total
  before you confirm.
- **Message the removed players and lobby timeouts** with the matching note in "Message
  templates"; `status.csv` has each person's exit reason.

**5. Run `make payments` again.** Everyone just paid now shows as settled; anything still
listed was missed.

## If something goes off script

**Someone asks to be added after the allowlist was built.** Add them to the session's group
on Prolific. The study allowlists the group, so they become eligible immediately.

**`make payments` lists someone as owed but not ready.** `status.csv` gives the reason. "No
submission from this participant in this study" usually means they reached the game through
another session's link; check which study their submission is in. "Game still running"
means the export was taken before the game ended; take a new export once it has.

**A participant was paid by mistake.** Prolific cannot reverse a bonus. `make payments`
subtracts what Prolific has already paid, so re-running it never tells you to pay the same
person twice, but check `status.csv` before pasting a file you edited by hand.

**The Empirica server died mid-session.** Participants see "Just a moment" or a 502 while
their browsers retry.

1. *Look.* `ssh root@$EMPIRICA_SERVER "systemctl status empirica; journalctl -u empirica -n 200 --no-pager"`
   and the DigitalOcean memory graph. The service restarts itself, but after a crash it has
   to replay the whole database before it answers, which took nine minutes on 23 September.
   **Do not restart it again while it loads**: a manual restart throws away the loading
   done so far. Watch `journalctl -u empirica -f` for `server: started`.
2. *Decide.* A restart does not resume the games that were running. Do not leave nine
   people in a game that cannot continue: stop the batch in the admin panel, which sends
   everyone to the exit survey and the partial code, and tell them in a Prolific message.
   Participants who had finished but were on the exit survey when the server died need the
   finished code sent to them by message.
3. *Save the data.* The newest zip under `experiment/data/` is at most five minutes old, and
   `empirica export` reads the database file directly, so it works even while the server is
   down: `ssh root@$EMPIRICA_SERVER "cd ~/empirica && empirica export --out /tmp/crash.zip"`.
4. *Pay the players of an interrupted game by hand.* A game that never reached
   `onGameEnded` leaves its players looking active, with no exit reason and no partial pay,
   so `make payments` lists them as finishers in a game still running and marks them not
   ready. Their pay is base prorated to the minutes they played plus the bonus they had
   earned (`experiment/server/src/compensation.js`); the export's `gameStartTime`,
   `minutesSpent` and `bonus` columns are what you need. Pay it as a bonus, make sure their
   submissions are returned rather than approved, and send the "session stopped" note.
5. *Do not reuse the batch.* Create a fresh one for any replacement session, and list the
   crashed game in `data/full/exclude_games.txt` if it should not be analyzed.

## Reference: what the studies look like

Values from the final pilot, which the full-sample studies are duplicated from.

| | Screening survey study | Game study |
|--|--|--|
| reward | $0.30 per response | $12.00 |
| places | a ceiling; you pay per response, so size it to need (60 for 40 eligible) and stop the survey once the allowlist is built | the players you expect |
| time | 1 min | 50 min estimated, 123 max |
| device | desktop | desktop |
| URL | `https://prolific.com/surveys/<survey_id>` | the server, with `?PROLIFIC_PID={{%PROLIFIC_PID%}}&STUDY_ID={{%STUDY_ID%}}&SESSION_ID={{%SESSION_ID%}}` |
| filters | US, fluent English, `participant_group_blocklist` (`Played the game`) | `participant_group_allowlist` (this session's group) |
| completion codes | one, `COMPLETED` | `C2I8XDMC` finished (manual review, add to `Played the game`) · `CMZUY3MK` lobby timeout (request return) · `CFTYDMIY` removed early (request return, add to `Played the game`) |

The completion paths are `https://app.prolific.com/submissions/complete?cc=<code>`; the exit
screens link participants straight to them. The three codes are defined in
`experiment/shared/constants.js`, and `make payments` reads them from there, so if this page
and that file ever disagree, the file is right and this page is stale. The finished code
must not approve automatically, because approval should follow a check against the game
data; the partial and lobby-timeout codes must request a return; and the finished and partial
codes must add the participant to `Played the game`. Prolific requires a privacy notice on
any survey-backed study.

## Reference: eligibility, and why lobby timeouts stay eligible

The design is between subjects, so nobody may play twice. Two filters, both pointing at
participant groups rather than lists of people:

- **`participant_group_allowlist`** on the game study, the group built for this session.
  Only its members can see the study.
- **`participant_group_blocklist`** on the screening survey, one standing group,
  `Played the game`, of everyone who has ever been placed in a game.

**The blocklist maintains itself.** The two completion codes that mean "saw the task",
`C2I8XDMC` and `CFTYDMIY`, carry an "add to participant group" action, so Prolific adds each
player to the group the moment they submit. The lobby-timeout code `CMZUY3MK` carries no
such action, and that is what keeps those participants eligible: they never saw a tangram,
they are already screened, and they have shown they turn up on time, so they are the best
people to invite to a later session.

## Reference: how people are paid

**Finishers** are approved, which pays the $12 base reward, and then receive their earned
bonus.

**Removed players** -- disbanded group, failed accuracy check, too few groups, a batch the
researcher stopped, or idling out -- are paid by **returning the submission and receiving
their partial pay as a bonus**, never by approval. The server's `computePartialPay`
(`experiment/server/src/compensation.js`) already bundles prorated base pay with the earned
bonus into one number, so approving would pay the full base reward on top of it. Players
removed for inactivity get the prorated base pay only, without the bonus. This is what
Prolific recommends for participants who cannot be matched in live studies: partial payment
by bonus, a return request, and a message explaining it.

**Lobby timeouts** -- people who arrived on time but for whom no game could be formed -- are
paid the `LOBBY_TIMEOUT_PAY` ($2) their Sorry page promises, the same way: a bonus, a return
request and a note. They are the one group the data pipeline cannot see, because Empirica
creates a player record only once someone is placed in a game, so `make payments` finds them
by their completion code among the study's submissions.

`make payments` applies all of this: a partial or lobby amount is listed in full for a
submission that is returned or awaiting review; for one that was approved anyway, which
already received the $12 base, only the part above $12 is listed (a player removed late in
the game with bonuses earned can be owed more than the base); and whatever Prolific has
already paid on a submission is subtracted. Prolific's fee
on bonuses is about 33%, shown before you confirm a bulk bonus.

## Reference: the data

`copy_tajriba.sh` leaves each export as
`experiment/data/<timestamp>/empirica-export-<timestamp>.zip`. `extract_run.py` unzips one,
strips the Prolific ids from the raw CSVs into the gitignored `data/runs/<timestamp>/`, and
registers the timestamp in `data/<dataset>/runs.txt`; `combine_runs.py` stacks the registered
runs into the committed `data/<dataset>/raw_anonymized/`; `process_data.py` produces the
analysis tables and derived metrics. Only `make payments` reads the Prolific ids, straight
from the export zips.

**Exports are cumulative.** `empirica export` dumps the whole server, not just the last
session, so if the server was not wiped between sessions the newest export contains every
earlier one. `combine_runs.py` refuses duplicated records across runs, so keep one export per
server state in `runs.txt`: the newest export of a server replaces its earlier exports.

## Message templates

Which note a removed player gets depends on the exit reason the server recorded, which
`status.csv` shows. `{time}` and `{amount}` are filled in by hand.

### Reminder, about ten minutes before the session

> Hello! Thank you for signing up for our study. Just a reminder that the study will show up on your Prolific dashboard in a few minutes, at exactly {time}. This experiment depends on synchronous and real-time participation, so please join as soon as you see it. If it doesn't appear after refreshing, please let us know.

### Removed, reason `low accuracy` or none recorded

The wording is neutral about whose doing it was.

> Hello, and thank you for taking part in our study today.
>
> Unfortunately the session ended before the game could be completed. This kind of study needs enough players to stay online together for the whole game, so sessions sometimes end early.
>
> We have sent you a partial payment of ${amount} through Prolific for the time you spent. You will also see a request to return the submission, since the study was not completed. Returning it does not affect the partial payment.
>
> Thank you again for your time, and sorry for the inconvenience.

### Removed, reason `group disbanded`, `insufficient groups` or `insufficient groups after accuracy check`

> Hello, and thank you for taking part in our study today.
>
> Unfortunately the other players in your group left the game, so your session could not continue. Nothing went wrong on your end -- this kind of study needs everyone in a group to stay online together for the whole game.
>
> We have sent you a partial payment of ${amount} through Prolific for the time you spent. You will also see a request to return the submission, since the study was not completed. Returning it does not affect the partial payment.
>
> Thank you again for your time, and sorry for the inconvenience.

### Removed, reason `player timeout` (inactivity)

The pay is base prorated to the time spent, with no bonus; the note says so plainly and
without blame.

> Hello, and thank you for taking part in our study today.
>
> The game removes a player after several rounds without a response, so that the other players in the group are not left waiting, and that is why your session ended early.
>
> We have sent you ${amount} through Prolific: the study's base pay, prorated to the time you spent in the game. The bonus for correct answers is not included. You will also see a request to return the submission, since the study was not completed. Returning it does not affect the payment.
>
> Thank you again for your time.

### Removed, reason `game terminated` (the researcher stopped the batch)

> Hello, and thank you for taking part in our study today.
>
> We had to stop this session early on our side, so your game could not continue. Nothing went wrong on your end.
>
> We have sent you a partial payment of ${amount} through Prolific: the study's base pay, prorated to the time you spent in the game, plus the bonus you had earned so far. You will also see a request to return the submission, since the study was not completed. Returning it does not affect the payment.
>
> You are still eligible for this study, and we would be glad to have you in a future session. Thank you again for your time, and sorry for the inconvenience.

### Lobby timeout

They were not able to take part at all, so the note says plainly that nothing went wrong on
their end and that they remain eligible for a later session.

> Hello, and thank you for signing up for our study today.
>
> Unfortunately we were not able to form a complete group at the scheduled time, so the game could not start and you were not able to take part. Nothing went wrong on your end -- this kind of study needs everyone in a group online at the same moment, and sometimes too few people arrive.
>
> We have sent you ${amount} through Prolific for the time you spent waiting. You will also see a request to return the submission, since the study itself did not run. Returning it does not affect the payment.
>
> You are still eligible for this study, and we would be glad to have you in a future session.
>
> Thank you again for your time, and sorry for the inconvenience.

## What the pilots showed

The show-up rate held steady at roughly 75% across sessions. "Invited" below means the people
who said on the form that they could make the session.

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

For a single nine-player game, inviting about 15 people has been enough. For two concurrent
games, 35 to 40 invitations worked and 28 did not.

## Operational lessons

- **Say that the study appears exactly at the announced time.** Participants go looking for
  it on their dashboard several minutes early and message you when they cannot find it.
- **Do not require a reply to confirm.** Some participants miss the instruction and message
  anyway, and unconfirmed participants show up regardless, so the confirmation step adds
  monitoring work without improving attendance.
- **Weeknight evening sessions were harder to fill** than the weekend late-morning session.
  The Wednesday 6pm pilot session was the weakest.
- **Longer instructions cost you players.** The experiment 2 pilot, which has longer
  instructions, lost more participants between logging on and being placed in a game.
- **Tell participants to keep their sound on** and to watch for the sound that plays when
  the game starts.
- **Keep sessions small until the server is proven.** Five concurrent games on 22 September
  2026 made every game slower and ended in a crash (see "Before every session").
- **Consider re-contacting the near misses.** Participants who logged on but did not get into
  a game have been screened and turned up on time; they stay eligible, and their lobby note
  says so, so an invitation to a later session is not the first they hear from you.
