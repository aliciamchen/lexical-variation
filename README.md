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

## Required Patches

After installing empirica, you need to make edits `experiment/client/node_modules/@empirica/core/dist/chunk-J6LPACOK.js` for some details of the experiment to work correctly. 

**Avatar display patch:** Comment out the avatar URL check (~line 522-524):
```js
// if (!avatar.startsWith("http")) {
//   avatarImage = /* @__PURE__ */ React6.createElement("div", { className: "inline-block h-9 w-9 rounded-full" }, avatar);
// }
```

**Chat timestamp display patch:** Modify the `relTime` function (~line 598-602) to show 5-second increments:
```js
// Change:
if (difference < 60) {
  return `now`;
}

// To:
if (difference < 5) {
  return `now`;
} else if (difference < 60) {
  return `${Math.floor(difference / 5) * 5}s`;
}
```

**Chat timestamp data patch:** Add timestamp to message data in `handleNewMessage` (~line 468-477):
```js
// Change:
scope.append(attribute, {
  text,
  sender: { ... }
});

// To:
scope.append(attribute, {
  text,
  timestamp: Date.now(),
  sender: { ... }
});
```

**Chat role indicator patch:** Modify the Chat function (~line 458-479) to accept `customPlayerName` prop:
```js
// Change:
function Chat({
  scope,
  attribute = "messages",
  loading: LoadingComp = Loading
}) {
  // ...
  const handleNewMessage = (text) => {
    scope.append(attribute, {
      text,
      timestamp: Date.now(),
      sender: {
        id: player.id,
        name: player.get("name") || player.id,
        avatar: player.get("avatar")
      }
    });
  };

// To:
function Chat({
  scope,
  attribute = "messages",
  loading: LoadingComp = Loading,
  customPlayerName
}) {
  // ...
  const handleNewMessage = (text) => {
    const senderName = customPlayerName ? customPlayerName(player) : (player.get("name") || player.id);
    scope.append(attribute, {
      text,
      timestamp: Date.now(),
      sender: {
        id: player.id,
        name: senderName,
        avatar: player.get("avatar")
      }
    });
  };
```

**Chat avatar square patch:** Add to `experiment/client/src/index.css`:
```css
/* Override Empirica chat avatar styling - make them squares to match other avatars */
img.rounded-full {
  border-radius: 6px !important;
}
```

## Dependencies

The R packages are managed by `renv` and the Python packages are managed by conda.

The R version is `4.5.2`.

```bash
conda env create -f environment.yml
conda activate lexical-variation
# In R: renv::restore()
```