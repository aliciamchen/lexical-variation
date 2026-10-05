# Running a data-collection session

This is the runbook for one session of the reference game: recruiting five games' worth of
people (45 players, all in one treatment) on Prolific to be online at the same moment,
running the games, and paying everyone afterwards. Recruitment, approvals and payments are done
by hand on the Prolific website, and the games are run from the Empirica admin panel. Two
commands help: `make tally` says which treatment the next session should run, and `make
payments` works out what each Prolific study still owes and writes the files to paste into
Prolific's bulk bonus form. The numbers below come from the full-sample sessions of September
and October 2026.

The game needs everyone online at once, so recruitment happens in two stages a few minutes
apart: participants first answer a three-question scheduling survey saying they can make the
session, then the game study is delivered to exactly those people at the announced time. The
manuscript describes this in the Recruitment paragraph of `writing/preregistration/main.tex`.

## Before every session

1. **Back up, wipe and restart the server, while no session is running.** Copy
   `~/empirica/.empirica/local/tajriba.json` off the server, delete it, and restart the
   service. Empirica exports are cumulative, so without a wipe every earlier game stays loaded,
   and the server slows down with everything it holds as well as with the games running at
   once. Everything in the old file is already in the backups. Restarting or wiping ends any
   game in progress, so do it only between sessions.
2. **Plan five games, all of one treatment.** A sixth game slows every game down. In the three
   six-game sessions the typical pause between stages was 2.8 to 4.1 seconds, each game had 4 to
   27 pauses longer than ten seconds, and 10 of 18 games ran past 60 minutes, which costs
   overtime pay and draws complaints. In the five-game sessions the typical pause was about 1.5
   seconds, long pauses were rare, and no game ran past 60 minutes. To collect faster, run more
   sessions in a day rather than more games per session. One treatment per session
   also means nobody is left without a game because the open games are of another treatment.
3. **Set a memory alert** in the DigitalOcean monitoring, at 75%. If it fires during a
   session, start no new games until the running ones finish.
4. **Freeze the bundle.** The server restarts whenever `~/empirica/empirica.tar.zst` changes,
   so an upload during a session ends every game in progress. Deploy before anyone is invited
   (`experiment/README.md`, "Deploying a new build").

## The session, step by step

### Lead time: about an hour

Scheduling-survey responses arrive within minutes of the survey going live, so a whole session
fits inside about an hour, and the steps below are written as time before the session start,
`T`. A short window works well: the people answering are at their computers right now.

### T-60: pick the treatment

Run `make tally`. Collection runs to the preregistered cap of 120 started games, balanced by
started games: 30 per condition, 15 per treatment (a condition with one of the two tangram
sets). The next session runs the treatment marked `<- next`, the one with the fewest started
games:

```text
33 intact nine-player game(s) in data/full/games.csv, 31 that lost a player or did not finish:
  condition          set intact  partial  incomplete  started
  refer_separated      0      3        5           0     8/15
  ...
  social_mixed         1      5        1           0     6/15   <- next
  ...
  Started: 64 of 120, 56 left; target 30 per condition, 15 per treatment -- refer_separated 16/30, ...
  Intact (the preregistration's other limit is 20 per condition) -- refer_separated 5/20, ...
```

**Intact** games finished with all nine players, **partial** games finished a player or more
short, and **incomplete** games ended early; all three are started games, which is what the
target and the cap count. A lobby that never formed a game does not count. The intact counts
are shown for reference. `tally` prints a `STOP` line once 120 games have been started; games
already underway then finish.

### T-45: create the scheduling survey and the game study

Duplicate the previous session's scheduling survey and game study on Prolific, then change the
session time in the survey's availability question and in both titles, the number of places,
and both internal names (`full-sample scheduling survey batch 22`, `full sample batch 22`).
The public names are all the same, so the internal name is how you and `make payments` tell
studies apart. Check every value in "Reference: what the studies look like", especially the
reward and the three completion codes: a wrong value is copied silently into every later
session. Add the previous session's game study to the survey's "Exclude participants from
other studies" filter, so that nobody who has played can sign up again.

**How many to recruit.** A game starts only when nine people are ready, meaning they arrived
and passed the quiz. In the four six-game sessions, between 56% and 70% of the allowlist ended
up ready, and the most recent session (4 October) was the lowest: 82 people on the allowlist
gave 46 ready players, so the sixth game never filled. Planning for that low rate means about
16 eligible people per game: 80 for five games and 95 to 100 for six. About three in four
survey responses come back eligible (the rest answer "No" to a question or return the survey),
so set the survey's places as a ceiling and stop it once you have enough:

