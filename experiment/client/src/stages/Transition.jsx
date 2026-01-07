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
          You will continue playing the reference game with the{" "}
          <strong>same group members</strong> you played with in Phase 1. Your
          goal (and the scoring) remains the same: describe the tangrams to help your listeners
          identify them correctly. Remember to limit your messages to describing
          the current target picture only.
        </p>
      );
    } else if (condition === "refer_mixed") {
      conditionInstructions = (
        <div className="instruction-prompt" style={{ marginTop: 8 }}>
          <p>
            In this phase, players from all groups will be{" "}
            <strong>mixed together</strong>. On each round, you will be randomly
            assigned to play with different players. These people may or may not
            be from your original group. Player identities will be hidden:
            Everyone will appear as "Player" with anonymous avatars.
          </p>
          <p style={{ marginTop: 8 }}>
            Your goal remains the same: describe the tangrams to help your
            listeners identify them correctly.
          </p>
        </div>
      );
    } else if (condition === "social_mixed") {
      conditionInstructions = (
        <div className="instruction-prompt" style={{ marginTop: 8 }}>
          <p>
            In this phase, players from all groups will be{" "}
            <strong>mixed together</strong>. On each round, you will be randomly
            assigned to play with different players. These people may or may not
            be from your original group. Player identities will be hidden:
            Everyone will appear as "Player" with anonymous avatars.
          </p>
          <p style={{ marginTop: 8 }}>
            <strong>New task:</strong> After clicking on a tangram, listeners
            will also guess whether the speaker was in their{" "}
            <em>original group</em> from Phase 1. Speakers and listeners will be
            rewarded for correct guesses. For these guesses, we won't tell you
            whether you were correct or not, but you will see the overall
            results at the end of the game.
          </p>
          <p style={{ marginTop: 8 }}>
            Remember to limit your messages to describing the current target
            picture only.
          </p>
        </div>
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
          Phase 2 consists of 12 blocks. Each block has 6 rounds, just like in
          Phase 1.
        </p>
        <p className="instruction-prompt" style={{ marginTop: 8 }}>
          <strong>Scoring:</strong>
          <ul style={{ marginTop: 4, marginLeft: 20 }}>
            <li>
              Listeners earn <strong>2 points</strong> for correctly identifying
              the target tangram.
            </li>
            <li>
              Speakers earn <strong>1 point</strong> for each listener who
              correctly identifies the target.
            </li>
            {condition === "social_mixed" && (
              <>
                <li>
                  Listeners earn <strong>2 bonus points</strong> for correctly
                  guessing whether the speaker was in their original group.
                </li>
                <li>
                  Speakers earn <strong>1 bonus point</strong> for each listener
                  who correctly guesses their group membership.
                </li>
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

    // Social guess summary for social_mixed condition
    const socialGuessTotal = player.get("social_guess_total") || 0;
    const socialGuessCorrect = player.get("social_guess_correct_total") || 0;
    const socialGuessedAboutTotal =
      player.get("social_guessed_about_total") || 0;
    const socialGuessedAboutCorrect =
      player.get("social_guessed_about_correct") || 0;
    const showSocialSummary =
      condition === "social_mixed" &&
      (socialGuessTotal > 0 || socialGuessedAboutTotal > 0);

    return (
      <div className="prompt-container" style={{ textAlign: "left" }}>
        <div className="text-2xl">
          <em>End of Game</em>
        </div>
        <p className="instruction-prompt" style={{ marginTop: 8 }}>
          You have completed the game. Congrats!
        </p>
        <p className="instruction-prompt" style={{ marginTop: 8 }}>
          You earned <strong>{score} points</strong> in total, for a bonus of{" "}
          <strong>${bonus.toFixed(2)}</strong>.
        </p>

        {showSocialSummary && (
          <div
            style={{
              marginTop: 16,
              padding: 16,
              backgroundColor: "#f0f9ff",
              borderRadius: 8,
            }}
          >
            <p
              className="instruction-prompt"
              style={{ fontWeight: "bold", marginBottom: 8 }}
            >
              Social Guessing Summary:
            </p>
            {socialGuessTotal > 0 && (
              <p className="instruction-prompt" style={{ marginTop: 4 }}>
                When you were a listener, you correctly guessed the speaker's
                group <strong>{socialGuessCorrect}</strong> out of{" "}
                <strong>{socialGuessTotal}</strong> times (
                {Math.round((socialGuessCorrect / socialGuessTotal) * 100)}%).
              </p>
            )}
            {socialGuessedAboutTotal > 0 && (
              <p className="instruction-prompt" style={{ marginTop: 4 }}>
                When you were a speaker, other players correctly identified your
                group <strong>{socialGuessedAboutCorrect}</strong> out of{" "}
                <strong>{socialGuessedAboutTotal}</strong> times (
                {Math.round(
                  (socialGuessedAboutCorrect / socialGuessedAboutTotal) * 100
                )}
                %).
              </p>
            )}
          </div>
        )}

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
