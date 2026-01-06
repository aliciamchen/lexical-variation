// Test script to verify balanced reshuffling logic
// Run with: node test_reshuffling.js

const _ = require("lodash");

const GROUP_SIZE = 3;
const MIN_GROUP_SIZE = 2;
const GROUP_NAMES = ["A", "B", "C"];

// Mock player class
class MockPlayer {
  constructor(id, playerIndex, originalGroup) {
    this.id = id;
    this.data = {
      player_index: playerIndex,
      original_group: originalGroup,
      current_group: originalGroup,
      name: `Player${id}`,
    };
  }
  get(key) {
    return this.data[key];
  }
  set(key, value) {
    this.data[key] = value;
  }
}

// Balanced reshuffling function (copy from callbacks.js)
function reshuffleGroups(players, activeGroups) {
  const numPlayers = players.length;
  const maxGroups = Math.floor(numPlayers / MIN_GROUP_SIZE);
  const numGroups = Math.min(maxGroups, activeGroups.length);

  if (numGroups === 0) {
    console.log("Not enough players for any viable group");
    return { numGroups: 0, numCompleteGroups: 0, composition: {} };
  }

  // Group players by their original_player_index
  const playersByIndex = {
    0: players.filter((p) => p.get("player_index") === 0),
    1: players.filter((p) => p.get("player_index") === 1),
    2: players.filter((p) => p.get("player_index") === 2),
  };

  // Shuffle within each index group
  Object.keys(playersByIndex).forEach((idx) => {
    playersByIndex[idx] = _.shuffle(playersByIndex[idx]);
  });

  // Calculate target group sizes for even distribution
  const baseSize = Math.floor(numPlayers / numGroups);
  const extraPlayers = numPlayers % numGroups;
  const targetSizes = [];
  for (let i = 0; i < numGroups; i++) {
    targetSizes.push(baseSize + (i < extraPlayers ? 1 : 0));
  }
  console.log(`  Target group sizes: ${targetSizes.join(", ")}`);

  const usedGroups = activeGroups.slice(0, numGroups);

  // Strategy: For each group, assign one player from each index (0, 1, 2)
  const assignedInThisReshuffling = new Set();
  const indexPointers = { 0: 0, 1: 0, 2: 0 };

  // First pass: Fill each group with one player from each index
  usedGroups.forEach((groupName, groupIdx) => {
    const targetSize = targetSizes[groupIdx];
    let assigned = 0;

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

  // Second pass: Distribute remaining unassigned players
  const unassignedPlayers = players.filter(
    (p) => !assignedInThisReshuffling.has(p.id)
  );

  if (unassignedPlayers.length > 0) {
    let unassignedIdx = 0;
    usedGroups.forEach((groupName, groupIdx) => {
      const targetSize = targetSizes[groupIdx];
      let currentSize = players.filter(
        (p) =>
          assignedInThisReshuffling.has(p.id) &&
          p.get("current_group") === groupName
      ).length;

      while (currentSize < targetSize && unassignedIdx < unassignedPlayers.length) {
        const player = unassignedPlayers[unassignedIdx];
        player.set("current_group", groupName);
        assignedInThisReshuffling.add(player.id);
        currentSize++;
        unassignedIdx++;
      }
    });
  }

  // Build composition report
  const composition = {};
  usedGroups.forEach((groupName) => {
    const groupPlayers = players.filter(
      (p) => p.get("current_group") === groupName
    );
    const indices = groupPlayers.map((p) => p.get("player_index"));
    composition[groupName] = {
      size: groupPlayers.length,
      indices: indices.sort(),
      hasAllIndices: [0, 1, 2].every((idx) => indices.includes(idx)),
      players: groupPlayers.map((p) => `${p.get("name")}(idx${p.get("player_index")})`),
    };
  });

  const numCompleteGroups = Object.values(composition).filter(g => g.hasAllIndices).length;
  return { numGroups, numCompleteGroups, composition };
}

// Test speaker selection logic
function selectSpeaker(groupPlayers, blockNum) {
  const speakerTargetIndex = blockNum % GROUP_SIZE;
  let speaker = groupPlayers.find(
    (p) => p.get("player_index") === speakerTargetIndex
  );

  if (!speaker && groupPlayers.length > 0) {
    const fallbackIdx = blockNum % groupPlayers.length;
    const sortedPlayers = _.sortBy(groupPlayers, (p) => p.get("player_index"));
    speaker = sortedPlayers[fallbackIdx];
    return { speaker, usedFallback: true, targetIndex: speakerTargetIndex };
  }

  return { speaker, usedFallback: false, targetIndex: speakerTargetIndex };
}

// Test scenarios
function runTests() {
  console.log("=".repeat(60));
  console.log("BALANCED RESHUFFLING TEST SUITE");
  console.log("=".repeat(60));

  // Test 1: Full 9 players
  console.log("\n--- TEST 1: 9 players (no dropouts) ---");
  const players9 = [];
  for (let g = 0; g < 3; g++) {
    for (let i = 0; i < 3; i++) {
      players9.push(new MockPlayer(g * 3 + i, i, GROUP_NAMES[g]));
    }
  }
  const result9 = reshuffleGroups(players9, GROUP_NAMES);
  console.log(`Groups formed: ${result9.numGroups}, Complete: ${result9.numCompleteGroups}`);
  console.log("Composition:", JSON.stringify(result9.composition, null, 2));
  const allComplete9 = Object.values(result9.composition).every(
    (g) => g.hasAllIndices
  );
  console.log(`✓ All groups complete: ${allComplete9}`);

  // Test speaker rotation for 6 blocks
  console.log("\nSpeaker rotation test (6 blocks):");
  const speakerCounts9 = {};
  for (let block = 0; block < 6; block++) {
    Object.entries(result9.composition).forEach(([groupName, info]) => {
      const groupPlayers = players9.filter(
        (p) => p.get("current_group") === groupName
      );
      const { speaker, usedFallback, targetIndex } = selectSpeaker(groupPlayers, block);
      if (speaker) {
        speakerCounts9[speaker.id] = (speakerCounts9[speaker.id] || 0) + 1;
        console.log(
          `  Block ${block}: Group ${groupName} speaker = ${speaker.get("name")} (idx ${speaker.get("player_index")}, target was ${targetIndex})${usedFallback ? " [FALLBACK]" : ""}`
        );
      }
    });
  }
  console.log("\nSpeaker counts:", speakerCounts9);

  // Test 2: 8 players (one index-0 dropped)
  console.log("\n--- TEST 2: 8 players (one index-0 dropped) ---");
  const players8 = players9.filter((p) => p.id !== 0); // Remove first player
  const result8 = reshuffleGroups(players8, GROUP_NAMES);
  console.log(`Groups formed: ${result8.numGroups}, Complete: ${result8.numCompleteGroups}`);
  console.log("Composition:", JSON.stringify(result8.composition, null, 2));
  const incompleteGroups8 = Object.entries(result8.composition)
    .filter(([_, g]) => !g.hasAllIndices)
    .map(([name, _]) => name);
  console.log(`Incomplete groups: ${incompleteGroups8.join(", ") || "none"}`);

  // Test speaker selection with fallback
  console.log("\nSpeaker selection with fallback (block 0, need index 0):");
  Object.entries(result8.composition).forEach(([groupName, info]) => {
    const groupPlayers = players8.filter(
      (p) => p.get("current_group") === groupName
    );
    const { speaker, usedFallback, targetIndex } = selectSpeaker(groupPlayers, 0);
    if (speaker) {
      console.log(
        `  Group ${groupName}: speaker = ${speaker.get("name")} (idx ${speaker.get("player_index")})${usedFallback ? " [FALLBACK - needed idx 0]" : ""}`
      );
    }
  });

  // Test 3: 6 players (one from each index dropped)
  console.log("\n--- TEST 3: 6 players (one from each index dropped) ---");
  const players6 = players9.filter((p) => p.id !== 0 && p.id !== 4 && p.id !== 8);
  const result6 = reshuffleGroups(players6, GROUP_NAMES);
  console.log(`Groups formed: ${result6.numGroups}, Complete: ${result6.numCompleteGroups}`);
  console.log("Composition:", JSON.stringify(result6.composition, null, 2));

  // Test 4: 5 players
  console.log("\n--- TEST 4: 5 players (severe dropouts) ---");
  const players5 = players9.slice(0, 5);
  const result5 = reshuffleGroups(players5, GROUP_NAMES);
  console.log(`Groups formed: ${result5.numGroups}, Complete: ${result5.numCompleteGroups}`);
  console.log("Composition:", JSON.stringify(result5.composition, null, 2));

  // Test 5: 3 players (TEST_MODE scenario)
  console.log("\n--- TEST 5: 3 players (TEST_MODE) ---");
  const players3 = [
    new MockPlayer(0, 0, "A"),
    new MockPlayer(1, 1, "A"),
    new MockPlayer(2, 2, "A"),
  ];
  const result3 = reshuffleGroups(players3, ["A"]);
  console.log(`Groups formed: ${result3.numGroups}, Complete: ${result3.numCompleteGroups}`);
  console.log("Composition:", JSON.stringify(result3.composition, null, 2));

  console.log("\n" + "=".repeat(60));
  console.log("TEST SUITE COMPLETE");
  console.log("=".repeat(60));
}

runTests();
