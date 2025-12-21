import React from "react";
import { Button } from "../components/Button";

export function Transition(props) {
  const { round, stage, game, player, players } = props;
  const condition = game.get("condition");

  if (player.stage.get("submit")) {
    return (
      <div className="text-center text-gray-400 pointer-events-none">
        Please wait for other player(s).
      </div>
    );
  }

  if (stage.get("name") === "phase_2_transition") {
    // Get condition-specific instructions
    let conditionInstructions = "";

    if (condition === "refer_separated") {
      conditionInstructions = (
        <p className="instruction-prompt" style={{ marginTop: 8 }}>
          [Placeholder: You will continue playing the reference game with the same group members you played with in Phase 1. Your goal remains the same: describe tangrams to help your listeners identify them correctly.]
        </p>
      );
    } else if (condition === "refer_mixed") {
      conditionInstructions = (
        <p className="instruction-prompt" style={{ marginTop: 8 }}>
          [Placeholder: In this phase, the groups will be shuffled. You will be randomly assigned to new groups each block, and player identities will be masked. You won't know who your current group members are. Your goal remains the same: describe tangrams to help your listeners identify them correctly.]
        </p>
      );
    } else if (condition === "social_mixed") {
      conditionInstructions = (
        <p className="instruction-prompt" style={{ marginTop: 8 }}>
          [Placeholder: In this phase, the groups will be shuffled. You will be randomly assigned to new groups each block, and player identities will be masked. You won't know who your current group members are. In addition to selecting the correct tangram, listeners will also guess whether the speaker was in their original group from Phase 1. You earn bonus points for correct social guesses.]
        </p>
      );
    }

    return (
      <div className="prompt-container" style={{ textAlign: "left" }}>
        <div className="text-2xl">
          <em>End of Phase 1</em>
        </div>
        <p className="instruction-prompt" style={{ marginTop: 8 }}>
          Great job completing Phase 1! You will now continue to Phase 2.
        </p>
        {conditionInstructions}
        <p className="instruction-prompt" style={{ marginTop: 8 }}>
          Phase 2 consists of 12 blocks. Each block has 6 trials, just like in Phase 1.
        </p>
        <p className="instruction-prompt" style={{ marginTop: 8 }}>
          Scoring:
          <ul style={{ marginTop: 4, marginLeft: 20 }}>
            <li>Listeners earn <strong>2 points</strong> for correctly identifying the target tangram.</li>
            <li>Speakers earn <strong>1 point</strong> for each listener who correctly identifies the target.</li>
            {condition === "social_mixed" && (
              <>
                <li>Listeners earn <strong>2 bonus points</strong> for correctly guessing whether the speaker was in their original group.</li>
                <li>Speakers earn <strong>1 bonus point</strong> for each listener who correctly guesses their group membership.</li>
              </>
            )}
          </ul>
        </p>
        <div
          style={{
            marginTop: "1rem",
          }}
        >
          <Button handleClick={() => player.stage.set("submit", true)}>
            Continue
          </Button>
        </div>
      </div>
    );
  }

  if (stage.get("name") === "bonus_info") {
    const score = player.get("score") || 0;
    const bonus = player.get("bonus") || 0;

    return (
      <div className="prompt-container" style={{ textAlign: "left" }}>
        <div className="text-2xl">
          <em>End of Game</em>
        </div>
        <p className="instruction-prompt" style={{ marginTop: 8 }}>
          You have completed the game. Congrats!
        </p>
        <p className="instruction-prompt" style={{ marginTop: 8 }}>
          You earned <strong>{score} points</strong> in total, for
          a bonus of <strong>${bonus.toFixed(2)}</strong>.
        </p>
        <p className="instruction-prompt" style={{ marginTop: 8 }}>
          Please press "Continue" to proceed to the post-game survey.
        </p>
        <div
          style={{
            marginTop: "1rem",
          }}
        >
          <Button handleClick={() => player.stage.set("submit", true)}>
            Continue
          </Button>
        </div>
      </div>
    );
  }

  return "Not implemented yet";
}
