// Centralized DOM selectors for the experiment UI

// Game container (Game.jsx)
export const GAME_CONTAINER = '[data-testid="game-container"]';
export const GAME_PHASE = '[data-game-phase]';
export const GAME_BLOCK = '[data-game-block]';
export const GAME_ROUND = '[data-game-round]';
export const STAGE_NAME = '[data-stage-name]';
export const CONDITION = '[data-condition]';
export const PLAYER_GROUP = '[data-player-group]';

// Profile (Profile.jsx)
export const PLAYER_NAME_ATTR = '[data-player-name]';
export const PLAYER_GROUP_ATTR = '[data-player-group]';

// Task / Refgame (Refgame.jsx)
export const TASK = '.task';
export const TARGET_INDEX = '[data-target-index]';
export const ROLE = '[data-role]';
export const CURRENT_GROUP = '[data-current-group]';
export const TANGRAM_GRID = '.tangrams.grid';
export const TANGRAM_ITEMS = '.tangrams.grid > div';

// Chat
export const CHAT_INPUT = 'textarea';
export const CHAT_MESSAGES = '.chat-messages';

// Exit screens (Sorry.jsx, Quiz.jsx, ExitSurvey.jsx)
export const SORRY_SCREEN = '[data-testid="sorry-screen"]';
export const QUIZ_FAILED_SCREEN = '[data-testid="quiz-failed-screen"]';
export const EXIT_SURVEY = '[data-testid="exit-survey"]';
export const EXIT_REASON = '[data-exit-reason]';
export const PROLIFIC_CODE = '[data-prolific-code]';
export const PARTIAL_PAY = '[data-partial-pay]';
export const PLAYER_ID = '[data-player-id]';

// Social guess (Refgame.jsx)
export const SOCIAL_GUESS_CONTAINER = '.social-guess-container';

// Feedback
export const FEEDBACK_INDICATOR = '.feedbackIndicator';

// Player status
export const PLAYER_GROUP_DISPLAY = '.player-group';

// Buttons (role-based selectors)
export const BUTTON = {
  enter: { role: 'button' as const, name: /enter/i },
  consent: { role: 'button' as const, name: /consent/i },
  next: { role: 'button' as const, name: /next/i },
  submit: { role: 'button' as const, name: /submit/i },
  continue: { role: 'button' as const, name: /continue/i },
  sameGroup: { role: 'button' as const, name: /yes, same group/i },
  differentGroup: { role: 'button' as const, name: /no, different group/i },
  newParticipant: { role: 'button' as const, name: /new participant/i },
};

// Radio buttons for quiz (Quiz.jsx)
export const QUIZ_RADIOS = {
  speakerJob: { role: 'radio' as const, name: /describe the target picture/i },
  inactivePenalty: { role: 'radio' as const, name: /removed from the game/i },
  chatRestrictions: { role: 'radio' as const, name: /only descriptions of the current/i },
  listenerWaiting: { role: 'radio' as const, name: /listeners must wait/i },
  picturePositions: { role: 'radio' as const, name: /mixed up/i },
  positionReason: { role: 'radio' as const, name: /different positions for each player/i },
};

// Chat textbox
export const CHAT_TEXTBOX = { role: 'textbox' as const, name: 'Say something' };
