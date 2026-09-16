// Group reshuffling for Phase 2 of the mixed conditions.
//
// On every trial the active players are reassigned to groups by exhaustive
// search over all assignments that place at most one player of each rotation
// index in each group (at most 6^3 = 216 candidates). Candidates are ranked
// lexicographically by
//   1. the number of three-person groups (no pair while a trio can be formed),
//   2. the number of trios whose speaker has exactly one in-group listener,
//      where the speaker is whoever selectSpeaker() will pick for the block,
//      including its fallback when a group lacks the block's speaker index,
//   3. the number of two-person groups whose lone listener matches a coin
//      flipped once per trial, so that a pair's listener is in-group half the
//      time rather than always (which speakers could learn from their feedback),
// and one of the best candidates is drawn uniformly at random.
//
// With a full roster (three original groups, each with all three indices) the
// best candidates are exactly the assignments of the constrained construction
// the preregistration describes: the three speakers go to three groups, one
// listener index follows the speakers (always in-group) and the other follows
// a derangement of the original groups (always out-group). Enumeration
// reproduces that distribution and degrades gracefully after dropout instead
// of switching to a heuristic. Tests: reshuffling.test.js.
import { GROUP_NAMES, GROUP_SIZE, MIN_GROUP_SIZE } from "./constants";
import { selectSpeaker } from "./roles";

// Every injective map from `items` into `nSlots` slots, as arrays of slot
// numbers aligned with `items`. Empty `items` gives the single empty map.
function injections(items, nSlots) {
  const result = [];
  const walk = (i, used, acc) => {
    if (i === items.length) {
      result.push(acc.slice());
      return;
    }
    for (let slot = 0; slot < nSlots; slot++) {
      if (used.has(slot)) continue;
      used.add(slot);
      acc.push(slot);
      walk(i + 1, used, acc);
      acc.pop();
      used.delete(slot);
    }
  };
  walk(0, new Set(), []);
  return result;
}

// All assignments of `players` to `nSlots` group slots with at most one player
// per rotation index in each slot. Each assignment is an array of `nSlots`
// arrays of players (some possibly empty).
export function enumerateAssignments(players, nSlots) {
  const byIndex = [0, 1, 2].map((idx) =>
    players.filter((p) => p.get("player_index") === idx),
  );
  const maps = byIndex.map((ps) => injections(ps, nSlots));
  const assignments = [];
  for (const m0 of maps[0]) {
    for (const m1 of maps[1]) {
      for (const m2 of maps[2]) {
        const groups = Array.from({ length: nSlots }, () => []);
        byIndex[0].forEach((p, i) => groups[m0[i]].push(p));
        byIndex[1].forEach((p, i) => groups[m1[i]].push(p));
        byIndex[2].forEach((p, i) => groups[m2[i]].push(p));
        assignments.push(groups);
      }
    }
  }
  return assignments;
}

// Number of listeners in `group` who share the speaker's original group.
export function inGroupListenerCount(group, blockNum) {
  const { speaker } = selectSpeaker(group, blockNum);
  if (!speaker) return 0;
  return group.filter(
    (p) => p !== speaker && p.get("original_group") === speaker.get("original_group"),
  ).length;
}

// Score one candidate assignment, or null when a non-empty group is below
// MIN_GROUP_SIZE. `key` is the lexicographic ranking described above.
export function scoreAssignment(groups, blockNum, pairTargetInGroup) {
  const nonEmpty = groups.filter((g) => g.length > 0);
  if (nonEmpty.some((g) => g.length < MIN_GROUP_SIZE)) return null;
  let nTrios = 0;
  let nTriosOk = 0;
  let nPairs = 0;
  let nPairsOk = 0;
  for (const group of nonEmpty) {
    const inGroup = inGroupListenerCount(group, blockNum);
    if (group.length >= GROUP_SIZE) {
      nTrios += 1;
      if (inGroup === 1) nTriosOk += 1;
    } else {
      nPairs += 1;
      if ((inGroup === 1) === pairTargetInGroup) nPairsOk += 1;
    }
  }
  return {
    key: [nTrios, nTriosOk, nPairsOk],
    nGroups: nonEmpty.length,
    nTrios,
    nTriosOk,
    nPairs,
    nPairsOk,
  };
}

