// ============ SHARED CONSTANTS ============
// Import from here in both client/src and server/src.

// ============ TEST MODE ============
// Defaults to false for production. Set TEST_MODE=true env var for local testing.
// TEST_MODE shortens the game (fewer blocks) but keeps production timers and the
// production idle threshold, so end-to-end tests exercise the timing that
// participants actually get.
export const TEST_MODE =
  typeof process !== "undefined" && process.env?.TEST_MODE === "true";

// ============ TESTING VS PRODUCTION VALUES ============
// TEST_MODE only affects the number of blocks, not player/group counts or timing.
// Player count is set in treatments.yaml and group count is derived from player count.
//
// | Setting              | Testing | Production | Description                          |
// |----------------------|---------|------------|--------------------------------------|
// | TEST_MODE            | true    | false      | Master toggle                        |
// | SELECTION_DURATION   | 45      | 45         | Seconds for Phase 1 selection stage  |
// | PHASE2_SEL_DURATION  | 25      | 25         | Seconds for Phase 2 selection stage  |
// | MAX_IDLE_ROUNDS      | 3       | 3          | Rounds before idle kick              |
// | PHASE_1_BLOCKS       | 3       | 6          | Blocks in Phase 1                    |
// | PHASE_2_BLOCKS       | 2       | 6          | Blocks in Phase 2                    |

// ============ IDLE-TEST TIMING ============
// Idle-detection tests must wait out the FULL selection timer for
// MAX_IDLE_ROUNDS consecutive rounds (an idle player never submits).
// IDLE_TEST_TIMING=true shortens the timer to 30 s and the idle threshold to 2
// for suites that exercise idleness (see `npm run test:group4:fast`).
export const IDLE_TEST_TIMING =
  typeof process !== "undefined" && process.env?.IDLE_TEST_TIMING === "true";

// ============ TIMING CONFIGURATION ============
// Stage durations in seconds
export const SELECTION_DURATION = IDLE_TEST_TIMING ? 30 : 45; // Phase 1 selection stage
export const PHASE2_SELECTION_DURATION = IDLE_TEST_TIMING ? 30 : 25; // Phase 2 selection stage
export const FEEDBACK_DURATION = 15; // Feedback stage (same for both)
export const TRANSITION_DURATION = 60; // Phase transition (same for both)
export const BONUS_INFO_DURATION = 30; // End game bonus info (same for both)

// ============ TANGRAM SETS ============
// All 16 tangrams displayed in the grid (from tangram_sets.json)
export const all_tangrams = [
  "page7-255", "page9-46", "page5-28", "page7-107",
  "page3-35", "page-B", "page3-121", "page4-157",
  "page7-26", "page5-64", "page6-149", "page3-193",
  "page5-63", "page9-7", "page5-142", "page4-15",
];

// Two sets of 6 target tangrams (the other 4 are permanent distractors)
export const tangram_sets = {
  0: ["page7-255", "page9-46", "page5-28", "page7-107", "page3-35", "page-B"],
  1: ["page3-121", "page4-157", "page7-26", "page5-64", "page6-149", "page3-193"],
};

// 4 permanent distractors (never the referent)
export const distractors = ["page5-63", "page9-7", "page5-142", "page4-15"];

// ============ PLAYER CONFIGURATION ============
// Player count is set in treatments.yaml (playerCount field)
// Group count is derived dynamically in callbacks.js from actual player count
export const GROUP_SIZE = 3;
export const LISTENERS_PER_TRIAL = 2;

// Group names (no color distinction)
export const GROUP_NAMES = ["A", "B", "C"];

// ============ PHASE CONFIGURATION ============
// Phase 1: Within-group reference game
// Phase 2: Continued reference game (condition-dependent)
export const PHASE_1_BLOCKS = TEST_MODE ? 3 : 6; // Each player speaks twice in production (3 for test to match ACCURACY_CHECK_BLOCKS)
export const PHASE_2_BLOCKS = TEST_MODE ? 2 : 6;

// ============ GAME STRUCTURE ============
export const NUM_TANGRAMS = 6;
export const NUM_DISPLAY_TANGRAMS = 16;