| Games | Eligible people to allowlist | Survey responses to collect | Survey cost (before fees) |
|-------|------------------------------|-----------------------------|---------------------------|
| 5     | about 80                     | about 105                   | about $32                 |
| 6     | 95 to 100                    | about 130                   | about $39                 |

The buffer above nine per game is what absorbs the people who never open the study, quiz
failures, and slow arrivals. Its cost is the lobby timeouts at $2 each when more people arrive
than the games can take: 0 to 14 per session so far.

### T-30: bring up Empirica

**Have three windows open**: the admin panel, Sentry filtered to the `production`
environment, and the server's log (`journalctl -u empirica -f`). Server-side callback errors
never reach Sentry, which is browser-only, so the log is the only place they appear. Keep
the DigitalOcean memory graph open as well.

**Create one batch per game, all of the session's treatment, and start them before
publishing.** Empirica spreads arrivals at random over the unstarted games inside a batch, so
a batch with several games fills all of them slowly; separate batches fill in the order they
were created, one game at a time. When a game starts, the players assigned to it beyond the
nine who play are moved to an unstarted game of the same treatment in any batch. If none has
room, Empirica marks them "no more games", and the exit screen treats them as a lobby timeout:
they see the lobby-timeout code and the $2 payment. Someone who arrives after every game has
started is never assigned and sees the "session is full" screen, which asks them to return the
submission.

**Start the backup loop**, under `caffeinate -i` so the laptop does not sleep and stop backing
up without saying so. `caffeinate` does not keep a Mac awake with the lid closed, so keep the
lid open; if it was closed, run `bash operations/copy_tajriba.sh --once` after waking it to
catch up:

```bash
caffeinate -i bash operations/copy_tajriba.sh
```

Every five minutes it takes an export into its own `experiment/data/<timestamp>/` directory,
with the server log beside it, and it flags any callback error it finds in the log. A failed
copy is retried at the next interval; the loop gives up only after three failures in a row.

### T-25: open the survey

Publish the scheduling survey and watch the responses arrive.

### T-15: build the allowlist and close the survey

Paste the Prolific IDs of everyone who answered "Yes" to all three questions into the game
study's Custom Allowlist. Then stop the survey: every further response costs its reward and
tells someone they are expected at a session they will not be sent. Approve the survey
submissions so the respondents are paid.

### T-10: send the reminder

Message the people on the allowlist with the reminder in "Message templates", with the session
time filled in.

### T: publish

Publish the game study at the announced minute, and check that it has the allowlist before you
do: without one, a $12 study opens to everyone on Prolific. Then watch the admin panel for
arrivals and game progress, Sentry for client errors, and the memory graph.

Prolific shows an allowlisted study to some participants several minutes late. When someone
messages that they cannot find it, send the reply in "Message templates", which gives them the
game link and asks them to enter their Prolific ID and submit the study afterwards (appending
`?PROLIFIC_PID=<their id>` to the link fills the ID in for them). Anyone who plays but never submits the game study
is paid through their scheduling-survey submission (see "Reference: how people are paid").

### After the session

**1. Stop the batches** once the last game has ended and its players have had a few minutes
for the exit survey, take one more export with `bash operations/copy_tajriba.sh --once`, and
stop the backup loop.

**2. Run the export through the pipeline.** Claude does this with the `process-new-run` skill
when told the session is done; it also refreshes the published pages. By hand:

```bash
make smoke ZIP=experiment/data/<ts>/empirica-export-<ts>.zip   # check the export first
uv run python analysis/extract_run.py experiment/data/<ts>/empirica-export-<ts>.zip --dataset full
make combine process-no-filter test DATASET=full   # `process` instead runs the LLM message filter, which costs Vertex AI credit
```

Use the newest export in which every game has ended and the exit surveys are in. Each session
starts from a wiped server, so each session's final export is registered on its own.

**3. Work out what each study owes** with `make payments`. It reads every export in
`runs.txt`, identifies each player by the Prolific ID they entered on the identifier screen,
places them in the study where that ID has a submission (by completion code, then by time, so
players who joined through a link sent by message are paid in the right study), and asks
Prolific (read-only) for each study's submissions, their status and the bonuses already paid.
It prints a table per study and writes `data/payments/full/<date>_<internal name>_<id>/`:

```text
full sample batch 20  [6ac021def53ee57a669004a9]  games: 2N1CT5 5F1AS9 HGKW39 QQK054
    ready to pay: bonus 28 ($198.77), partial 7 ($39.22), lobby 2 ($4.00), overtime 7 ($12.48)
    2 partial or lobby submission(s) still awaiting review: ask them to return it; Prolific approves them from 2026-10-23
    folder: 2026-10-02_full-sample-batch-20_9004a9/
```

