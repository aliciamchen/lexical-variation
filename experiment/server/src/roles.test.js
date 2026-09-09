import { describe, it, expect } from "vitest";
import { selectSpeaker } from "./roles.js";

const P = (idx) => ({ idx, get(k) { return k === "player_index" ? this.idx : undefined; } });

describe("selectSpeaker", () => {
  const group = [P(0), P(1), P(2)];
  it("rotates the designated speaker by block so each member speaks once per three blocks", () => {
    expect([0, 1, 2, 3, 4, 5].map((b) => selectSpeaker(group, b).speaker.idx)).toEqual([0, 1, 2, 0, 1, 2]);
    expect(selectSpeaker(group, 4).reassigned).toBe(false);
  });
  it("falls back to the remaining members, rotating, when the designated speaker is gone", () => {
    const twoLeft = [P(0), P(2)]; // index 1 was removed
    const r = selectSpeaker(twoLeft, 1);
    expect(r.reassigned).toBe(true);
    expect(r.designatedIndex).toBe(1);
    expect(r.speaker.idx).toBe(2); // sorted [0,2], block 1 -> position 1
    expect(selectSpeaker(twoLeft, 4).speaker.idx).toBe(0); // block 4 -> position 0
    // Blocks where the designated member is present are not reassigned
    expect(selectSpeaker(twoLeft, 3)).toMatchObject({ reassigned: false });
    expect(selectSpeaker(twoLeft, 3).speaker.idx).toBe(0);
  });
  it("does not let one survivor speak in every block", () => {
    const twoLeft = [P(1), P(2)];
    const speakers = [0, 1, 2, 3, 4, 5].map((b) => selectSpeaker(twoLeft, b).speaker.idx);
    expect(new Set(speakers).size).toBe(2);
  });
  it("returns null for an empty group", () => {
    expect(selectSpeaker([], 0).speaker).toBeNull();
  });
});
