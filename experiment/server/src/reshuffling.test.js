// Unit tests for the production reshuffling logic (imported from
// reshuffling.js, not a copy). Players only need get/set attribute maps and an
// id; the speaker rule comes from the real roles.js through the module.
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  chooseAssignment,
  enumerateAssignments,
  inGroupListenerCount,
  reshuffleGroups,
} from "./reshuffling";
import { selectSpeaker } from "./roles";
import { GROUP_SIZE, MIN_GROUP_SIZE } from "./constants";

class Attrs {
  constructor(init = {}) {
    this.map = new Map(Object.entries(init));
  }
  get(key) {
    return this.map.get(key);
  }
  set(key, value) {
    this.map.set(key, value);
  }
}

function makePlayer(originalGroup, playerIndex) {
  const player = new Attrs({
    original_group: originalGroup,
    player_index: playerIndex,
    current_group: null,
    name: `${originalGroup}${playerIndex}`,
  });
  player.id = `${originalGroup}${playerIndex}`;
  return player;
}

function makePlayers(groups) {
  const players = [];
  for (const group of groups) {
    for (let idx = 0; idx < GROUP_SIZE; idx++) {
      players.push(makePlayer(group, idx));
    }
  }
  return players;
}

function removePlayers(players, ids) {
  return players.filter((p) => !ids.includes(p.id));
}

function makeGame(activeGroups) {
  return new Attrs({ active_groups: activeGroups });
}

function groupMembers(players, groupName) {
  return players.filter((p) => p.get("current_group") === groupName);
}

function currentGroups(players) {
  return [...new Set(players.map((p) => p.get("current_group")))].sort();
}

function assertAllAssigned(players, allowedNames) {
  for (const p of players) {
    expect(allowedNames).toContain(p.get("current_group"));
  }
  for (const g of currentGroups(players)) {
    expect(groupMembers(players, g).length).toBeGreaterThanOrEqual(MIN_GROUP_SIZE);
  }
}

function assertOnePlayerPerIndex(players) {
  for (const g of currentGroups(players)) {
    const indices = groupMembers(players, g).map((p) => p.get("player_index"));
    expect(new Set(indices).size).toBe(indices.length);
  }
}

beforeEach(() => {
  vi.spyOn(console, "log").mockImplementation(() => {});
  vi.spyOn(console, "warn").mockImplementation(() => {});
  vi.spyOn(console, "error").mockImplementation(() => {});
});

describe("enumerateAssignments", () => {
  it("lists every one-per-index assignment of nine players into three slots", () => {
    const all = enumerateAssignments(makePlayers(["A", "B", "C"]), 3);
    expect(all).toHaveLength(216);
    for (const groups of all) {
      expect(groups).toHaveLength(3);
      for (const g of groups) {
        expect(g).toHaveLength(3);
        expect(new Set(g.map((p) => p.get("player_index"))).size).toBe(3);
      }
    }
  });

  it("handles an index with fewer players than slots without leaving a slot empty when another index fills it", () => {
    const seven = removePlayers(makePlayers(["A", "B", "C"]), ["A1", "B2"]);
    const all = enumerateAssignments(seven, 3);
    expect(all).toHaveLength(6 * 6 * 6);
    expect(all.some((groups) => groups.some((g) => g.length === 0))).toBe(false);
    const sizes = new Set(all.map((groups) => groups.map((g) => g.length).sort().join("")));
    expect(sizes.has("133")).toBe(true);
    expect(sizes.has("223")).toBe(true);
  });
});