// ============ PLAYER NAMES ============
export const names = [
  "Repi",
  "Minu",
  "Laju",
  "Hera",
  "Zuda",
  "Bavi",
  "Lika",
  "Felu",
  "Nori", // Added 9th name
];

// ============ EXPERIMENTAL CONDITIONS ============
// Between-subjects conditions (set at game creation)
export const conditions = [
  "refer_separated", "refer_mixed", "social_mixed", "social_first",
];

// Helper: conditions where groups are reshuffled in Phase 2
export function isMixedCondition(condition) {
  return ["refer_mixed", "social_mixed", "social_first"].includes(condition);
}

// Helper: conditions where social guessing is enabled in Phase 2
export function hasSocialGuessing(condition) {
  return ["social_mixed", "social_first"].includes(condition);
}

// ============ AVATAR CONFIGURATION ============
// Using DiceBear API for avatars (https://www.dicebear.com)

// Regular avatar seeds for Phase 1 (identicon style)
export const avatar_seeds = [
  "aria",
  "katherine",
  "kayla",
  "oliver",
  "kaylee",
  "alexandra",
  "cole",
  "noah",
  "morgan",
];

// Avatars are served from our own origin, not fetched from DiceBear at play
// time. In the mixed conditions the anonymous seed changes every trial, so
// nine players would each request a fresh avatar on all 36 Phase 2 trials --
// hundreds of third-party requests per game, on the critical path, in the
// condition where identity IS the manipulation. Every seed is deterministic,
// so the set is downloaded once by scripts/fetch-avatars.mjs and committed.
// The DiceBear URLs stay here as the record of how each file was generated.
export const DICEBEAR_IDENTICON = (seed) =>
  `https://api.dicebear.com/9.x/identicon/svg?seed=${seed}&backgroundColor=e0f2fe&rowColor=0369a1`;
export const DICEBEAR_SHAPES = (seed) =>
  `https://api.dicebear.com/9.x/shapes/svg?seed=${seed}&backgroundColor=e5e7eb&shape1Color=9ca3af&shape2Color=6b7280&shape3Color=4b5563`;

/** The file a seed is stored under. Seeds are alphanumeric plus underscores. */
export const avatarFileName = (seed) => `${String(seed).replace(/[^a-zA-Z0-9_-]/g, "_")}.svg`;

/** Served path for a seed; both helpers below resolve to one of these. */
export const avatarPath = (seed) => `/avatars/${avatarFileName(seed)}`;

export const getAvatarUrl = (seed) => avatarPath(seed);
export const getAnonymousAvatarUrl = (seed) => avatarPath(seed);

/**
 * Every anonymous seed the server can generate, in the shape callbacks.js
 * builds it: `anon_block{block}_trial{trial}_player{index}`. Enumerated from
 * the production block count and roster so the download script and the test
 * cover every avatar a real session can ask for, whatever TEST_MODE says.
 */
export function anonymousAvatarSeeds() {
  const seeds = [];
  const blocks = Math.max(PHASE_2_BLOCKS, 6);
  const players = GROUP_NAMES.length * GROUP_SIZE;
  for (let block = 0; block < blocks; block++) {
    for (let trial = 0; trial < NUM_TANGRAMS; trial++) {
      for (let index = 0; index < players; index++) {
        seeds.push(`anon_block${block}_trial${trial}_player${index}`);
      }
    }
  }
  return seeds;
}

// Neutral colors for player names (no group distinction)
export const name_colors = [
  "#29828D",
  "#444EA1",
  "#57AEC6",
  "#5792C8",
  "#A93F39",
  "#D075A7",
  "#A9385B",
  "#A93849",
  "#6B7280", // Added 9th color (neutral gray)
];

// ============ SCORING ============
export const BONUS_PER_POINT = 0.0556;
export const bonus_per_point = BONUS_PER_POINT; // Alias for server compatibility
export const LISTENER_CORRECT_POINTS = 2;
// Speaker scoring: 2 * (proportion of correct listeners) - max 2 points per round
export const SPEAKER_MAX_POINTS_PER_ROUND = 2;
export const SOCIAL_GUESS_CORRECT_POINTS = 6;
// Speaker bonus: points for each original-group listener who correctly identifies them
export const SOCIAL_SPEAKER_POINTS_PER_CORRECT = 6;
// Social condition has more scoring opportunities, so lower multiplier to keep max bonus similar
export const BONUS_PER_POINT_SOCIAL = 0.023;

