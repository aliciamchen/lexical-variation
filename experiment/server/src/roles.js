/**
 * Speaker selection for a group in a given block (pure; wired in callbacks.js).
 *
 * The designated speaker is the member whose player_index equals
 * blockNum % GROUP_SIZE, so each member speaks once every GROUP_SIZE blocks.
 * If that member has been removed, the role falls back to the remaining
 * members sorted by player_index, rotating with the block number so the same
 * survivor does not speak in every block.
 */
import _ from "lodash";
import { GROUP_SIZE } from "./constants";

export function selectSpeaker(groupPlayers, blockNum, groupSize = GROUP_SIZE) {
  const designatedIndex = blockNum % groupSize;
  const designated = groupPlayers.find((p) => p.get("player_index") === designatedIndex);
  if (designated) return { speaker: designated, reassigned: false, designatedIndex };
  if (groupPlayers.length === 0) return { speaker: null, reassigned: false, designatedIndex };
  const sorted = _.sortBy(groupPlayers, (p) => p.get("player_index"));
  return { speaker: sorted[blockNum % sorted.length], reassigned: true, designatedIndex };
}
