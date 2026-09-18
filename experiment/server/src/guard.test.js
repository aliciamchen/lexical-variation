// Unit tests for the callback guard. Empirica does not catch what a callback
// throws, so these pin the containment: the game survives, the error is
// reported with context, and the failure is recorded on the game.
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { guard } from "./guard";

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

function makeGame({ players = [] } = {}) {
  const game = new Attrs({ condition: "social_mixed" });
  game.id = "g1";
  game.players = players;
  return game;
}

describe("guard", () => {
  let errors;

  beforeEach(() => {
    errors = [];
    vi.spyOn(console, "error").mockImplementation((...args) => errors.push(args.join(" ")));
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("passes the payload and the return value through when nothing throws", () => {
    const wrapped = guard("onRoundStart", ({ round }) => round.get("block_num") + 1);
    const round = new Attrs({ block_num: 2 });
    expect(wrapped({ round })).toBe(3);
    expect(errors).toEqual([]);
  });

  it("contains a throw instead of letting it reach Empirica", () => {
    const wrapped = guard("onStageEnded", () => {
      throw new Error("scoring blew up");
    });
    const game = makeGame();
    expect(() => wrapped({ game })).not.toThrow();
  });

  it("names the callback and the error in one greppable line", () => {
    const wrapped = guard("onStageEnded", () => {
      throw new Error("scoring blew up");
    });
    wrapped({ game: makeGame() });
    expect(errors[0]).toContain("CALLBACK ERROR in onStageEnded");
    expect(errors[0]).toContain("scoring blew up");
    expect(errors[0]).toContain("game=g1");
  });

  it("reports where in the game it happened", () => {
    const players = [new Attrs({ is_active: true }), new Attrs({ is_active: false })];
    const game = makeGame({ players });
    const round = new Attrs({ phase_num: 2, block_num: 3, target_num: 4 });
    round.currentGame = game;
    const stage = new Attrs({ name: "Selection" });
    stage.round = round;
    stage.currentGame = game;
    const wrapped = guard("onStageEnded", () => {
      throw new Error("boom");
    });
    wrapped({ stage });
    const line = errors[0];
    expect(line).toContain("condition=social_mixed");
    expect(line).toContain("active=1");
    expect(line).toContain("phase=2");
    expect(line).toContain("block=3");
    expect(line).toContain("stage=Selection");
  });

  it("records the failure on the game so it reaches the export", () => {
    const game = makeGame();
    const wrapped = guard("onRoundEnded", () => {
      throw new Error("bonus failed");
    });
    wrapped({ game });
    wrapped({ game });
    expect(game.get("callbackErrors")).toBe(2);
    expect(game.get("lastCallbackError")).toBe("onRoundEnded: bonus failed");
  });

  it("still contains the throw when there is no context to describe", () => {
    const wrapped = guard("onGameStart", () => {
      throw new Error("no payload");
    });
    expect(() => wrapped(undefined)).not.toThrow();
    expect(errors[0]).toContain("CALLBACK ERROR in onGameStart");
  });

  it("does not let a broken context reader mask the real error", () => {
    const game = makeGame();
    game.get = () => {
      throw new Error("attribute store is broken");
    };
    const wrapped = guard("onGameEnded", () => {
      throw new Error("the real problem");
    });
    expect(() => wrapped({ game })).not.toThrow();
    expect(errors[0]).toContain("the real problem");
    expect(errors[0]).toContain("context-unavailable");
  });
});
