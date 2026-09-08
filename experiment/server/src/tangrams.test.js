import { describe, it, expect, vi } from "vitest";
import { resolveTangramSet } from "./tangrams.js";
import { tangram_sets, all_tangrams, distractors } from "./constants.js";

describe("resolveTangramSet", () => {
  it("reads the tangramSet treatment factor", () => {
    expect(resolveTangramSet({ tangramSet: 1 })).toBe(1);
    expect(resolveTangramSet({ tangramSet: "1" })).toBe(1);
    expect(resolveTangramSet({ tangramSet: 0 })).toBe(0);
  });

  it("defaults to set 0 when the factor is absent", () => {
    expect(resolveTangramSet({})).toBe(0);
    expect(resolveTangramSet(undefined)).toBe(0);
    expect(resolveTangramSet({ tangramSet: "" })).toBe(0);
  });

  it("falls back to set 0 with a warning for invalid values", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    expect(resolveTangramSet({ tangramSet: 2 })).toBe(0);
    expect(resolveTangramSet({ tangramSet: -1 })).toBe(0);
    expect(resolveTangramSet({ tangramSet: "abc" })).toBe(0);
    expect(warn).toHaveBeenCalledTimes(3);
    warn.mockRestore();
  });
});

describe("tangram sets", () => {
  it("has two disjoint sets of six targets plus four distractors making the 16-item grid", () => {
    expect(Object.keys(tangram_sets)).toEqual(["0", "1"]);
    expect(tangram_sets[0]).toHaveLength(6);
    expect(tangram_sets[1]).toHaveLength(6);
    expect(new Set([...tangram_sets[0], ...tangram_sets[1]]).size).toBe(12);
    expect(distractors).toHaveLength(4);
    expect(new Set(all_tangrams).size).toBe(16);
    expect(new Set(all_tangrams)).toEqual(new Set([...tangram_sets[0], ...tangram_sets[1], ...distractors]));
  });
});
