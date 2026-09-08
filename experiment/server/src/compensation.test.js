import { describe, it, expect } from "vitest";
import { computePartialPay, applyPartialPay } from "./compensation.js";
import { BASE_PAY, EXPECTED_GAME_DURATION_MIN } from "./constants.js";

const MIN = 60 * 1000;

describe("computePartialPay", () => {
  it("prorates base pay by time spent", () => {
    const half = (EXPECTED_GAME_DURATION_MIN / 2) * MIN;
    const pay = computePartialPay({ startMs: 0, endMs: half, bonus: 0 });
    expect(pay.partialBasePay).toBe(BASE_PAY / 2);
    expect(pay.partialPay).toBe(BASE_PAY / 2);
    expect(pay.minutesSpent).toBe(Math.round(EXPECTED_GAME_DURATION_MIN / 2));
  });

  it("caps base pay at the full amount", () => {
    const pay = computePartialPay({ startMs: 0, endMs: 3 * EXPECTED_GAME_DURATION_MIN * MIN });
    expect(pay.partialBasePay).toBe(BASE_PAY);
  });

  it("adds the earned bonus when the removal was outside the player's control", () => {
    const pay = computePartialPay({ startMs: 0, endMs: 9 * MIN, bonus: 1.234 });
    expect(pay.partialBonus).toBe(1.23);
    expect(pay.partialPay).toBe(Math.round((BASE_PAY * 0.2 + 1.234) * 100) / 100);
  });

  it("forfeits the bonus for inactivity removals but still pays for time", () => {
    const pay = computePartialPay({ startMs: 0, endMs: 9 * MIN, bonus: 3, includeBonus: false });
    expect(pay.partialBonus).toBe(0);
    expect(pay.partialBasePay).toBe(Math.round(BASE_PAY * 0.2 * 100) / 100);
    expect(pay.partialPay).toBe(pay.partialBasePay);
    expect(pay.partialPay).toBeGreaterThan(0);
  });

  it("rounds to cents and never goes negative", () => {
    const pay = computePartialPay({ startMs: 1000, endMs: 0, bonus: 0.005 });
    expect(pay.partialBasePay).toBe(0);
    expect(pay.partialPay).toBeGreaterThanOrEqual(0);
    const odd = computePartialPay({ startMs: 0, endMs: 7 * MIN + 1234, bonus: 1.2345 });
    for (const v of [odd.partialPay, odd.partialBasePay, odd.partialBonus]) {
      expect(Math.round(v * 100) / 100).toBe(v);
    }
  });

  it("treats a missing bonus as zero", () => {
    const pay = computePartialPay({ startMs: 0, endMs: MIN, bonus: undefined });
    expect(pay.partialBonus).toBe(0);
  });
});

describe("applyPartialPay", () => {
  const makePlayer = (attrs) => ({
    attrs: { ...attrs },
    get(k) { return this.attrs[k]; },
    set(k, v) { this.attrs[k] = v; },
  });

  it("writes the four pay attributes from the player's start time and bonus", () => {
    const player = makePlayer({ gameStartTime: 0, bonus: 2 });
    const pay = applyPartialPay(player, { now: 22.5 * MIN });
    expect(player.get("partialPay")).toBe(pay.partialPay);
    expect(player.get("partialBasePay")).toBe(6);
    expect(player.get("partialBonus")).toBe(2);
    expect(player.get("minutesSpent")).toBe(23);
  });

  it("drops the bonus when includeBonus is false", () => {
    const player = makePlayer({ gameStartTime: 0, bonus: 2 });
    applyPartialPay(player, { includeBonus: false, now: 22.5 * MIN });
    expect(player.get("partialBonus")).toBe(0);
    expect(player.get("partialPay")).toBe(6);
  });
});
