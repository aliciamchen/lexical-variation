// ============ TEST MODE ============
// Set to true for local testing with fewer players
export const TEST_MODE = true;

// ============ TANGRAM SETS ============
// Using Ji et al. (2022) tangrams - single set of 6
export const tangram_sets = {
  0: ["page1-129", "page3-121", "page3-182", "page4-157", "page6-149", "page7-81"],
};

// ============ PLAYER CONFIGURATION ============
// Production: 9 players, 3 groups of 3
// Test mode: 3 players, 1 group of 3
export const PLAYER_COUNT = TEST_MODE ? 3 : 9;
export const GROUP_COUNT = TEST_MODE ? 1 : 3;
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
export const MAX_IDLE_ROUNDS = 2; // Remove player after 2 consecutive idle rounds
export const MIN_GROUP_SIZE = 2; // Minimum players needed to continue in a group
export const MIN_ACTIVE_GROUPS = TEST_MODE ? 1 : 2; // Minimum groups needed to continue the game

// Log warning if in test mode
if (TEST_MODE) {
  console.warn("⚠️  RUNNING IN TEST MODE - Reduced players and blocks for testing");
}