Each folder has two paste files, one line per person (`participant_id,amount`, no header):
`1_main.csv`, with the performance bonuses, partial pay, lobby pay, and anyone paid through
this study because they never submitted the game study; and `2_overtime.csv`, with the
overtime owed to finishers whose time on the study ran past 60 minutes, the top of the "45 to
60 minutes" the instructions promise. `status.csv` lists everyone with the reason anything owed
is not ready (a game still running, or no submission in the study). At the end it checks for
repeat participants and prints a warning if anyone was placed in two games; `repeats.csv` has
the details. The folder is rewritten on every run and contains Prolific IDs, which is why
`data/payments/` is gitignored.

**4. On each study's submissions page:**

- **Approve the finishers**, the submissions with the finished code `C2I8XDMC`. Approval pays
  the $12 base reward. Before approving, check that everyone approved appears in that study's
  `status.csv` as a finisher: a finished code without a completed game in the data is worth a
  look.
- **Make sure removed players and lobby timeouts are returned, not approved.** Their codes
  request a return, but Prolific approves a submission left awaiting review 21 days after it
  was submitted, which pays the full base reward on top of the partial or lobby payment.
  `make payments` prints how many are still waiting and the first date Prolific will approve
  them; message those participants and ask them to return the submission.
- **Paste `1_main.csv`, then `2_overtime.csv`,** into the study's bulk bonus form. The order
  matters because `make payments` counts what Prolific records as paid against the
  performance bonus first. Prolific shows the fee-inclusive total before you confirm.
- **Answer anyone who writes in** with the replies in "Message templates"; Prolific has
  already sent removed players and lobby timeouts the return request, and `status.csv` has
  each person's exit reason.

**5. Run `make payments` again.** Everyone just paid now shows as settled; anything still
listed was missed.

## If something goes off script

**Someone asks to be added after the allowlist was built.** Add their Prolific ID to the game
study's Custom Allowlist.

**`make payments` lists someone as owed but not ready.** `status.csv` gives the reason. "No
submission from this participant in this study" usually means they reached the game through
another session's link; check which study their submission is in. "Game still running"
means the export was taken before the game ended; take a new export once it has.

**A participant was paid by mistake.** Prolific cannot reverse a bonus. `make payments`
subtracts what Prolific has already paid on a submission, so re-running it never tells you to
pay the same person twice in the same study, but check `status.csv` before pasting a file you
edited by hand, and remember that a payment made on a different study is not visible to it.

**The Empirica server died mid-session.** Participants see "Just a moment" or a 502 while
their browsers retry.

1. *Look.* `ssh root@$EMPIRICA_SERVER "systemctl is-active empirica; journalctl -u empirica -n 200 --no-pager"`
   and the DigitalOcean memory graph. Avoid `systemctl status` and `ps` with arguments: they
   print the tajriba service token from the process command line. The journal's timestamps
   are UTC, while the export folders are named in local time, and `copy_tajriba.sh` saves
   only the last 20 minutes of log with each export, so for an earlier incident pull
   `journalctl -u empirica --since ... --until ...` by hand. The service restarts itself, but
   after a crash it has to replay the whole database before it answers, which took nine
   minutes on 23 September. **Do not restart it again while it loads**: a manual restart
   throws away the loading done so far. Watch `journalctl -u empirica -f` for `server: started`.
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

