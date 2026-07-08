// Group reshuffling for Phase 2 mixed conditions.
// Extracted from callbacks.js so the logic can be unit tested directly
// (see reshuffling.test.js) — tests import these functions, not a copy.
import _ from "lodash";
import { GROUP_SIZE, MIN_GROUP_SIZE, GROUP_NAMES } from "./constants";

// Precomputed derangements for small N (permutations with no fixed points)
const DERANGEMENTS = {
  2: [[1, 0]],
  3: [
    [1, 2, 0],
    [2, 0, 1],
  ],
};

// Constrained reshuffling: guarantees exactly 1 in-group listener per group per trial.
// Works when the active players form a complete N×N matrix (N original groups × N player indices).
// Returns true if successful, false if the matrix is irregular (fall back to best-effort).
export function doConstrainedReshuffle(players, usedGroups, blockNum) {
  const speakerIdx = blockNum % GROUP_SIZE;
  const listenerIndices = [0, 1, 2].filter((i) => i !== speakerIdx);

  // Build lookup: playersByIndex[playerIndex][originalGroup] = player
  const playersByIndex = {};
  for (let idx = 0; idx < GROUP_SIZE; idx++) {
    playersByIndex[idx] = {};
  }
  for (const p of players) {
    playersByIndex[p.get("player_index")][p.get("original_group")] = p;
  }

  // Check: each index must have exactly one player per original group,
  // and the number of original groups must equal usedGroups
  const originalGroups = [
    ...new Set(players.map((p) => p.get("original_group"))),
  ].sort();
  const N = originalGroups.length;
  if (N !== usedGroups.length) return false;
  if (!DERANGEMENTS[N]) return false; // Only handle N=2 and N=3
  for (let idx = 0; idx < GROUP_SIZE; idx++) {
    if (Object.keys(playersByIndex[idx]).length !== N) return false;
  }

  // Random permutation for speakers: maps index i -> sigma[i]
  const sigma = _.shuffle(_.range(N));

  // One listener index uses the same permutation (always in-group with speaker)
  // The other listener index uses sigma composed with a derangement (always out-of-group)
  const matchIdx = _.sample(listenerIndices);
  const derangeIdx = listenerIndices.find((i) => i !== matchIdx);

  // Compose: sigma_derange[i] = sigma[D[i]]
  const D = _.sample(DERANGEMENTS[N]);
  const sigma_derange = D.map((d) => sigma[d]);

  // Assign all players to their reshuffled groups
  for (let i = 0; i < N; i++) {
    const og = originalGroups[i];
    playersByIndex[speakerIdx][og].set("current_group", usedGroups[sigma[i]]);
    playersByIndex[matchIdx][og].set("current_group", usedGroups[sigma[i]]);
    playersByIndex[derangeIdx][og].set(
      "current_group",
      usedGroups[sigma_derange[i]],
    );
  }
  return true;
}

