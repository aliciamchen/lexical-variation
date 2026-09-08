import { describe, it, expect } from "vitest";
import { accuracyCheckBlocks, playerAccuracyOverBlocks, evaluateGroupAccuracy } from "./accuracy.js";

describe("accuracyCheckBlocks", () => {
  it("returns the last three of six Phase 1 blocks in production", () => {
    expect(accuracyCheckBlocks(6, 3)).toEqual([3, 4, 5]);
  });
  it("returns all blocks when Phase 1 has no more blocks than the window (test mode)", () => {
    expect(accuracyCheckBlocks(3, 3)).toEqual([0, 1, 2]);
    expect(accuracyCheckBlocks(2, 3)).toEqual([0, 1]);
  });
});

describe("playerAccuracyOverBlocks", () => {
  const blocks = [3, 4, 5];
  it("pools correct and total over the checked blocks only", () => {
    const ba = { 0: { correct: 0, total: 6 }, 3: { correct: 6, total: 6 }, 4: { correct: 2, total: 6 }, 5: { correct: 0, total: 6 } };
    const r = playerAccuracyOverBlocks(ba, blocks);
    expect(r.totalCorrect).toBe(8);
    expect(r.totalTrials).toBe(18);
    expect(r.accuracy).toBeCloseTo(8 / 18);
    expect(r.meetsThreshold).toBe(false);
  });
  it("passes at exactly two thirds", () => {
    const r = playerAccuracyOverBlocks({ 3: { correct: 8, total: 12 } }, blocks);
    expect(r.meetsThreshold).toBe(true);
    expect(playerAccuracyOverBlocks({ 3: { correct: 7, total: 12 } }, blocks).meetsThreshold).toBe(false);
  });
  it("scores 0 when no trials were counted (e.g. the speaker never sent a message)", () => {
    const r = playerAccuracyOverBlocks({}, blocks);
    expect(r).toEqual({ accuracy: 0, meetsThreshold: false, totalCorrect: 0, totalTrials: 0 });
  });
  it("ignores blocks outside the window even if recorded", () => {
    expect(playerAccuracyOverBlocks({ 0: { correct: 6, total: 6 } }, blocks).totalTrials).toBe(0);
  });
});

describe("evaluateGroupAccuracy", () => {
  it("passes a full group when two of three members meet the threshold", () => {
    expect(evaluateGroupAccuracy([1, 0.7, 0.2]).groupMeetsThreshold).toBe(true);
    expect(evaluateGroupAccuracy([1, 0.5, 0.2]).groupMeetsThreshold).toBe(false);
  });
  it("requires both members of a two-person group", () => {
    expect(evaluateGroupAccuracy([1, 0.5]).groupMeetsThreshold).toBe(false);
    expect(evaluateGroupAccuracy([0.7, 0.7]).groupMeetsThreshold).toBe(true);
  });
  it("counts exactly two-thirds accuracy as meeting the threshold", () => {
    expect(evaluateGroupAccuracy([2 / 3, 2 / 3, 0]).groupMeetsThreshold).toBe(true);
  });
  it("fails an empty group", () => {
    expect(evaluateGroupAccuracy([]).groupMeetsThreshold).toBe(false);
  });
});
