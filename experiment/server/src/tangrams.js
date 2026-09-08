/**
 * Tangram-set assignment. Each game uses one of two target sets; the set is a
 * treatment factor (`tangramSet`, 0 or 1) chosen when the batch is created,
 * so sets can be counterbalanced exactly across games within each condition.
 */
import { tangram_sets } from "./constants";

/**
 * Resolve the tangram set index from a game's treatment. Missing values
 * default to set 0 (the pilot set); anything that is not a valid set index
 * also falls back to 0 with a warning rather than crashing game start.
 */
export function resolveTangramSet(treatment, sets = tangram_sets) {
  const raw = treatment?.tangramSet;
  if (raw === undefined || raw === null || raw === "") return 0;
  const n = Number(raw);
  if (!Number.isInteger(n) || !Object.prototype.hasOwnProperty.call(sets, n)) {
    console.warn(`Invalid tangramSet "${raw}" in treatment; using set 0`);
    return 0;
  }
  return n;
}