describe("reshuffleGroups with a full 9-player game", () => {
  const GROUPS = ["A", "B", "C"];

  it("assigns every player to exactly one group with one player per index, for every block", () => {
    for (let blockNum = 0; blockNum < 6; blockNum++) {
      const players = makePlayers(GROUPS);
      const info = reshuffleGroups(makeGame(GROUPS), players, blockNum);
      expect(info.mode).toBe("constrained");
      expect(info.nGroups).toBe(3);
      expect(info.nPairs).toBe(0);
      assertAllAssigned(players, GROUPS);
      for (const groupName of GROUPS) {
        const members = groupMembers(players, groupName);
        expect(members).toHaveLength(GROUP_SIZE);
        expect(members.map((p) => p.get("player_index")).sort()).toEqual([0, 1, 2]);
      }
    }
  });

  it("gives every group exactly one in-group and one out-group listener, for every block", () => {
    for (let blockNum = 0; blockNum < 6; blockNum++) {
      const players = makePlayers(GROUPS);
      const info = reshuffleGroups(makeGame(GROUPS), players, blockNum);
      expect(info.nTriosOk).toBe(3);
      for (const groupName of GROUPS) {
        const members = groupMembers(players, groupName);
        const { speaker, reassigned } = selectSpeaker(members, blockNum);
        expect(reassigned).toBe(false);
        expect(speaker.get("player_index")).toBe(blockNum % GROUP_SIZE);
        expect(inGroupListenerCount(members, blockNum)).toBe(1);
      }
    }
  });

  it("mixes every group (players from at least two original groups)", () => {
    const players = makePlayers(GROUPS);
    reshuffleGroups(makeGame(GROUPS), players, 0);
    for (const groupName of GROUPS) {
      const originalGroups = new Set(groupMembers(players, groupName).map((p) => p.get("original_group")));
      expect(originalGroups.size).toBeGreaterThanOrEqual(2);
    }
  });

  it("only ever produces the four partitions of the constrained construction", () => {
    // Given the speaker index, the in-group listener index (2 options) and the
    // derangement (2 options) determine who is with whom; labels do not.
    const partitions = new Set();
    for (let i = 0; i < 400; i++) {
      const players = makePlayers(GROUPS);
      reshuffleGroups(makeGame(GROUPS), players, 0);
      const key = currentGroups(players)
        .map((g) => groupMembers(players, g).map((p) => p.id).sort().join(""))
        .sort()
        .join("|");
      partitions.add(key);
    }
    expect(partitions.size).toBe(4);
  });

  it("assigns speakers to groups approximately uniformly (unbiased labels)", () => {
    const iterations = 3000;
    const counts = { A: 0, B: 0, C: 0 };
    for (let i = 0; i < iterations; i++) {
      const players = makePlayers(GROUPS);
      reshuffleGroups(makeGame(GROUPS), players, 0);
      const speakerA = players.find((p) => p.get("original_group") === "A" && p.get("player_index") === 0);
      counts[speakerA.get("current_group")]++;
    }
    for (const groupName of GROUPS) {
      const proportion = counts[groupName] / iterations;
      expect(proportion).toBeGreaterThan(1 / 3 - 0.05);
      expect(proportion).toBeLessThan(1 / 3 + 0.05);
    }
  });

  it("uses the in-group listener index and the derangement approximately uniformly", () => {
    const iterations = 2000;
    let inGroupAtIndex1 = 0;
    for (let i = 0; i < iterations; i++) {
      const players = makePlayers(GROUPS);
      reshuffleGroups(makeGame(GROUPS), players, 0);
      const a0 = players.find((p) => p.id === "A0");
      const a1 = players.find((p) => p.id === "A1");
      if (a0.get("current_group") === a1.get("current_group")) inGroupAtIndex1++;
    }
    expect(inGroupAtIndex1 / iterations).toBeGreaterThan(0.45);
    expect(inGroupAtIndex1 / iterations).toBeLessThan(0.55);
  });
});

describe("reshuffleGroups with two full groups (6 players)", () => {
  const GROUPS = ["A", "B"];

  it("keeps the exactly-one-in-group-listener rule via the forced derangement", () => {
    for (let blockNum = 0; blockNum < 6; blockNum++) {
      const players = makePlayers(GROUPS);
      const info = reshuffleGroups(makeGame(GROUPS), players, blockNum);
      expect(info.mode).toBe("constrained");
      for (const groupName of GROUPS) {
        const members = groupMembers(players, groupName);
        expect(members).toHaveLength(GROUP_SIZE);
        expect(inGroupListenerCount(members, blockNum)).toBe(1);
      }
    }
  });
});