| | Scheduling survey | Game study |
|--|--|--|
| reward | $0.30 per response | $12.00 |
| places | a ceiling of about 20 responses per game; stop the survey once the allowlist is built | the number of people on the allowlist |
| time | 1 min | 50 min estimated |
| device | desktop | desktop |
| URL | `https://prolific.com/surveys/<survey_id>` | the server, with `?PROLIFIC_PID={{%PROLIFIC_PID%}}&STUDY_ID={{%STUDY_ID%}}&SESSION_ID={{%SESSION_ID%}}` |
| filters | current country of residence (US), fluent languages (English), Exclude participants from other studies (every earlier game study) | Custom Allowlist (the eligible respondents' Prolific IDs) |
| completion codes | one, manually reviewed | `C2I8XDMC` finished (manual review) · `CMZUY3MK` lobby timeout (request return) · `CFTYDMIY` removed early (request return) |

The completion paths are `https://app.prolific.com/submissions/complete?cc=<code>`; the exit
screens link participants straight to them. The three codes are defined in
`experiment/shared/constants.js`, and `make payments` reads them from there, so if this page
and that file ever disagree, the file is right and this page is stale. The finished code
must not approve automatically, because approval should follow a check against the game
data, and the partial and lobby-timeout codes must request a return. Prolific requires a
privacy notice on any survey-backed study.

## Reference: eligibility

The design is between subjects, so nobody may play twice. The game study is visible only to
the session's Custom Allowlist, and the scheduling survey excludes everyone who took part in an
earlier game study. That exclusion may not catch everyone, for example people who returned an
earlier submission, so `make payments` checks every export for a Prolific ID placed in more
than one started game and prints a warning if it finds one. It also lists, for information,
anyone who came back after an earlier visit that never reached a game, such as a lobby
timeout or a quiz failure.

## Reference: how people are paid

**Finishers** are approved, which pays the $12 base reward, and then receive their earned
bonus. A finisher who returned the submission instead of submitting the code cannot be
approved, so `make payments` adds the $12 base to their bonus.

**Removed players** -- disbanded group, failed accuracy check, too few groups, a batch the
researcher stopped, or idling out -- are paid by **returning the submission and receiving
their partial pay as a bonus**, never by approval. The server's `computePartialPay`
(`experiment/server/src/compensation.js`) already bundles prorated base pay with the earned
bonus into one number, so approving would pay the full base reward on top of it. Players
removed for inactivity get the prorated base pay only, without the bonus. When a removal
was not the player's doing (their screen stopped updating, or they answered the group guess
but never saw that a tangram click was also needed), add a line to
`data/full/payment_adjustments.csv` with their Empirica player id, `restore_bonus` and the
reason; `make payments` then pays the earned bonus as well. This is what
Prolific recommends for participants who cannot be matched in live studies: partial payment
by bonus, a return request, and a message explaining it.

**Lobby timeouts** -- people who arrived on time but for whom no game could be formed,
including overflow players Empirica turned away with "no more games" -- are paid the
`LOBBY_TIMEOUT_PAY` ($2) their exit screen promises, the same way: a bonus, a return request
and a note. Their game never started, so `make payments` finds them by the lobby-timeout code
on their submission, or, when they returned without entering it, by their export record, which
shows they waited in the lobby (quiz failures and people who left during the instructions are
not paid).

**Players who never submitted the game study** (usually because they played through a link
sent by message) are paid the $12 base plus their bonus, or their partial pay, as a bonus on
their scheduling-survey submission; these lines are in that survey's `1_main.csv`.

`make payments` applies all of this: a partial or lobby amount is listed in full for a
submission that is returned or awaiting review; for one that was approved anyway, which
already received the $12 base, only the part above $12 is listed (a player removed late in
the game with bonuses earned can be owed more than the base); and whatever Prolific has
already paid on a submission is subtracted. Overtime is paid at the study's own advertised
rate ($12 for 50 minutes, $0.24 a minute) for the whole minutes beyond 60, using the longer of
Prolific's recorded time and the game's own record; `--overtime-after` changes the threshold.
Prolific's fee on bonuses is about 33%, shown before you confirm a bulk bonus.

## Reference: the data

`copy_tajriba.sh` leaves each export as
`experiment/data/<timestamp>/empirica-export-<timestamp>.zip`. `extract_run.py` unzips one,
strips the Prolific ids from the raw CSVs into the gitignored `data/runs/<timestamp>/`, and
registers the timestamp in `data/<dataset>/runs.txt`; `combine_runs.py` stacks the registered
runs into `data/<dataset>/raw_anonymized/`; `process_data.py` produces the analysis tables
and derived metrics. The full sample's outputs are gitignored and stay on this machine until
collection ends. Only `make payments` reads the Prolific ids, straight from the export zips.
The export folders themselves are the record of what the server held: read them, never edit,
move or delete anything in them. They are also backed up on MIT's Engaging cluster.

**Exports are cumulative.** `empirica export` dumps the whole server, not just the last
session, so if the server was not wiped between sessions the newest export contains every
earlier one. `combine_runs.py` keeps the newest version of a record that appears in several
exports and reports the overlap, but keep one export per server state in `runs.txt` anyway:
the newest export of a server replaces its earlier exports.

## Message templates

These are the messages actually sent during the full-sample sessions (from the Prolific
message history, October 2026), with the session time, amounts and links as placeholders.
Removed players and lobby timeouts are not messaged individually: their completion codes make
Prolific send the return request itself, with the reason "Disbanded" (the partial code, used
for every kind of removal, including inactivity) or "Lobby timeout". Participants who write in
get a short personal reply; the recurring ones are below.

