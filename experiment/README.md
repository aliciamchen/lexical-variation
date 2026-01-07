# Interactive experiment

## Required Patches

After running `npm install`, the following patches must be applied to `node_modules/@empirica/core/dist/chunk-J6LPACOK.js`:

### 1. Avatar Display Patch

Comment out the following code to allow HTTP URLs for avatars:

```js
// if (!avatar.startsWith("http")) {
//   avatarImage = /* @__PURE__ */ React6.createElement("div", { className: "inline-block h-9 w-9 rounded-full" }, avatar);
// }
```

This is needed because `player.get("avatar")` returns a URL path, not a full image tag.

### 2. Chat Timestamp Display Patch

Change the `relTime` function to show 5-second increments instead of "now" for all messages under 60 seconds:

```js
// Change this:
if (difference < 60) {
  return `now`;
}

// To this:
if (difference < 5) {
  return `now`;
} else if (difference < 60) {
  return `${Math.floor(difference / 5) * 5}s`;
}
```

### 3. Chat Timestamp Data Patch

Add `timestamp: Date.now()` to message data in `handleNewMessage`:

```js
scope.append(attribute, {
  text,
  timestamp: Date.now(),
  sender: { ... }
});
```

### 4. Chat Role Indicator Patch

Modify the Chat function to accept `customPlayerName` prop:

```js
function Chat({
  scope,
  attribute = "messages",
  loading: LoadingComp = Loading,
  customPlayerName  // Add this parameter
}) {
  const player = usePlayer();
  if (!scope || !player) {
    return /* @__PURE__ */ React6.createElement(LoadingComp, null);
  }
  const handleNewMessage = (text) => {
    const senderName = customPlayerName ? customPlayerName(player) : (player.get("name") || player.id);
    scope.append(attribute, {
      text,
      timestamp: Date.now(),
      sender: {
        id: player.id,
        name: senderName,  // Use senderName instead of player.get("name")
        avatar: player.get("avatar")
      }
    });
  };
  // ... rest of function
}
```

### 5. Square Chat Avatars (CSS)

Add to `client/src/index.css`:

```css
/* Override Empirica chat avatar styling - make them squares to match other avatars */
img.rounded-full {
  border-radius: 6px !important;
}
```

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