// Helper function to reshuffle groups for mixed conditions with BALANCED assignment
// Goal: Each group should have one player from each original_player_index (0, 1, 2)
// This ensures speaker rotation (blockNum % 3) works consistently across conditions
// Additionally: Ensures groups are MIXED (players from different original groups together)
export function reshuffleGroups(game, players, blockNum) {
  const activeGroups = game.get("active_groups") || GROUP_NAMES;
  const numPlayers = players.length;

  // Calculate how many groups we can support (each needs MIN_GROUP_SIZE players)
  const maxGroups = Math.floor(numPlayers / MIN_GROUP_SIZE);
  const numGroups = Math.min(maxGroups, activeGroups.length);

  if (numGroups === 0) {
    console.log("Not enough players for any viable group");
    return;
  }

  const usedGroups = activeGroups.slice(0, numGroups);

  // Try constrained reshuffling first (guarantees exactly 1 in-group listener)
  if (blockNum !== undefined && doConstrainedReshuffle(players, usedGroups, blockNum)) {
    // Verify: each group of 3 has exactly 1 in-group listener
    const speakerTargetIndex = blockNum % GROUP_SIZE;
    usedGroups.forEach((groupName) => {
      const gp = players.filter(
        (p) => p.get("current_group") === groupName,
      );
      if (gp.length < GROUP_SIZE) return; // Skip groups of 2
      const sp = gp.find(
        (p) => p.get("player_index") === speakerTargetIndex,
      );
      if (!sp) return;
      const listeners = gp.filter((p) => p !== sp);
      const inGroup = listeners.filter(
        (p) => p.get("original_group") === sp.get("original_group"),
      );
      console.assert(
        inGroup.length === 1,
        `Group ${groupName}: expected 1 in-group listener, got ${inGroup.length}`,
      );
    });

    // Log final composition
    console.log(
      `Constrained reshuffle succeeded (block ${blockNum}, speaker_idx ${speakerTargetIndex}):`,
    );
    usedGroups.forEach((groupName) => {
      const gp = players.filter(
        (p) => p.get("current_group") === groupName,
      );
      console.log(
        `  Group ${groupName}: ${gp.map((p) => `${p.get("name") || p.id}(og=${p.get("original_group")}, idx=${p.get("player_index")})`).join(", ")}`,
      );
    });
    return;
  }

  // Fall through to best-effort reshuffling (irregular dropout patterns)
  if (blockNum !== undefined) {
    console.log(
      `Constrained reshuffle failed for block ${blockNum}, falling back to best-effort`,
    );
  }

  // Calculate target group sizes for even distribution
  const baseSize = Math.floor(numPlayers / numGroups);
  const extraPlayers = numPlayers % numGroups;
  const targetSizes = [];
  for (let i = 0; i < numGroups; i++) {
    targetSizes.push(baseSize + (i < extraPlayers ? 1 : 0));
  }
  // Check how many unique original groups we have
  const uniqueOriginalGroups = new Set(
    players.map((p) => p.get("original_group")),
  );
  const canMix = uniqueOriginalGroups.size >= 2;

  // Helper function to perform one reshuffling attempt
  function doReshuffle() {
    // Group players by their original_player_index
    const playersByIndex = {
      0: players.filter((p) => p.get("player_index") === 0),
      1: players.filter((p) => p.get("player_index") === 1),
      2: players.filter((p) => p.get("player_index") === 2),
    };

    // Shuffle within each index group for randomization
    Object.keys(playersByIndex).forEach((idx) => {
      playersByIndex[idx] = _.shuffle(playersByIndex[idx]);
    });

    // Track which players have been assigned in THIS reshuffling
    const assignedInThisReshuffling = new Set();
    const indexPointers = { 0: 0, 1: 0, 2: 0 };

    // First pass: Fill each group with one player from each index
    usedGroups.forEach((groupName, groupIdx) => {
      const targetSize = targetSizes[groupIdx];
      let assigned = 0;

      // Try to assign one player from each index
      for (let idx = 0; idx < GROUP_SIZE && assigned < targetSize; idx++) {
        const pointer = indexPointers[idx];
        if (pointer < playersByIndex[idx].length) {
          const player = playersByIndex[idx][pointer];
          player.set("current_group", groupName);
          assignedInThisReshuffling.add(player.id);
          indexPointers[idx]++;
          assigned++;
        }
      }
    });

    // Second pass: Distribute any remaining unassigned players
    const unassignedPlayers = players.filter(
      (p) => !assignedInThisReshuffling.has(p.id),
    );

    if (unassignedPlayers.length > 0) {
      let unassignedIdx = 0;
      usedGroups.forEach((groupName, groupIdx) => {
        const targetSize = targetSizes[groupIdx];
        let currentSize = players.filter(
          (p) =>
            assignedInThisReshuffling.has(p.id) &&
            p.get("current_group") === groupName,
        ).length;

        while (
          currentSize < targetSize &&
          unassignedIdx < unassignedPlayers.length
        ) {
          const player = unassignedPlayers[unassignedIdx];
          player.set("current_group", groupName);
          assignedInThisReshuffling.add(player.id);
          currentSize++;
          unassignedIdx++;
        }
      });
    }
  }

  // Helper function to check if groups are properly mixed
  // Mixed = at least one group has players from 2+ different original groups
  function checkMixing() {
    for (const groupName of usedGroups) {
      const groupPlayers = players.filter(
        (p) => p.get("current_group") === groupName,
      );
      const originalGroups = new Set(
        groupPlayers.map((p) => p.get("original_group")),
      );
      if (originalGroups.size >= 2) {
        return true; // At least one group is mixed
      }
    }
    return false; // No group has players from different original groups
  }

  // Perform reshuffling with mixing guarantee (if possible)
  const MAX_RESHUFFLE_ATTEMPTS = 10;
  let attempts = 0;
  let isMixed = false;

  if (!canMix) {
    // Only one original group remaining, mixing is impossible
    console.log("Only one original group remaining - mixing not possible");
    doReshuffle();
  } else {
    // Try to get a mixed result
    while (attempts < MAX_RESHUFFLE_ATTEMPTS && !isMixed) {
      attempts++;
      doReshuffle();
      isMixed = checkMixing();
    }

    if (isMixed) {
      console.log(`Achieved mixed groups after ${attempts} attempt(s)`);
    } else {
      console.warn(
        `WARNING: Could not achieve mixing after ${MAX_RESHUFFLE_ATTEMPTS} attempts`,
      );
    }
  }

  // Verification: Log final group composition
  const groupComposition = {};
  usedGroups.forEach((groupName) => {
    const groupPlayers = players.filter(
      (p) => p.get("current_group") === groupName,
    );
    const indices = groupPlayers.map((p) => p.get("player_index"));
    const originalGroups = [
      ...new Set(groupPlayers.map((p) => p.get("original_group"))),
    ];
    groupComposition[groupName] = {
      size: groupPlayers.length,
      indices: indices.sort(),
      hasAllIndices: [0, 1, 2].every((idx) => indices.includes(idx)),
      originalGroups: originalGroups.sort(),
      isMixed: originalGroups.length >= 2,
    };
  });

  // Verify all groups meet MIN_GROUP_SIZE
  const undersizedGroups = Object.entries(groupComposition)
    .filter(([_, info]) => info.size < MIN_GROUP_SIZE)
    .map(([name, _]) => name);

  if (undersizedGroups.length > 0) {
    console.error(
      `ERROR: Groups ${undersizedGroups.join(", ")} are below MIN_GROUP_SIZE=${MIN_GROUP_SIZE}`,
    );
  }

  // Warn if any group is missing an index (will need fallback for speaker selection)
  const numComplete = Object.values(groupComposition).filter(
    (g) => g.hasAllIndices,
  ).length;
  const numMixed = Object.values(groupComposition).filter(
    (g) => g.isMixed,
  ).length;
  console.log(
    `Reshuffled ${numPlayers} players into ${numGroups} groups (${numComplete} complete, ${numMixed} mixed)`,
  );
}
