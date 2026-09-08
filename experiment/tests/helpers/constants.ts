// Mirror of experiment/shared/constants.js for test usage
// Keep in sync with the source file
// Default: TEST_MODE=true (test timing). Run with TEST_MODE=false for production timing.
// The server gets the same value via env var in server-manager.ts.

export const TEST_MODE = process.env.TEST_MODE !== 'false';

// Fast timing for idle-heavy suites; must mirror shared/constants.js
export const IDLE_TEST_TIMING = process.env.IDLE_TEST_TIMING === 'true';

// Timing
export const SELECTION_DURATION = IDLE_TEST_TIMING ? 30 : TEST_MODE ? 120 : 45;
export const PHASE2_SELECTION_DURATION = IDLE_TEST_TIMING ? 30 : TEST_MODE ? 120 : 25;
export const FEEDBACK_DURATION = 15;
export const TRANSITION_DURATION = 60;
export const BONUS_INFO_DURATION = 30;

// Players
export const GROUP_SIZE = 3;
export const LISTENERS_PER_TRIAL = 2;
export const PLAYER_COUNT = 9;

// Phases
export const PHASE_1_BLOCKS = TEST_MODE ? 3 : 6;
export const PHASE_2_BLOCKS = TEST_MODE ? 2 : 6;
export const NUM_TANGRAMS = 6;
export const NUM_DISPLAY_TANGRAMS = 16;
export const ROUNDS_PER_BLOCK = NUM_TANGRAMS;
export const TOTAL_BLOCKS = PHASE_1_BLOCKS + PHASE_2_BLOCKS;
export const TOTAL_ROUNDS = TOTAL_BLOCKS * ROUNDS_PER_BLOCK;
export const PHASE_1_ROUNDS = PHASE_1_BLOCKS * ROUNDS_PER_BLOCK;
export const PHASE_2_ROUNDS = PHASE_2_BLOCKS * ROUNDS_PER_BLOCK;

// Dropout
export const MAX_IDLE_ROUNDS = IDLE_TEST_TIMING ? 2 : TEST_MODE ? 5 : 3;
export const MIN_GROUP_SIZE = 2;

// Scoring
export const LISTENER_CORRECT_POINTS = 2;
export const SPEAKER_MAX_POINTS_PER_ROUND = 2;
export const SOCIAL_GUESS_CORRECT_POINTS = 6;
export const SOCIAL_SPEAKER_POINTS_PER_CORRECT = 6;
export const BONUS_PER_POINT = 0.0556;
export const BONUS_PER_POINT_SOCIAL = 0.023;

// Compensation
export const BASE_PAY = 12;
export const LOBBY_TIMEOUT_PAY = 2;
export const MAX_BONUS = 8;

// Accuracy threshold
export const ACCURACY_CHECK_BLOCKS = 3;
export const ACCURACY_THRESHOLD = 2 / 3;
export const PLAYER_ACCURACY_THRESHOLD = 2 / 3;

// Player names
export const PLAYER_NAMES = [
  'Repi', 'Minu', 'Laju', 'Hera', 'Zuda', 'Bavi', 'Lika', 'Felu', 'Nori',
];

// Conditions
export const CONDITIONS = [
  'refer_separated', 'refer_mixed', 'social_mixed', 'social_first',
] as const;
export type Condition = typeof CONDITIONS[number];

// Quiz answers (correct values matching Quiz.jsx)
export const QUIZ_ANSWERS = {
  speakerJob: 'To describe the target picture so Listeners can identify it.',
  inactivePenalty: 'You will be removed from the game and lose your bonus.',
  chatRestrictions: 'Only topics related to picking out the correct target picture.',
  listenerWaiting: 'Listeners must wait for the Speaker to send a message before they can click.',
  picturePositions: 'Everyone will see the same pictures, but the pictures will be mixed up and in different places for different people.',
  positionReason: 'Because the pictures are in different positions for each player.',
  phase2SocialFirst: "Players from all groups will be mixed together, and listeners will need to use speakers' descriptions to figure out whether they were in the same Phase 1 group.",
};

// Prolific codes
export const PROLIFIC_CODES = {
  completion: 'C2I8XDMC',
  quizFail: 'QUIZFAIL2026',
  lobbyTimeout: 'CMZUY3MK',
  disbanded: 'CFTYDMIY',
};

// Treatments as shown in admin dropdown
export const TREATMENTS = {
  refer_separated: 'Refer Separated (9 players)',
  refer_mixed: 'Refer Mixed (9 players)',
  social_mixed: 'Social Mixed (9 players)',
  social_first: 'Social First (9 players)',
  // Tangram set 1 variants (set 0 is the default for the names above)
  refer_separated_set1: 'Refer Separated (9 players, tangram set 1)',
  refer_mixed_set1: 'Refer Mixed (9 players, tangram set 1)',
  social_mixed_set1: 'Social Mixed (9 players, tangram set 1)',
  social_first_set1: 'Social First (9 players, tangram set 1)',
};
export type TreatmentKey = keyof typeof TREATMENTS;

// Group names
export const GROUP_NAMES = ['A', 'B', 'C'];