// ============ COMPENSATION ============
export const BASE_PAY = 12; // dollars
export const LOBBY_TIMEOUT_PAY = 2; // dollars for players who couldn't find a match in lobby

// Prolific completion codes shown on the exit screens
export const PROLIFIC_CODES = {
  completion: "C2I8XDMC", // finished the game
  lobbyTimeout: "CMZUY3MK", // no game formed within the lobby timeout
  partial: "CFTYDMIY", // removed early (disbanded, low accuracy, insufficient groups, inactivity)
};

// Expected game duration in minutes (used for proportional compensation)
export const EXPECTED_GAME_DURATION_MIN = 45; // full base pay after 45 minutes (task estimate is 45-60 min)

// ============ DROPOUT HANDLING ============
export const MAX_IDLE_ROUNDS = IDLE_TEST_TIMING ? 2 : 3; // consecutive idle rounds before removal (2 under IDLE_TEST_TIMING)
export const MIN_GROUP_SIZE = 2; // Minimum players needed to continue in a group
// MIN_ACTIVE_GROUPS is derived dynamically in callbacks.js based on actual group count

// Why a player left before the end. The server writes one of these to the
// player's `exitReason` (and `ended`) when it removes them; the client routes
// the exit screens on it; operations/game_constants.py reads this object so the
// payment tooling words each removal message from the same list. Empirica
// itself writes "game ended", "game failed" (lobby timeout), and
// "game terminated" (the admin stopped the batch) to `ended`.
export const EXIT_REASONS = {
  quizFailed: "quiz failed", // three failed quiz attempts; no pay
  playerTimeout: "player timeout", // idle for MAX_IDLE_ROUNDS; prorated base, no bonus
  groupDisbanded: "group disbanded", // own original group fell below MIN_GROUP_SIZE
  insufficientGroups: "insufficient groups", // too few viable groups remained mid-game
  lowAccuracy: "low accuracy", // own group failed the Phase 1 accuracy screen
  insufficientGroupsAccuracy: "insufficient groups after accuracy check",
  gameTerminated: "game terminated", // the researcher stopped the batch
};

// ============ INTRO ============
export const MAX_QUIZ_ATTEMPTS = 3; // quiz attempts before the player is excluded
// Shared lobby wait before a batch fails; must match `duration` in
// .empirica/lobbies.yaml, which Empirica reads directly.
export const LOBBY_TIMEOUT_MINUTES = 10;

// ============ PHASE 1 ACCURACY THRESHOLD ============
// At end of Phase 1, remove groups where fewer than 2/3 of players achieved >= 2/3 accuracy
// Accuracy is calculated from listener performance in the last 3 blocks of Phase 1
export const ACCURACY_CHECK_BLOCKS = 3; // Check last 3 blocks of Phase 1
export const ACCURACY_THRESHOLD = 2 / 3; // Players must achieve >= 66.7% accuracy
export const PLAYER_ACCURACY_THRESHOLD = 2 / 3; // >= 2/3 of group members must meet threshold

// ============ DERIVED VALUES ============
// Total blocks
export const TOTAL_BLOCKS = PHASE_1_BLOCKS + PHASE_2_BLOCKS;

// Rounds per block (one per tangram)
export const ROUNDS_PER_BLOCK = NUM_TANGRAMS;

// Total rounds
export const TOTAL_ROUNDS = TOTAL_BLOCKS * ROUNDS_PER_BLOCK;

// How many times each player is speaker in Phase 1
export const SPEAKER_TIMES_PHASE_1 = PHASE_1_BLOCKS / GROUP_SIZE;

// Maximum bonus displayed to participants (approximate, same across all conditions)
export const MAX_BONUS = 8;

// Estimated time in minutes
export const ESTIMATED_TIME = "45-60";

// Log warning if in test mode (only runs on server)
if (typeof window === "undefined" && TEST_MODE) {
  console.warn("⚠️  RUNNING IN TEST MODE");
}
