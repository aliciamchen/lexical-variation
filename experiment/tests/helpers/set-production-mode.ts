// Side-effect module: forces production mode constants.
// Import this BEFORE any other module that reads from constants.ts
// so that TEST_MODE-dependent values (SELECTION_DURATION, PHASE_1_BLOCKS, etc.)
// evaluate to their production values.
process.env.TEST_MODE = 'false';
