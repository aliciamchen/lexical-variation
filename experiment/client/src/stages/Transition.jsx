import React from "react";
import { Button } from "../components/Button";

export function Transition(props) {
  const { round, stage, game, player, players } = props;
  if (player.stage.get("submit")) {
    return (
      <div className="text-center text-gray-400 pointer-events-none">
        Please wait for other player(s).
      </div>
    );
  }

  if (stage.get("name") === "phase_2_transition") {
    return (
      <div className="prompt-container" style={{ textAlign: "left" }}>
        <div className="text-2xl">
          <em>End of Phase 1</em>
        </div>
        <p className="instruction-prompt" style={{ marginTop: 8 }}>
          In Phase 2, you will be shown a target picture on each trial, and
          asked to generate a description for the picture. We will tell you{" "}
          <strong>who</strong> will see your description (a member of your
          group, or a member of another group) and{" "}
          <strong>what question</strong> they will be answering when they see it
          (select the correct picture, or identify whether you are a member of
          their group). Your goal is to try to get them to answer the question
          in a certain way based on your description of the picture.
        </p>
        <p className="instruction-prompt" style={{ marginTop: 8 }}>
          Then, in Phase 3, we will deliver your descriptions to the other
          players, and ask them to answer the questions based on your
          descriptions. You will receive <strong>three points</strong> for each correct guess.
        </p>
        <p className="instruction-prompt" style={{ marginTop: 8 }}>
          ⚠️ Please ensure that your description is of the highlighted picture.
          Any other kinds of messages (e.g. identifying information about your
          group, such as the names of the players in your group) will be
          considered invalid and you will not receive any points for that trial.
          ⚠️{" "}
        </p>
        <p className="instruction-prompt" style={{ marginTop: 8 }}>
          You have 30 seconds to submit your description on each trial. If you
          do not submit a description within 30 seconds, neither you nor the
          listener will receive any points for that trial.
        </p>
        <p className="instruction-prompt" style={{ marginTop: 8 }}>
          There will be 18 trials in this phase. We will tell you how many
          points you have earned at the end of the game.
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

  if (stage.get("name") === "phase_3_transition") {
    return (
      <div className="prompt-container" style={{ textAlign: "left" }}>
        <div className="text-2xl">
          <em>End of Phase 2</em>
        </div>
        <p className="instruction-prompt" style={{ marginTop: 8 }}>
          In the next phase, you will be shown descriptions that other players
          produced in the previous phase. You will be asked to guess (1) which
          picture they were describing, and (2) whether they were a member of
          your group. You will receive <strong>three points</strong> for each
          correct guess, for a total of <strong>six possible points</strong> per
          trial.
        </p>
        <p className="instruction-prompt" style={{ marginTop: 8 }}>
          There will be 36 trials in this phase. Unlike in the first phase, you
          will not receive feedback at the end of each trial. We will tell you
          how many points you have earned at the end of the phase.
        </p>
        <p className="instruction-prompt" style={{ marginTop: 8 }}>
          You have 30 seconds to make your guess for each trial. If you do not
          submit a guess within 30 seconds, you will not receive any points for
          that trial.
        </p>
        <p className="instruction-prompt" style={{ marginTop: 8 }}>
          This is the last phase of the game. Stay focused; you're almost at the
          end! 😁
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
    return (
      <div className="prompt-container" style={{ textAlign: "left" }}>
        <div className="text-2xl">
          <em>End of Phase 3</em>
        </div>
        <p className="instruction-prompt" style={{ marginTop: 8 }}>
          You have completed the game. Congrats!
        </p>
        <p className="instruction-prompt" style={{ marginTop: 8 }}>
          You earned <strong>{player.get("phase3score")} points</strong> in the
          last two phases of the task.
        </p>
        <p className="instruction-prompt" style={{ marginTop: 8 }}>
          You earned <strong>{player.get("score")} points</strong> in total, for
          a bonus of <strong>${player.get("bonus").toFixed(2)}</strong>.
        </p>
        <p className="instruction-prompt" style={{ marginTop: 8 }}>
          Please press "continue" to proceed to the post-game survey.
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