### Reminder, sent to the allowlist about ten minutes before the session

> Hello! Thank you for signing up for our study. The study will show up on your dashboard very shortly, at {time}. It might take a few minutes to show up for some participants. This experiment depends on synchronous and real-time participation, so please join as soon as you see it. If it doesn't appear after refreshing, please let us know.

### The study has not appeared on someone's dashboard

> hello! sorry about that, it seems like prolific has a lag for some participants even though we send it to everyone at the same time. i'll try sending it again, could you refresh again in a minute or so? it should be called "Group communication game." if it still doesn't show up, the study is at {link} and you can start it; just make sure to put in your prolific ID so we can pay you, and submit it on prolific after the study ends.

### The server is slow, sent to everyone in the running games

> Hello! The game server is at high load right now, so the game may pause for several seconds between rounds. Sorry about this -- you will be compensated for any extra time. If you see "The game is catching up", please wait for the next screen instead of reloading the page, because reloading makes the delay longer. Your progress is saved.

This promises compensation for the extra time, which `make payments` pays as overtime.

### Lobby timeouts, when another session follows the same day

> Hi, really sorry for the lobby timeout, it looks like we weren't able to find you a game since the game requires 9 players to be online at once, and sometimes players don't show up. If you're still interested in the study, we will be running a new session at {time}, it should show up on your dashboard then if you would like to participate.

### Replies to common questions

Why they are asked to return the submission:

> returning is just so that we can pay you through another mechanism (the bonus payments) and that you won't be penalized for future studies!

When the bonus arrives:

> yes I will pay the bonus shortly! takes us a few days to calculate the bonuses

Someone whose game ended early:

> Hey sorry about that, it looks like some of your group members left, or there were technical issues, this isn't your fault, and I'll make sure you get compensated for your time. The returning the study is so that we can pay you through the bonus avenue

Someone who could not be placed in a game:

> sorry, the game requires 9 people on at the same time, but sometimes people don't show up, which is out of our control, apologies! returning ensures that you're not penalized for this and that we can pay you the ${amount} through a bonus

## What the full-sample sessions showed

"Eligible" is the size of the game study's allowlist, "opened" the number of submissions on the
game study (everyone who started it, including returns), and "games" the games started. The
failed first attempt at batch 10 (no game formed) and its redo, which reused a pooled
allowlist, are left out.

| Batch | Eligible | Opened | Games | Eligible per game | Lobby timeouts |
|-------|----------|--------|-------|-------------------|----------------|
| 4     | 52       | 43     | 3     | 17                | 9              |
| 7     | 62       | 54     | 4     | 16                | 7              |
| 11    | 90       | 78     | 6     | 15                | 14             |
| 13    | 92       | 64     | 6     | 15                | 7              |
| 14    | 64       | 51     | 5     | 13                | 4              |
| 16    | 66       | 46     | 3     | 22                | 12             |
| 17    | 59       | 49     | 4     | 15                | 7              |
| 18    | 79       | 60     | 6     | 13                | 0              |
| 19    | 54       | 40     | 3     | 18                | 6              |
| 20    | 66       | 52     | 4     | 17                | 2              |

Across these sessions about 78% of eligible people opened the study (60% to 94%), and about
three in four scheduling-survey responses were eligible.

What fills a game is the number of people who are ready, which the exports record (an entered
identifier, then the intro and quiz completed). For the six-game sessions:

| Session | Allowlist | Arrived | Ready | Ready share | Games filled |
|---------|-----------|---------|-------|-------------|--------------|
| 25 Sep, noon (batch 11) | 90 | 72 | 63 | 70% | 6 |
| 25 Sep, 4:35 pm (batch 13) | 92 | 64 | 59 | 64% | 6 |
| 26 Sep, 10 pm (batch 18) | 79 | 57 | 54 | 68% | 6 |
| 4 Oct, 5:34 pm (batch 21) | 82 | 52 | 46 | 56% | 5 of 6 |

## Operational lessons

- **Say that the study appears exactly at the announced time.** Participants go looking for
  it on their dashboard several minutes early and message you when they cannot find it.
- **Do not require a reply to confirm.** Unconfirmed participants show up regardless, so a
  confirmation step adds monitoring work without improving attendance.
- **Tell participants to keep their sound on** and to watch for the sound that plays when
  the game starts.
- **More sessions, not bigger ones.** Five games per session keeps the server responsive; a
  sixth roughly doubles the pauses between stages and pushes most games into overtime.
- **Keep the laptop awake and open** while the backup loop runs; a closed lid stops the
  backups without warning.
