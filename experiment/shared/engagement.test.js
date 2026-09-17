import { describe, it, expect, vi } from "vitest";
import { createEngagementRecorder, MAX_ENGAGEMENT_EVENTS } from "./engagement.js";

/** A recorder writing into an array, with a fixed clock. */
function makeRecorder(overrides = {}) {
  const written = [];
  const onTruncated = vi.fn();
  const recorder = createEngagementRecorder({
    write: (event) => written.push(event),
    onTruncated,
    now: () => 1000,
    ...overrides,
  });
  return { recorder, written, onTruncated };
}

describe("createEngagementRecorder", () => {
  it("stamps each event with its type and the time", () => {
    const { recorder, written } = makeRecorder();
    recorder.record("hidden");
    recorder.record("offline");
    expect(written).toEqual([
      { t: 1000, type: "hidden" },
      { t: 1000, type: "offline" },
    ]);
  });

  it("carries the extra fields an event supplies", () => {
    const { recorder, written } = makeRecorder();
    recorder.record("resize", { viewportWidth: 800, viewportHeight: 600 });
    expect(written[0]).toEqual({
      t: 1000,
      type: "resize",
      viewportWidth: 800,
      viewportHeight: 600,
    });
  });

  describe("the cap", () => {
    it("stops writing once the cap is reached", () => {
      const { recorder, written } = makeRecorder({ max: 3 });
      for (let i = 0; i < 10; i++) recorder.record("hidden");
      expect(written).toHaveLength(3);
      expect(recorder.count).toBe(3);
    });

    it("reports truncation exactly once, so it cannot spam the scope", () => {
      const { recorder, onTruncated } = makeRecorder({ max: 2 });
      for (let i = 0; i < 10; i++) recorder.record("hidden");
      expect(onTruncated).toHaveBeenCalledTimes(1);
      expect(recorder.truncated).toBe(true);
    });

    it("does not report truncation while still under the cap", () => {
      const { recorder, onTruncated } = makeRecorder({ max: 5 });
      recorder.record("hidden");
      recorder.record("visible");
      expect(onTruncated).not.toHaveBeenCalled();
      expect(recorder.truncated).toBe(false);
    });

    it("defaults to a cap that a normal session cannot reach", () => {
      expect(MAX_ENGAGEMENT_EVENTS).toBe(200);
      const { recorder, written } = makeRecorder();
      for (let i = 0; i < MAX_ENGAGEMENT_EVENTS + 5; i++) recorder.record("hidden");
      expect(written).toHaveLength(MAX_ENGAGEMENT_EVENTS);
    });

    it("is per player, not per recorder: a fresh recorder resumes from the saved count", () => {
      // A reload creates a new recorder; seeded from the player scope it has
      // only the remainder of the cap left, not a fresh two hundred.
      const { recorder, written, onTruncated } = makeRecorder({ max: 5, initialCount: 3 });
      expect(recorder.record("hidden")).toBe(true);
      expect(recorder.record("visible")).toBe(true);
      expect(recorder.record("hidden")).toBe(false);
      expect(written).toHaveLength(2);
      expect(recorder.count).toBe(5);
      expect(onTruncated).toHaveBeenCalledTimes(1);
    });

    it("stays truncated once the player scope says so, without re-marking it", () => {
      const { recorder, written, onTruncated } = makeRecorder({
        max: 5,
        initialCount: 5,
        truncated: true,
      });
      expect(recorder.record("hidden")).toBe(false);
      expect(recorder.recordOnline()).toBe(false);
      expect(written).toEqual([]);
      expect(recorder.truncated).toBe(true);
      expect(onTruncated).not.toHaveBeenCalled();
    });

    it("counts a write that throws, so one broken scope is not retried forever", () => {
      const onTruncated = vi.fn();
      const recorder = createEngagementRecorder({
        write: () => {
          throw new Error("scope gone");
        },
        onTruncated,
        max: 2,
      });
      // The first two attempts reach the failing write and throw; the hook
      // catches that. Past the cap, write is never called, so there is
      // nothing left to throw and the recorder simply declines.
      expect(() => recorder.record("hidden")).toThrow("scope gone");
      expect(() => recorder.record("hidden")).toThrow("scope gone");
      expect(recorder.record("hidden")).toBe(false);
      expect(recorder.count).toBe(2);
      expect(onTruncated).toHaveBeenCalledTimes(1);
    });
  });

  describe("losing and regaining the connection", () => {
    it("writes nothing while offline, because the write cannot be sent", () => {
      const { recorder, written } = makeRecorder();
      expect(recorder.recordOffline(500)).toBe(false);
      expect(written).toEqual([]);
    });

    it("writes the outage on reconnect, keeping the time it began", () => {
      const { recorder, written } = makeRecorder();
      recorder.recordOffline(500);
      recorder.recordOnline();
      // The offline carries the moment the connection dropped, not the moment
      // it was written, so the length of the outage is recoverable.
      expect(written).toEqual([
        { t: 500, type: "offline" },
        { t: 1000, type: "online" },
      ]);
    });

    it("keeps the first drop when offline fires more than once", () => {
      const { recorder, written } = makeRecorder();
      recorder.recordOffline(500);
      recorder.recordOffline(700);
      recorder.recordOnline();
      expect(written[0]).toEqual({ t: 500, type: "offline" });
      expect(written).toHaveLength(2);
    });

    it("records a reconnection that had no recorded drop", () => {
      const { recorder, written } = makeRecorder();
      recorder.recordOnline();
      expect(written).toEqual([{ t: 1000, type: "online" }]);
    });

    it("starts a fresh outage after the previous one closed", () => {
      const { recorder, written } = makeRecorder();
      recorder.recordOffline(500);
      recorder.recordOnline();
      recorder.recordOffline(2000);
      recorder.recordOnline();
      expect(written.map((e) => [e.type, e.t])).toEqual([
        ["offline", 500],
        ["online", 1000],
        ["offline", 2000],
        ["online", 1000],
      ]);
    });
  });

  describe("resize", () => {
    it("records the first resize, having nothing to compare against", () => {
      const { recorder, written } = makeRecorder();
      expect(recorder.recordResize({ viewportWidth: 800, viewportHeight: 600 })).toBe(true);
      expect(written).toHaveLength(1);
    });

    it("ignores a resize that left the viewport the same size", () => {
      const { recorder, written } = makeRecorder();
      recorder.recordResize({ viewportWidth: 800, viewportHeight: 600 });
      expect(recorder.recordResize({ viewportWidth: 800, viewportHeight: 600 })).toBe(false);
      expect(written).toHaveLength(1);
    });

    it("records a change in either dimension", () => {
      const { recorder, written } = makeRecorder();
      recorder.recordResize({ viewportWidth: 800, viewportHeight: 600 });
      recorder.recordResize({ viewportWidth: 900, viewportHeight: 600 });
      recorder.recordResize({ viewportWidth: 900, viewportHeight: 700 });
      expect(written).toHaveLength(3);
    });

    it("records a return to an earlier size, which is still a change", () => {
      const { recorder, written } = makeRecorder();
      recorder.recordResize({ viewportWidth: 800, viewportHeight: 600 });
      recorder.recordResize({ viewportWidth: 900, viewportHeight: 600 });
      recorder.recordResize({ viewportWidth: 800, viewportHeight: 600 });
      expect(written).toHaveLength(3);
    });

    it("counts against the same cap as every other event", () => {
      const { recorder, written } = makeRecorder({ max: 2 });
      recorder.record("hidden");
      recorder.recordResize({ viewportWidth: 800, viewportHeight: 600 });
      expect(recorder.recordResize({ viewportWidth: 900, viewportHeight: 600 })).toBe(false);
      expect(written).toHaveLength(2);
    });
  });
});
