// Re-export all constants from shared
// This keeps import paths short: import { X } from "../constants.js"
export * from "../../shared/constants.js";

import { EXIT_REASONS } from "../../shared/constants.js";

// Exit reasons whose players were removed through no fault of their own and
// are paid base prorated to time spent plus the bonus earned so far. They
// answer the exit survey first (App.jsx routes them to [ExitSurvey, Sorry])
// and then get the partial completion code on the Sorry page. Idle removals
// (`playerTimeout`) skip the survey and forfeit the bonus; quiz failures get
// no pay.
export const PARTIAL_PAY_SURVEY_REASONS = [
  EXIT_REASONS.groupDisbanded,
  EXIT_REASONS.insufficientGroups,
  EXIT_REASONS.lowAccuracy,
  EXIT_REASONS.insufficientGroupsAccuracy,
  EXIT_REASONS.gameTerminated,
];