function compareKeys(a, b) {
  for (let i = 0; i < a.length; i++) {
    if (a[i] !== b[i]) return a[i] - b[i];
  }
  return 0;
}

// Choose an assignment of `players` into `nSlots` groups for `blockNum`:
// uniformly at random among the best-scoring candidates. `rng` is a function
// returning a uniform number in [0, 1), injectable for tests. Returns null when
// no candidate has every non-empty group at MIN_GROUP_SIZE or above.
export function chooseAssignment(players, nSlots, blockNum, rng = Math.random) {
  const pairTargetInGroup = rng() < 0.5;
  let best = null;
  let bestGroups = [];
  let nCandidates = 0;
  for (const groups of enumerateAssignments(players, nSlots)) {
    const score = scoreAssignment(groups, blockNum, pairTargetInGroup);
    if (!score) continue;
    nCandidates += 1;
    const cmp = best ? compareKeys(score.key, best.key) : 1;
    if (cmp > 0) {
      best = score;
      bestGroups = [groups];
    } else if (cmp === 0) {
      bestGroups.push(groups);
    }
  }
  if (!best) return null;
  const groups = bestGroups[Math.floor(rng() * bestGroups.length)];
  return { groups, pairTargetInGroup, nCandidates, nBest: bestGroups.length, ...best };
}

// Reassign `players` (the active players) to the game's active groups for
// `blockNum`, setting each player's current_group. Returns a summary of what
// the assignment achieved, which onRoundStart records on the round:
//   mode        "constrained" when every group is a trio with exactly one
//               in-group listener (the full design), "reduced" otherwise
//   nGroups, nTrios, nTriosOk, nPairs
//               groups formed, trios among them, trios meeting the rule, pairs
//   pairTargetInGroup
//               the coin the pairs were asked to match this trial
// Returns null when fewer than MIN_GROUP_SIZE players remain.
export function reshuffleGroups(game, players, blockNum) {
  const block = blockNum ?? 0;
  const activeGroups = game.get("active_groups") || GROUP_NAMES;
  if (players.length < MIN_GROUP_SIZE) {
    console.log("Not enough players for any viable group");
    return null;
  }

  let names = activeGroups;
  let chosen = chooseAssignment(players, names.length, block);
  if (!chosen) {
    // Should not happen: the viability check removes players whose original
    // group is no longer active before the next round starts. Widen the label
    // set rather than leave anyone without a group.
    console.error(
      `Reshuffle: no valid assignment of ${players.length} players into ${names.length} groups; using all group names`,
    );
    names = GROUP_NAMES;
    chosen = chooseAssignment(players, names.length, block);
    if (!chosen) return null;
  }

  chosen.groups.forEach((group, slot) => {
    group.forEach((p) => p.set("current_group", names[slot]));
  });

  const mode =
    chosen.nPairs === 0 && chosen.nTriosOk === chosen.nTrios
      ? "constrained"
      : "reduced";
  console.log(
    `Reshuffle (block ${block}, speaker_idx ${block % GROUP_SIZE}): ${mode}, ` +
      `${chosen.nTriosOk}/${chosen.nTrios} trios with one in-group listener, ` +
      `${chosen.nPairs} pairs, ${chosen.nBest} of ${chosen.nCandidates} candidates tied for best`,
  );
  chosen.groups.forEach((group, slot) => {
    if (group.length === 0) return;
    console.log(
      `  Group ${names[slot]}: ${group
        .map((p) => `${p.get("name") || p.id}(og=${p.get("original_group")}, idx=${p.get("player_index")})`)
        .join(", ")}`,
    );
  });

  return {
    mode,
    nGroups: chosen.nGroups,
    nTrios: chosen.nTrios,
    nTriosOk: chosen.nTriosOk,
    nPairs: chosen.nPairs,
    pairTargetInGroup: chosen.pairTargetInGroup,
  };
}
