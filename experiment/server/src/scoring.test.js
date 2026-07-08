// Unit tests for the REAL production scoring logic (imported from scoring.js,
// not a copy). Uses minimal mocks of Empirica's game/stage/player objects:
// only get/set attribute maps are needed.
import { beforeEach, describe, expect, it, vi } from "vitest";
import { scoreSelectionStage } from "./scoring";
import {
  LISTENER_CORRECT_POINTS,
  SPEAKER_MAX_POINTS_PER_ROUND,
  SOCIAL_GUESS_CORRECT_POINTS,
  SOCIAL_SPEAKER_POINTS_PER_CORRECT,
} from "./constants";

class Attrs {
  constructor(init = {}) {
    this.map = new Map(Object.entries(init));
  }
  get(key) {
    return this.map.get(key);
  }
  set(key, value) {
    this.map.set(key, value);
  }
}

function makePlayer({
  id,
  group = "A",
  originalGroup = "A",
  role,
  clicked = null,
  socialGuess = null,
  score = 0,
  isActive = true,
}) {
  const player = new Attrs({
    is_active: isActive,
    current_group: group,
    original_group: originalGroup,
    score,
  });
  player.id = id;
  player.round = new Attrs({
    role,
    clicked,
    social_guess: socialGuess,
  });
  return player;
}

function makeStage({ target = "T1", phaseNum = 1, blockNum = 0, chats = {} }) {
  const stage = new Attrs();
  for (const [group, chat] of Object.entries(chats)) {
    stage.set(`${group}_chat`, chat);
  }
  stage.round = new Attrs({
    target,
    phase_num: phaseNum,
    block_num: blockNum,
  });
  return stage;
}

function makeGame({
  players,
  condition = "refer_separated",
  activeGroups = ["A"],
}) {
  const game = new Attrs({
    condition,
    active_groups: activeGroups,
  });
  game.players = players;
  return game;
}

beforeEach(() => {
  vi.spyOn(console, "log").mockImplementation(() => {});
});

