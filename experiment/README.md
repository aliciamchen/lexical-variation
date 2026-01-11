# Interactive experiment

## Custom Chat Component

This project uses a custom Chat component (`client/src/components/Chat.jsx`) instead of the default Empirica Chat. This eliminates the need for any `node_modules` patches.

The custom Chat component provides:
- **Role labels**: Shows "(Speaker)" or "(Listener)" after player names
- **Identity masking**: Uses `display_name` and `display_avatar` in Phase 2 mixed conditions
- **Timestamps**: Shows 5-second increments (5s, 10s, 15s...) instead of "now" for recent messages
- **Square avatars**: Matches the UI style of other avatars in the game
- **DiceBear fallback**: Uses identicon avatars when player avatar is not set

No `node_modules` patches are required.

## Running the experiment

### Local Development

```bash
cd experiment
rm .empirica/local/tajriba.json  # Fresh database
empirica
```

- Admin: http://localhost:3000/admin
- Players: http://localhost:3000/

### Production Deployment

```bash
empirica bundle
scp prod-comp.tar.zst root@45.55.59.202:~
empirica serve prod-comp.tar.zst
```

Production URL: http://45.55.59.202:3000/

### Data Backup

Periodically copy the tajriba file: `sh copy_tajriba.sh`
