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

The R packages are managed by `renv` and the Python packages are managed by conda.

The R version is `4.5.2`.

```bash
conda env create -f environment.yml
conda activate lexical-variation
# In R: renv::restore()
```