describe("reference-game scoring", () => {
  it("awards correct listeners the listener points and incorrect listeners zero", () => {
    const speaker = makePlayer({ id: "s", role: "speaker" });
    const right = makePlayer({ id: "l1", role: "listener", clicked: "T1" });
    const wrong = makePlayer({ id: "l2", role: "listener", clicked: "T2" });
    const game = makeGame({ players: [speaker, right, wrong] });
    const stage = makeStage({ chats: { A: [{ sender: { id: "s" } }] } });

    scoreSelectionStage(game, stage);

    expect(right.get("score")).toBe(LISTENER_CORRECT_POINTS);
    expect(right.round.get("clicked_correct")).toBe(true);
    expect(right.round.get("round_score")).toBe(LISTENER_CORRECT_POINTS);
    expect(wrong.get("score")).toBe(0);
    expect(wrong.round.get("clicked_correct")).toBe(false);
    expect(wrong.round.get("round_score")).toBe(0);
  });

  it("awards the speaker max points times the proportion of correct listeners", () => {
    const speaker = makePlayer({ id: "s", role: "speaker" });
    const right = makePlayer({ id: "l1", role: "listener", clicked: "T1" });
    const wrong = makePlayer({ id: "l2", role: "listener", clicked: "T2" });
    const game = makeGame({ players: [speaker, right, wrong] });
    const stage = makeStage({ chats: { A: [{ sender: { id: "s" } }] } });

    scoreSelectionStage(game, stage);

    expect(speaker.get("score")).toBe(SPEAKER_MAX_POINTS_PER_ROUND * (1 / 2));
    expect(speaker.round.get("round_score")).toBe(
      SPEAKER_MAX_POINTS_PER_ROUND * (1 / 2),
    );
  });

  it("awards the speaker full points when all listeners are correct", () => {
    const speaker = makePlayer({ id: "s", role: "speaker" });
    const l1 = makePlayer({ id: "l1", role: "listener", clicked: "T1" });
    const l2 = makePlayer({ id: "l2", role: "listener", clicked: "T1" });
    const game = makeGame({ players: [speaker, l1, l2] });
    const stage = makeStage({ chats: { A: [{ sender: { id: "s" } }] } });

    scoreSelectionStage(game, stage);

    expect(speaker.get("score")).toBe(SPEAKER_MAX_POINTS_PER_ROUND);
  });

  it("accumulates score across stages instead of overwriting", () => {
    const speaker = makePlayer({ id: "s", role: "speaker", score: 5 });
    const listener = makePlayer({
      id: "l1",
      role: "listener",
      clicked: "T1",
      score: 4,
    });
    const game = makeGame({ players: [speaker, listener] });
    const stage = makeStage({ chats: { A: [{ sender: { id: "s" } }] } });

    scoreSelectionStage(game, stage);

    expect(listener.get("score")).toBe(4 + LISTENER_CORRECT_POINTS);
    expect(speaker.get("score")).toBe(5 + SPEAKER_MAX_POINTS_PER_ROUND);
  });

  it("skips groups with no active speaker and leaves listeners unscored", () => {
    const listener = makePlayer({ id: "l1", role: "listener", clicked: "T1" });
    const game = makeGame({ players: [listener] });
    const stage = makeStage({});

    scoreSelectionStage(game, stage);

    expect(listener.get("score")).toBe(0);
    expect(listener.round.get("clicked_correct")).toBeUndefined();
    expect(listener.round.get("round_score")).toBeUndefined();
  });

  it("ignores inactive players entirely", () => {
    const speaker = makePlayer({ id: "s", role: "speaker" });
    const active = makePlayer({ id: "l1", role: "listener", clicked: "T1" });
    const inactive = makePlayer({
      id: "l2",
      role: "listener",
      clicked: "T1",
      isActive: false,
    });
    const game = makeGame({ players: [speaker, active, inactive] });
    const stage = makeStage({ chats: { A: [{ sender: { id: "s" } }] } });

    scoreSelectionStage(game, stage);

    expect(inactive.get("score")).toBe(0);
    expect(inactive.round.get("clicked_correct")).toBeUndefined();
    // Speaker proportion is over active listeners only
    expect(speaker.get("score")).toBe(SPEAKER_MAX_POINTS_PER_ROUND);
  });

  it("tracks phase 1 block accuracy only when the speaker sent a message", () => {
    const speaker = makePlayer({ id: "s", role: "speaker" });
    const listener = makePlayer({ id: "l1", role: "listener", clicked: "T1" });
    const game = makeGame({ players: [speaker, listener] });

    // No speaker message: no accuracy tracked
    scoreSelectionStage(game, makeStage({ blockNum: 0, chats: { A: [] } }));
    expect(listener.get("block_accuracy")).toBeUndefined();

    // Speaker message: accuracy tracked
    scoreSelectionStage(
      game,
      makeStage({ blockNum: 0, chats: { A: [{ sender: { id: "s" } }] } }),
    );
    expect(listener.get("block_accuracy")).toEqual({
      0: { correct: 1, total: 1 },
    });
  });

  it("does not track block accuracy in phase 2", () => {
    const speaker = makePlayer({ id: "s", role: "speaker" });
    const listener = makePlayer({ id: "l1", role: "listener", clicked: "T1" });
    const game = makeGame({ players: [speaker, listener] });
    const stage = makeStage({
      phaseNum: 2,
      chats: { A: [{ sender: { id: "s" } }] },
    });

    scoreSelectionStage(game, stage);

    expect(listener.get("block_accuracy")).toBeUndefined();
  });

  it("saves the group chat onto every group member's round", () => {
    const speaker = makePlayer({ id: "s", role: "speaker" });
    const listener = makePlayer({ id: "l1", role: "listener", clicked: "T1" });
    const game = makeGame({ players: [speaker, listener] });
    const chat = [{ sender: { id: "s" }, text: "the seated one" }];
    const stage = makeStage({ chats: { A: chat } });

    scoreSelectionStage(game, stage);

    expect(speaker.round.get("chat")).toEqual(chat);
    expect(listener.round.get("chat")).toEqual(chat);
  });
});

