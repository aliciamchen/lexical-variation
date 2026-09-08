/**
 * Partial-pay rules for players who leave the game early.
 *
 * Every removed player is paid base pay prorated to the time they spent,
 * capped at the full base pay. Players whose game ended for reasons outside
 * their control (their group disbanded, their group failed the Phase 1
 * accuracy check, or too few groups remained) also keep the bonus they had
 * earned. Players removed for inactivity forfeit the bonus: the prorated base
 * pay compensates their time, and the lost bonus is the incentive not to idle.
 *
 * Pure functions so the arithmetic can be unit tested; `applyPartialPay`
 * writes the result onto an Empirica player.
 */
import { BASE_PAY, EXPECTED_GAME_DURATION_MIN } from "./constants";

const round2 = (x) => Math.round(x * 100) / 100;

/**
 * @param {object} opts
 * @param {number} opts.startMs   game start time (ms since epoch)
 * @param {number} opts.endMs     removal time (ms since epoch)
 * @param {number} [opts.bonus]   bonus earned so far, in dollars
 * @param {boolean} [opts.includeBonus=true]  false for inactivity removals
 */
export function computePartialPay({ startMs, endMs, bonus = 0, includeBonus = true }) {
  const elapsedMs = Math.max(0, (endMs ?? Date.now()) - (startMs ?? endMs ?? Date.now()));
  const minutesSpent = elapsedMs / (1000 * 60);
  const partialBasePay = Math.min(
    BASE_PAY,
    (minutesSpent / EXPECTED_GAME_DURATION_MIN) * BASE_PAY,
  );
  const partialBonus = includeBonus ? Number(bonus) || 0 : 0;
  return {
    partialPay: round2(partialBasePay + partialBonus),
    partialBasePay: round2(partialBasePay),
    partialBonus: round2(partialBonus),
    minutesSpent: Math.round(minutesSpent),
  };
}

/**
 * Compute and store partial pay on a player being removed.
 * Reads `gameStartTime` and `bonus` from the player; writes `partialPay`,
 * `partialBasePay`, `partialBonus`, and `minutesSpent`.
 */
export function applyPartialPay(player, { includeBonus = true, now = Date.now() } = {}) {
  const pay = computePartialPay({
    startMs: player.get("gameStartTime"),
    endMs: now,
    bonus: player.get("bonus") || 0,
    includeBonus,
  });
  player.set("partialPay", pay.partialPay);
  player.set("partialBasePay", pay.partialBasePay);
  player.set("partialBonus", pay.partialBonus);
  player.set("minutesSpent", pay.minutesSpent);
  return pay;
}
