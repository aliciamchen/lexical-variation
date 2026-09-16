/**
 * Group-viability rules (pure functions; wired in callbacks.js).
 *
 * An original group stays viable while it has at least MIN_GROUP_SIZE active
 * members, in both phases and all conditions: a lone member has no partners
 * in refer_separated and no in-group listener for the social task in the
 * mixed conditions. The game continues while at least `minRequired` original
 * groups are viable (2 when the game started with more than one group).
 */
import { GROUP_NAMES, MIN_GROUP_SIZE } from "./constants";

const isActive = (p) => Boolean(p.get("is_active"));

/** Names of the original groups that still have at least `minGroupSize` active members. */
export function viableOriginalGroups(players, activeGroups = GROUP_NAMES, minGroupSize = MIN_GROUP_SIZE) {
  return activeGroups.filter(
    (g) => players.filter((p) => isActive(p) && p.get("original_group") === g).length >= minGroupSize,
  );
}

/** Active players whose original group is not viable (to be removed as "group disbanded"). */
export function strandedPlayers(players, activeGroups = GROUP_NAMES, minGroupSize = MIN_GROUP_SIZE) {
  const viable = new Set(viableOriginalGroups(players, activeGroups, minGroupSize));
  return players.filter(
    (p) => isActive(p) && activeGroups.includes(p.get("original_group")) && !viable.has(p.get("original_group")),
  );
}

/** Whether the game can continue with this many viable original groups. */
export function gameCanContinue(viableGroupCount, minRequired) {
  return viableGroupCount >= (minRequired || 1);
}