describe("reshuffleGroups after dropout", () => {
  const GROUPS = ["A", "B", "C"];

  it("8 players: both trios meet the rule and the pair's listener is in-group half the time", () => {
    let pairInGroup = 0;
    const trials = 600;
    for (let t = 0; t < trials; t++) {
      const block = t % 6;
      const players = removePlayers(makePlayers(GROUPS), ["C2"]);
      const info = reshuffleGroups(makeGame(GROUPS), players, block);
      expect(info.mode).toBe("reduced");
      expect(info.nTrios).toBe(2);
      expect(info.nTriosOk).toBe(2);
      expect(info.nPairs).toBe(1);
      assertAllAssigned(players, GROUPS);
      assertOnePlayerPerIndex(players);
      const pair = currentGroups(players).map((g) => groupMembers(players, g)).find((g) => g.length === 2);
      expect(pair).toBeDefined();
      const status = inGroupListenerCount(pair, block) === 1;
      expect(status).toBe(info.pairTargetInGroup);
      if (status) pairInGroup++;
    }
    expect(pairInGroup / trials).toBeGreaterThan(0.4);
    expect(pairInGroup / trials).toBeLessThan(0.6);
  });

  it("7 players (two groups lost one member each): the trio meets the rule and both pairs follow the coin", () => {
    for (let block = 0; block < 6; block++) {
      const players = removePlayers(makePlayers(GROUPS), ["A1", "B2"]);
      const info = reshuffleGroups(makeGame(GROUPS), players, block);
      expect(info.nTrios).toBe(1);
      expect(info.nTriosOk).toBe(1);
      expect(info.nPairs).toBe(2);
      assertAllAssigned(players, GROUPS);
      assertOnePlayerPerIndex(players);
      for (const g of currentGroups(players)) {
        const members = groupMembers(players, g);
        if (members.length === 2) {
          expect(inGroupListenerCount(members, block) === 1).toBe(info.pairTargetInGroup);
        }
      }
    }
  });

  it("6 players as three pairs are regrouped into two trios that both meet the rule", () => {
    for (let block = 0; block < 6; block++) {
      const players = removePlayers(makePlayers(GROUPS), ["A2", "B1", "C0"]);
      const info = reshuffleGroups(makeGame(GROUPS), players, block);
      expect(info.nGroups).toBe(2);
      expect(info.nTrios).toBe(2);
      expect(info.nTriosOk).toBe(2);
      expect(info.nPairs).toBe(0);
      expect(info.mode).toBe("constrained");
      assertAllAssigned(players, GROUPS);
    }
  });

  it("5 and 4 players form a trio plus a pair, and two pairs", () => {
    const five = removePlayers(makePlayers(["A", "B"]), ["A0"]);
    const infoFive = reshuffleGroups(makeGame(["A", "B"]), five, 1);
    expect(infoFive.nTrios).toBe(1);
    expect(infoFive.nTriosOk).toBe(1);
    expect(infoFive.nPairs).toBe(1);
    assertAllAssigned(five, ["A", "B"]);

    const four = removePlayers(makePlayers(["A", "B"]), ["A0", "B1"]);
    const infoFour = reshuffleGroups(makeGame(["A", "B"]), four, 2);
    expect(infoFour.nTrios).toBe(0);
    expect(infoFour.nPairs).toBe(2);
    assertAllAssigned(four, ["A", "B"]);
  });

  it("a single remaining original group cannot be mixed but is still assigned", () => {
    const players = makePlayers(["A"]);
    const info = reshuffleGroups(makeGame(["A"]), players, 0);
    expect(info.nGroups).toBe(1);
    assertAllAssigned(players, ["A"]);
  });

  it("an undefined block number is treated as block 0", () => {
    const players = makePlayers(GROUPS);
    const info = reshuffleGroups(makeGame(GROUPS), players, undefined);
    expect(info.mode).toBe("constrained");
    assertAllAssigned(players, GROUPS);
  });

  it("returns null when fewer than two players remain", () => {
    const one = makePlayers(["A"]).slice(0, 1);
    expect(reshuffleGroups(makeGame(["A"]), one, 0)).toBeNull();
  });
});

describe("chooseAssignment", () => {
  it("is deterministic given the random stream and reports the candidate counts", () => {
    const players = makePlayers(["A", "B", "C"]);
    const seq = [0.2, 0.7];
    const rng = () => seq.shift() ?? 0.5;
    const chosen = chooseAssignment(players, 3, 0, rng);
    expect(chosen.pairTargetInGroup).toBe(true);
    expect(chosen.nCandidates).toBe(216);
    expect(chosen.nBest).toBe(24);
    expect(chosen.key).toEqual([3, 3, 0]);
  });
});
