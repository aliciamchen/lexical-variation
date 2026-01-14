// ============ SHARED CONSTANTS ============
// Import from here in both client/src and server/src.

// ============ TEST MODE ============
// Set to true for local testing (longer timeouts, more idle tolerance)
export const TEST_MODE = true; // Set to false for production

// ============ TESTING VS PRODUCTION VALUES ============
// TEST_MODE only affects timing and tolerance settings, not player/group counts.
// Player count is set in treatments.yaml and group count is derived from player count.
//
// | Setting              | Testing | Production | Description                          |
// |----------------------|---------|------------|--------------------------------------|
// | TEST_MODE            | true    | false      | Master toggle                        |
// | SELECTION_DURATION   | 120     | 45         | Seconds for selection stage          |
// | MAX_IDLE_ROUNDS      | 5       | 2          | Rounds before idle kick              |
// | PHASE_1_BLOCKS       | 2       | 6          | Blocks in Phase 1                    |
// | PHASE_2_BLOCKS       | 2       | 6          | Blocks in Phase 2                    |

// ============ TIMING CONFIGURATION ============
// Stage durations in seconds
export const SELECTION_DURATION = TEST_MODE ? 120 : 45;  // Selection stage (TEST: 120s)
export const FEEDBACK_DURATION = 10;                      // Feedback stage (same for both)
export const TRANSITION_DURATION = 60;                    // Phase transition (same for both)
export const BONUS_INFO_DURATION = 30;                    // End game bonus info (same for both)

// ============ TANGRAM SETS ============
// Using Ji et al. (2022) tangrams - two sets of 6 with high SND (Shape Naming Divergence)
// Set 0: Original selection (SND range: 0.960-0.987)
// Set 1: Next highest SND tangrams (SND range: 0.978-0.987)
export const tangram_sets = {
  0: ["page1-129", "page3-121", "page3-182", "page4-157", "page6-149", "page7-81"],
  1: ["page3-85", "page3-136", "page5-64", "page9-46", "page9-27", "page1-128"],
};

// ============ PLAYER CONFIGURATION ============
// Player count is set in treatments.yaml (playerCount field)
// Group count is derived dynamically in callbacks.js from actual player count
export const GROUP_SIZE = 3;
export const LISTENERS_PER_TRIAL = 2;

// ============ PHASE CONFIGURATION ============
// Phase 1: Within-group reference game
// Phase 2: Continued reference game (condition-dependent)
export const PHASE_1_BLOCKS = TEST_MODE ? 3 : 6; // Each player speaks twice in production (3 for test to match ACCURACY_CHECK_BLOCKS)
export const PHASE_2_BLOCKS = TEST_MODE ? 2 : 6;

// ============ GAME STRUCTURE ============
export const NUM_TANGRAMS = 6;

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
export const conditions = ["refer_separated", "refer_mixed", "social_mixed"];

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

// Generate DiceBear identicon URL (consistent blue color scheme)
export const getAvatarUrl = (seed) =>
  `https://api.dicebear.com/9.x/identicon/svg?seed=${seed}&backgroundColor=e0f2fe&rowColor=0369a1`;

// Generate anonymous avatar URL (shapes style, grayscale)
export const getAnonymousAvatarUrl = (seed) =>
  `https://api.dicebear.com/9.x/shapes/svg?seed=${seed}&backgroundColor=e5e7eb&shape1Color=9ca3af&shape2Color=6b7280&shape3Color=4b5563`;

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
export const BONUS_PER_POINT = 0.05;
export const bonus_per_point = BONUS_PER_POINT; // Alias for server compatibility
export const LISTENER_CORRECT_POINTS = 2;
// Speaker scoring: 2 * (proportion of correct listeners) - max 2 points per round
export const SPEAKER_MAX_POINTS_PER_ROUND = 2;
export const SOCIAL_GUESS_CORRECT_POINTS = 2;
// Speaker bonus: points for each original-group listener who correctly identifies them
export const SOCIAL_SPEAKER_POINTS_PER_CORRECT = 2;
// Social condition has more scoring opportunities, so lower multiplier to keep max bonus similar
export const BONUS_PER_POINT_SOCIAL = 0.04;

// ============ COMPENSATION ============
export const BASE_PAY = 12; // dollars
export const LOBBY_TIMEOUT_PAY = 2; // dollars for players who couldn't find a match in lobby

// Expected game duration in minutes (used for proportional compensation)
export const EXPECTED_GAME_DURATION_MIN = 35; // midpoint of 30-45 minute estimate

// ============ DROPOUT HANDLING ============
export const MAX_IDLE_ROUNDS = TEST_MODE ? 5 : 2; // TEST: 5 rounds tolerance
export const MIN_GROUP_SIZE = 2; // Minimum players needed to continue in a group
// MIN_ACTIVE_GROUPS is derived dynamically in callbacks.js based on actual group count

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
export const ESTIMATED_TIME = 60;

// Log warning if in test mode (only runs on server)
if (typeof window === 'undefined' && TEST_MODE) {
  console.warn("⚠️  RUNNING IN TEST MODE");
}
