# lexical-variation

## Running the experiment

The experiment is created using Empirica. You need to install it: 

```bash
curl -fsS https://install.empirica.dev | sh
```

To run the experiment locally: 

```bash
cd experiment
empirica
```

Remove the tajriba file between instances of testing: 

```bash
rm .empirica/local/tajriba.json
```

## Custom Chat Component

This project uses a custom Chat component (`experiment/client/src/components/Chat.jsx`) instead of the default Empirica Chat. This eliminates the need for any `node_modules` patches.

The custom Chat component provides:
- **Role labels**: Shows "(Speaker)" or "(Listener)" after player names
- **Identity masking**: Uses `display_name` and `display_avatar` in Phase 2 mixed conditions
- **Timestamps**: Shows 5-second increments (5s, 10s, 15s...) instead of "now" for recent messages
- **Square avatars**: Matches the UI style of other avatars in the game
- **DiceBear fallback**: Uses identicon avatars when player avatar is not set

No `node_modules` patches are required.

## Dependencies

The R packages are managed by `renv` and the Python packages are managed by [uv](https://docs.astral.sh/uv/).

The R version is `4.5.2`.

```bash
# Install Python dependencies
uv sync

# In R: renv::restore()
```

Note: `rpy2` requires R to be installed. Cairo-based packages may require: `brew install cairo pango`

## Testing the experiment

The experiment has a Playwright test suite with 250 tests covering all 3 conditions, idle detection, group viability, UI, timing, and more. See [`experiment/README.md`](experiment/README.md) for full documentation.

```bash
cd experiment
npm install
npx playwright install chromium

# Start the server (in a separate terminal)
rm .empirica/local/tajriba.json
empirica

# Run tests
npx playwright test

# Run a specific category
npx playwright test tests/happy-path/

# run tests headful
npx playwright test --headed

# View report
npx playwright show-report
```
