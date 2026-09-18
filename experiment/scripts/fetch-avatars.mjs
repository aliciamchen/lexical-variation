/**
 * Download every avatar the game can show, once, into client/public/avatars/.
 *
 * The avatars used to be <img src> pointing straight at api.dicebear.com. In
 * the mixed conditions the anonymous seed changes every trial, so nine players
 * each fetched a fresh avatar on all thirty-six Phase 2 trials: hundreds of
 * third-party requests per game, on the critical path, in the condition where
 * identity is the manipulation. A rate limit or an outage mid-session would
 * have broken the identity cues for everyone at once.
 *
 * Every seed is deterministic, so the whole set can be fetched ahead of time
 * and served from our own origin. Run this when the seeds change (more blocks,
 * more players, a different style) and commit the result:
 *
 *   node scripts/fetch-avatars.mjs
 *
 * avatarFileName() in shared/constants.js maps a seed to its file, and
 * avatars.test.js checks that every seed the server can generate has one.
 */
import { mkdir, writeFile, readdir } from "fs/promises";
import { fileURLToPath } from "url";
import { join } from "path";
import {
  avatar_seeds,
  anonymousAvatarSeeds,
  avatarFileName,
  DICEBEAR_IDENTICON,
  DICEBEAR_SHAPES,
} from "../shared/constants.js";

const outDir = fileURLToPath(new URL("../client/public/avatars/", import.meta.url));

async function fetchOne(url, file) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText} for ${url}`);
  const svg = await res.text();
  if (!svg.includes("<svg")) throw new Error(`not an SVG: ${url}`);
  await writeFile(join(outDir, file), svg);
}

const wanted = [
  ...avatar_seeds.map((seed) => [DICEBEAR_IDENTICON(seed), avatarFileName(seed)]),
  ...anonymousAvatarSeeds().map((seed) => [DICEBEAR_SHAPES(seed), avatarFileName(seed)]),
];

await mkdir(outDir, { recursive: true });
const have = new Set(await readdir(outDir).catch(() => []));
let fetched = 0;
for (const [url, file] of wanted) {
  if (have.has(file)) continue;
  await fetchOne(url, file);
  fetched += 1;
  // DiceBear is doing us a favour; do not hammer it.
  await new Promise((r) => setTimeout(r, 60));
}
console.log(
  `${wanted.length} avatars wanted, ${fetched} downloaded, ${wanted.length - fetched} already present -> ${outDir}`,
);
