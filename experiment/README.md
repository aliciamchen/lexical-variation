# The experiment

The game is an [Empirica](https://empirica.ly/) app: the React client is in `client/`, the server callbacks in `server/src/`, the configuration both sides share (player counts, blocks, timing, scoring, exit reasons, completion codes) in `shared/constants.js`, and the treatments in `.empirica/treatments.yaml`, two per condition, one per tangram set. The Empirica release is pinned in `.empirica/release`.

## Local development

```bash
cd experiment
rm .empirica/local/tajriba.json   # a fresh database
empirica
```

The admin panel is at http://localhost:3000/admin and players join at http://localhost:3000/. Click "New Batch", choose a treatment and open nine player tabs. Each player goes through consent, an identifier screen, the instructions and a comprehension quiz before entering the lobby. On Prolific the study link carries the participant's id, which fills and locks the identifier field; locally the field is typed. The four conditions are `refer_separated`, `refer_mixed`, `social_mixed` and `social_first`.

The admin password and the token the server uses for its database are in `.empirica/empirica.toml`, created from `empirica.toml.example` with fresh random values. It is gitignored because `empirica bundle` ships it with the server.

## Tests

```bash
npm install
npx playwright install chromium
npm run test:unit         # server unit tests (vitest), no browser
npm test                  # the whole Playwright suite in test mode (3+2 blocks at production timers)
npm run test:group1       # one group: test:group1 to test:group4, test:group4:fast, test:holistic
npm run test:smoke        # the specs tagged @smoke
TEST_MODE=false npm test  # full-length games (6+6 blocks)
npm run test:report       # the HTML report
```

The server unit tests cover the pure modules beside the callbacks (scoring, reshuffling, roles, idle detection, accuracy screening, group viability, compensation, avatars) and the rules in `shared/` (chat input, the engagement log, Prolific codes). The Playwright suite has 47 spec files in 13 categories, grouped into five projects that each start from a reset server:

| Group | Categories |
|---|---|
| group-1 | happy-path, communication, lobby, edge-cases |
| group-2 | ui-verification, timing |
| group-3 | data-integrity, condition-specific, score-display |
| group-4 | idle-detection, group-viability, compensation |
| group-holistic | full end-to-end games at production timing |

Run the groups through the npm scripts, which pair each group with its server-reset setup and pass `--no-deps`; a bare `npx playwright test <file>` replays every earlier group first. A single spec runs as `npx playwright test reset-server.setup tests/<category>/<spec>.spec.ts --project=setup-N --project=group-N --no-deps`. Only one run can use the Empirica server at a time, because every run binds ports 3000 and 8844 and resets the server's state: the harness takes a lock file and refuses to start while another run holds it, and `npm run test:free-ports` frees the ports. The test helpers are in `tests/helpers/`; `constants.ts` there re-exports `shared/constants.js`, so tests compare exit reasons and completion codes against the shared values rather than string literals.

## Deployment

No production server exists: the server that ran the full sample was destroyed on 2026-10-10 after its exports were backed up. A new one is deployed following the [Empirica Ubuntu guide](https://docs.empirica.ly/guides/deploying-my-experiment/ubuntu-tutorial), with its hostname in `EMPIRICA_SERVER` in the repository-root `.env`:

```bash
cd experiment
empirica bundle
scp lexical-variation.tar.zst root@$EMPIRICA_SERVER:~/empirica/empirica.tar.zst
```

Two things are easy to get wrong. The Sentry DSN is compiled into the client bundle, so it has to be in `.env` on the machine that builds, and a production build fails without it unless `ALLOW_NO_SENTRY=1` is set; the server reads none of the `.env` values. And after `empirica upgrade`, the server keeps running the old release until `~/empirica/.empirica/release` on the server is set to the new version and the service is restarted, because that file, not the bundle, chooses the release. The server restarts whenever the bundle file changes, which ends every game in progress, so a deploy happens before participants are invited.

Avatars are served from `client/public/avatars/` rather than fetched at play time. `node scripts/fetch-avatars.mjs` regenerates the set if the block count, the roster or the avatar style changes, and `server/src/avatars.test.js` fails if a seed the server can generate has no file.

During a session, `operations/copy_tajriba.sh` runs `empirica export` on the server every five minutes and copies the zip into `experiment/data/<timestamp>/`; those exports are the pipeline's input. The sessions were run by hand on Prolific following `operations/procedures.md`.

## Error monitoring

Client errors are reported to Sentry through `@sentry/react`, configured in `client/src/index.jsx`, with session replays for sessions that hit an error and all text and inputs masked. Every URL is cut at the `?` before it leaves the browser, so the Prolific id in the study link never reaches Sentry, and the Sentry user is the Empirica player id only. A websocket drop shows up as an unhandled error from Empirica's `TajribaParticipant.emit`; it is noise rather than a game bug, and the connection log on each player record is the record of disconnects.
