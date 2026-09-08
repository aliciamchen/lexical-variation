import { describe, it, expect } from "vitest";
import { classifyIdle, isLateClick, updateIdleRounds } from "./idle.js";
import { MAX_IDLE_ROUNDS } from "./constants.js";

describe("classifyIdle", () => {
  it("marks a silent speaker idle and a speaker who sent a message active", () => {
    expect(classifyIdle({ role: "speaker", sentMessage: false })).toBe(true);
    expect(classifyIdle({ role: "speaker", sentMessage: true })).toBe(false);
  });

  it("marks a listener idle only when the speaker spoke and the listener did not click", () => {
    expect(classifyIdle({ role: "listener", clicked: null, speakerSentMessage: true })).toBe(true);
    expect(classifyIdle({ role: "listener", clicked: "page1-1", speakerSentMessage: true })).toBe(false);
  });

  it("does not penalize listeners when the speaker was silent", () => {
    expect(classifyIdle({ role: "listener", clicked: null, speakerSentMessage: false })).toBe(false);
    expect(classifyIdle({ role: "listener", clicked: null, sentMessage: true, speakerSentMessage: false })).toBe(false);
  });
});

describe("isLateClick", () => {
  it("flags a listener click that arrived after the deadline", () => {
    expect(isLateClick({ role: "listener", clicked: "page1-1", clickedAtDeadline: false })).toBe(true);
  });
  it("does not flag clicks present at the deadline, missing clicks, or speakers", () => {
    expect(isLateClick({ role: "listener", clicked: "page1-1", clickedAtDeadline: true })).toBe(false);
    expect(isLateClick({ role: "listener", clicked: null, clickedAtDeadline: false })).toBe(false);
    expect(isLateClick({ role: "speaker", clicked: "page1-1", clickedAtDeadline: false })).toBe(false);
    // No snapshot recorded (e.g. player joined mid-round): not a late click
    expect(isLateClick({ role: "listener", clicked: "page1-1", clickedAtDeadline: undefined })).toBe(false);
  });
});

describe("updateIdleRounds", () => {
  it("counts consecutive idle rounds and removes at the threshold", () => {
    let state = updateIdleRounds(0, true);
    expect(state).toEqual({ idleRounds: 1, remove: MAX_IDLE_ROUNDS <= 1 });
    for (let i = 1; i < MAX_IDLE_ROUNDS; i++) state = updateIdleRounds(state.idleRounds, true);
    expect(state.idleRounds).toBe(MAX_IDLE_ROUNDS);
    expect(state.remove).toBe(true);
  });

  it("does not remove after MAX_IDLE_ROUNDS - 1 idle rounds followed by activity", () => {
    let state = { idleRounds: 0 };
    for (let i = 0; i < MAX_IDLE_ROUNDS - 1; i++) state = updateIdleRounds(state.idleRounds, true);
    expect(state.remove).toBe(false);
    state = updateIdleRounds(state.idleRounds, false);
    expect(state).toEqual({ idleRounds: 0, remove: false });
  });

  it("treats a missing counter as zero", () => {
    expect(updateIdleRounds(undefined, true).idleRounds).toBe(1);
  });
});