describe("social-guess scoring", () => {
  // Phase 2 mixed group: speaker from A, one in-group listener (A), one
  // out-group listener (B) — the constrained reshuffle guarantees this shape.
  function makeSocialGroup({ inGroupGuess, outGroupGuess }) {
    const speaker = makePlayer({
      id: "s",
      role: "speaker",
      originalGroup: "A",
    });
    const inGroup = makePlayer({
      id: "l-in",
      role: "listener",
      originalGroup: "A",
      clicked: "T1",
      socialGuess: inGroupGuess,
    });
    const outGroup = makePlayer({
      id: "l-out",
      role: "listener",
      originalGroup: "B",
      clicked: "T1",
      socialGuess: outGroupGuess,
    });
    const game = makeGame({
      players: [speaker, inGroup, outGroup],
      condition: "social_mixed",
    });
    const stage = makeStage({
      phaseNum: 2,
      chats: { A: [{ sender: { id: "s" } }] },
    });
    return { speaker, inGroup, outGroup, game, stage };
  }

  it("awards correct social guesses on both sides of the same/different distinction", () => {
    const { speaker, inGroup, outGroup, game, stage } = makeSocialGroup({
      inGroupGuess: "same_group", // correct: speaker IS from their group
      outGroupGuess: "different_group", // correct: speaker is NOT
    });

    scoreSelectionStage(game, stage);

    expect(inGroup.round.get("social_guess_correct")).toBe(true);
    expect(inGroup.round.get("speaker_was_same_group")).toBe(true);
    expect(inGroup.round.get("social_round_score")).toBe(
      SOCIAL_GUESS_CORRECT_POINTS,
    );
    expect(outGroup.round.get("social_guess_correct")).toBe(true);
    expect(outGroup.round.get("speaker_was_same_group")).toBe(false);

    // Both also earned listener points for the correct click
    expect(inGroup.get("score")).toBe(
      LISTENER_CORRECT_POINTS + SOCIAL_GUESS_CORRECT_POINTS,
    );

    // The one in-group listener identified the speaker: full speaker social points
    expect(speaker.round.get("social_round_score")).toBe(
      SOCIAL_SPEAKER_POINTS_PER_CORRECT,
    );
    expect(speaker.round.get("social_recognized_count")).toBe(1);
    expect(speaker.round.get("social_original_group_listeners")).toBe(1);
    expect(speaker.get("score")).toBe(
      SPEAKER_MAX_POINTS_PER_ROUND + SOCIAL_SPEAKER_POINTS_PER_CORRECT,
    );
  });

  it("awards nothing for wrong guesses and no speaker points when unrecognized", () => {
    const { speaker, inGroup, outGroup, game, stage } = makeSocialGroup({
      inGroupGuess: "different_group", // wrong
      outGroupGuess: "same_group", // wrong
    });

    scoreSelectionStage(game, stage);

    expect(inGroup.round.get("social_guess_correct")).toBe(false);
    expect(inGroup.round.get("social_round_score")).toBe(0);
    expect(outGroup.round.get("social_guess_correct")).toBe(false);
    expect(speaker.round.get("social_round_score")).toBe(0);
    expect(speaker.round.get("social_recognized_count")).toBe(0);
    expect(speaker.get("score")).toBe(SPEAKER_MAX_POINTS_PER_ROUND);
  });

  it("tracks cumulative guess counters across stages", () => {
    const first = makeSocialGroup({
      inGroupGuess: "same_group",
      outGroupGuess: "same_group",
    });
    scoreSelectionStage(first.game, first.stage);
    expect(first.inGroup.get("social_guess_total")).toBe(1);
    expect(first.inGroup.get("social_guess_correct_total")).toBe(1);
    expect(first.outGroup.get("social_guess_correct_total")).toBe(0);
    expect(first.speaker.get("social_guessed_about_total")).toBe(1);
    expect(first.speaker.get("social_guessed_about_correct")).toBe(1);
    expect(first.speaker.get("social_speaker_points_total")).toBe(
      SOCIAL_SPEAKER_POINTS_PER_CORRECT,
    );

    // Same players again in a second stage
    scoreSelectionStage(first.game, makeStage({
      phaseNum: 2,
      chats: { A: [{ sender: { id: "s" } }] },
    }));
    expect(first.inGroup.get("social_guess_total")).toBe(2);
    expect(first.speaker.get("social_guessed_about_total")).toBe(2);
  });

  it("skips listeners with no guess without crashing or counting them", () => {
    const { speaker, inGroup, game, stage } = makeSocialGroup({
      inGroupGuess: null,
      outGroupGuess: "different_group",
    });

    scoreSelectionStage(game, stage);

    expect(inGroup.round.get("social_guess_correct")).toBeUndefined();
    expect(inGroup.get("social_guess_total")).toBeUndefined();
    // In-group listener made no guess, so the speaker went unrecognized
    expect(speaker.round.get("social_round_score")).toBe(0);
  });

  it("does not run social scoring in phase 1 or in refer conditions", () => {
    const phase1 = makeSocialGroup({
      inGroupGuess: "same_group",
      outGroupGuess: "same_group",
    });
    phase1.stage.round.set("phase_num", 1);
    scoreSelectionStage(phase1.game, phase1.stage);
    expect(phase1.inGroup.round.get("social_guess_correct")).toBeUndefined();

    const refer = makeSocialGroup({
      inGroupGuess: "same_group",
      outGroupGuess: "same_group",
    });
    refer.game.set("condition", "refer_mixed");
    scoreSelectionStage(refer.game, refer.stage);
    expect(refer.inGroup.round.get("social_guess_correct")).toBeUndefined();
  });
});
