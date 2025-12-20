# Interactive experiment

NOTE: For the avatars to show up in the chat, comment out 

```js
if (!avatar.startsWith("http")) {
avatarImage = /* @__PURE__ */ React6.createElement("div", { className: "inline-block h-9 w-9 rounded-full" }, avatar);
}
```

in `chunk-J6LPACOK.js` in `node_modules/@empirica/core/dist`. This is because `player.get("avatar")` isn't the full image tag, just the path (and this is so that we can also use `player.get("avatar")` in `Avatar.jsx`)

## Running the experiment

`empirica bundle`
`scp prod-comp.tar.zst root@45.55.59.202:~`
`empirica serve prod-comp.tar.zst`

experiment is at 45.55.59.202:3000/admin
`http://45.55.59.202:3000/`


it's good to periodically copy the tajriba file: `sh copy_tajriba.sh`