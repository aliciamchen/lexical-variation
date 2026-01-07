// ============ TEST MODE ============
// Set to true for local testing (longer timeouts, more idle tolerance)
// NOTE: Player count and group count are derived from the treatment, NOT from TEST_MODE
export const TEST_MODE = true; // Set to true for testing (longer timeouts)

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
export const SELECTION_DURATION = TEST_MODE ? 15 : 45;  // Selection stage (FAST TEST: 15s)
export const FEEDBACK_DURATION = 10;                      // Feedback stage (same for both)
export const TRANSITION_DURATION = 30;                    // Phase transition (same for both)
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
export const PHASE_1_BLOCKS = TEST_MODE ? 2 : 6; // Each player speaks twice in production
export const PHASE_2_BLOCKS = TEST_MODE ? 2 : 6;

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
export const bonus_per_point = 0.05; // Changed from 0.02 to 0.05
export const LISTENER_CORRECT_POINTS = 2;
export const SPEAKER_POINTS_PER_CORRECT_LISTENER = 1;
export const SOCIAL_GUESS_CORRECT_POINTS = 2;
export const SOCIAL_SPEAKER_POINTS_PER_CORRECT = 1;

// ============ DROPOUT HANDLING ============
export const MAX_IDLE_ROUNDS = TEST_MODE ? 2 : 2; // FAST TEST: 2 rounds
export const MIN_GROUP_SIZE = 2; // Minimum players needed to continue in a group
// MIN_ACTIVE_GROUPS is derived dynamically in callbacks.js based on actual group count

// Log warning if in test mode
if (TEST_MODE) {
  console.warn("⚠️  RUNNING IN TEST MODE - Longer timeouts and higher idle tolerance");
}
