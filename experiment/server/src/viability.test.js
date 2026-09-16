import { describe, it, expect } from "vitest";
import { viableOriginalGroups, strandedPlayers, gameCanContinue } from "./viability.js";
import { MIN_GROUP_SIZE } from "./constants.js";

const P = (originalGroup, currentGroup = originalGroup, isActive = true) => ({
  attrs: { original_group: originalGroup, current_group: currentGroup, is_active: isActive },
  get(k) { return this.attrs[k]; },
});
const full = () => ["A", "B", "C"].flatMap((g) => [P(g), P(g), P(g)]);

describe("viableOriginalGroups", () => {
  it("keeps every group of a full game", () => {
    expect(viableOriginalGroups(full())).toEqual(["A", "B", "C"]);
  });
  it("keeps a group that lost one member and drops a group down to one", () => {
    const players = [P("A"), P("A"), P("A", "A", false), P("B"), P("B", "B", false), P("B", "B", false), P("C"), P("C"), P("C")];
    expect(viableOriginalGroups(players)).toEqual(["A", "C"]);
    expect(MIN_GROUP_SIZE).toBe(2);
  });
  it("only considers groups listed as active", () => {
    expect(viableOriginalGroups(full(), ["A", "B"])).toEqual(["A", "B"]);
  });
});

describe("strandedPlayers", () => {
  it("returns the lone active member of a disbanded group and nobody else", () => {
    const lone = P("B");
    const players = [P("A"), P("A"), lone, P("B", "B", false), P("B", "B", false), P("C"), P("C")];
    expect(strandedPlayers(players)).toEqual([lone]);
  });
  it("is empty when every group is viable", () => {
    expect(strandedPlayers(full())).toEqual([]);
  });
});

describe("gameCanContinue", () => {
  it("requires two viable original groups when the game started with several", () => {
    expect(gameCanContinue(2, 2)).toBe(true);
    expect(gameCanContinue(1, 2)).toBe(false);
  });
  it("requires one when the game started with a single group (test games)", () => {
    expect(gameCanContinue(1, 1)).toBe(true);
    expect(gameCanContinue(0, 1)).toBe(false);
    expect(gameCanContinue(1, undefined)).toBe(true);
  });
});
