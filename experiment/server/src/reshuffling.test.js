// Unit tests for the REAL production reshuffling logic (imported from
// reshuffling.js, not a copy). Uses minimal mocks: players only need
// get/set attribute maps and an id.
import { beforeEach, describe, expect, it, vi } from "vitest";
import { doConstrainedReshuffle, reshuffleGroups } from "./reshuffling";
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

function makeGame(activeGroups) {
  return new Attrs({ active_groups: activeGroups });
}

function groupMembers(players, groupName) {
  return players.filter((p) => p.get("current_group") === groupName);
}

beforeEach(() => {
  vi.spyOn(console, "log").mockImplementation(() => {});
  vi.spyOn(console, "warn").mockImplementation(() => {});
});

describe("reshuffleGroups with a full 9-player game", () => {
  const GROUPS = ["A", "B", "C"];

  it("assigns every player to exactly one group with one player per index, for every block", () => {
    for (let blockNum = 0; blockNum < 6; blockNum++) {
      const players = makePlayers(GROUPS);
      reshuffleGroups(makeGame(GROUPS), players, blockNum);

      const assigned = players.map((p) => p.get("current_group"));
      expect(assigned.every((g) => GROUPS.includes(g))).toBe(true);

      for (const groupName of GROUPS) {
        const members = groupMembers(players, groupName);
        expect(members).toHaveLength(GROUP_SIZE);
        const indices = members.map((p) => p.get("player_index")).sort();
        expect(indices).toEqual([0, 1, 2]);
      }
    }
  });

  it("gives every group exactly one in-group and one out-group listener, for every block", () => {
    for (let blockNum = 0; blockNum < 6; blockNum++) {
      const players = makePlayers(GROUPS);
      reshuffleGroups(makeGame(GROUPS), players, blockNum);

      const speakerIdx = blockNum % GROUP_SIZE;
      for (const groupName of GROUPS) {
        const members = groupMembers(players, groupName);
        const speaker = members.find(
          (p) => p.get("player_index") === speakerIdx,
        );
        expect(speaker).toBeDefined();
        const listeners = members.filter((p) => p !== speaker);
        const inGroup = listeners.filter(
          (p) => p.get("original_group") === speaker.get("original_group"),
        );
        expect(inGroup).toHaveLength(1);
      }
    }
  });

  it("mixes every group (players from at least two original groups)", () => {
    const players = makePlayers(GROUPS);
    reshuffleGroups(makeGame(GROUPS), players, 0);

    for (const groupName of GROUPS) {
      const originalGroups = new Set(
        groupMembers(players, groupName).map((p) => p.get("original_group")),
      );
      expect(originalGroups.size).toBeGreaterThanOrEqual(2);
    }
  });

  it("assigns speakers to groups approximately uniformly (unbiased sigma)", () => {
    const iterations = 3000;
    const counts = { A: 0, B: 0, C: 0 };
    for (let i = 0; i < iterations; i++) {
      const players = makePlayers(GROUPS);
      reshuffleGroups(makeGame(GROUPS), players, 0);
      // Track where the speaker (index 0) from original group A lands
      const speakerA = players.find(
        (p) => p.get("original_group") === "A" && p.get("player_index") === 0,
      );
      counts[speakerA.get("current_group")]++;
    }
    for (const groupName of GROUPS) {
      const proportion = counts[groupName] / iterations;
      expect(proportion).toBeGreaterThan(1 / 3 - 0.05);
      expect(proportion).toBeLessThan(1 / 3 + 0.05);
    }
  });
});

describe("reshuffleGroups with two groups (6 players)", () => {
  const GROUPS = ["A", "B"];

  it("keeps the exactly-one-in-group-listener guarantee via the N=2 derangement", () => {
    for (let blockNum = 0; blockNum < 6; blockNum++) {
      const players = makePlayers(GROUPS);
      reshuffleGroups(makeGame(GROUPS), players, blockNum);

      const speakerIdx = blockNum % GROUP_SIZE;
      for (const groupName of GROUPS) {
        const members = groupMembers(players, groupName);
        expect(members).toHaveLength(GROUP_SIZE);
        const speaker = members.find(
          (p) => p.get("player_index") === speakerIdx,
        );
        const listeners = members.filter((p) => p !== speaker);
        const inGroup = listeners.filter(
          (p) => p.get("original_group") === speaker.get("original_group"),
        );
        expect(inGroup).toHaveLength(1);
      }
    }
  });
});

describe("best-effort fallback for irregular rosters", () => {
  it("doConstrainedReshuffle rejects an incomplete group-by-index matrix", () => {
    // 8 players: original group C is missing its index-2 player
    const players = makePlayers(["A", "B", "C"]).filter(
      (p) => p.id !== "C2",
    );
    const result = doConstrainedReshuffle(players, ["A", "B", "C"], 0);
    expect(result).toBe(false);
  });

  it("still assigns everyone to a viable, mixed group", () => {
    const players = makePlayers(["A", "B", "C"]).filter(
      (p) => p.id !== "C2",
    );
    reshuffleGroups(makeGame(["A", "B", "C"]), players, 0);

    const groups = new Set(players.map((p) => p.get("current_group")));
    for (const p of players) {
      expect(p.get("current_group")).toBeTruthy();
    }
    for (const groupName of groups) {
      const members = groupMembers(players, groupName);
      expect(members.length).toBeGreaterThanOrEqual(MIN_GROUP_SIZE);
    }
    // With multiple original groups present, at least one group must be mixed
    const anyMixed = [...groups].some((groupName) => {
      const originalGroups = new Set(
        groupMembers(players, groupName).map((p) => p.get("original_group")),
      );
      return originalGroups.size >= 2;
    });
    expect(anyMixed).toBe(true);
  });
});
