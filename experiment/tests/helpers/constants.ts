// Test constants. Everything the game defines is re-exported from the single
// source of truth, shared/constants.js, so the tests cannot drift from the
// server and client. Only test-specific values are defined here.
import './set-default-test-mode';
export * from '../../shared/constants.js';
import {
  PHASE_1_BLOCKS,
  PHASE_2_BLOCKS,
  ROUNDS_PER_BLOCK,
} from '../../shared/constants.js';

// Players per game (set in .empirica/treatments.yaml)
export const PLAYER_COUNT = 9;

// Rounds per phase in the current mode
export const PHASE_1_ROUNDS = PHASE_1_BLOCKS * ROUNDS_PER_BLOCK;
export const PHASE_2_ROUNDS = PHASE_2_BLOCKS * ROUNDS_PER_BLOCK;

// Player display names, in the order the server assigns them
export { names as PLAYER_NAMES } from '../../shared/constants.js';

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

// Treatments as shown in the admin dropdown (.empirica/treatments.yaml)
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
