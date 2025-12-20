import React, { useState, useEffect } from "react";
import { Tangram } from "../components/Tangram.jsx";
import { Button } from "../components/Button.jsx";

export function Refgame(props) {
  const { round, stage, game, player, players } = props;
  const [hasSubmitted, setHasSubmitted] = useState(false);

  // Reset the local submission state when stage changes
  useEffect(() => {
    if (stage.get("name") === "Feedback") {
      setHasSubmitted(false);
    }
  }, [stage.get("name")]);

  const target = round.get("target");
  const shuffled_tangrams = player.get("shuffled_tangrams");
  const correct = player.round.get("clicked") == target;
  let tangramsToRender;
  if (shuffled_tangrams) {
    tangramsToRender = shuffled_tangrams.map((tangram, i) => (
      <Tangram
        key={tangram}
        tangram={tangram}
        tangram_num={i}
        round={round}
        stage={stage}
        game={game}
        player={player}
        players={players}
        target={target}
      />
    ));
  }

  // Render player status indicator
  const renderPlayer = (p, self = false) => {
    return (
      <div className="player" key={p.id}>
        <span className="image">
          {p.get("avatar") && <img src={p.get("avatar")} alt="Player avatar" />}
        </span>
        <span className="name" style={{ color: p.get("name_color") || "#000" }}>
          {p.get("name") || `Player ${p.index}`}
          {self
            ? " (You)"
            : p.round.get("role") === "listener"
            ? " (Listener)"
            : " (Speaker)"}
        </span>
      </div>
    );
  };

  const playerGroup = player.get("group");
  const playersInGroup = players.filter((p) => p.get("group") === playerGroup);
  const otherPlayers = playersInGroup.filter((p) => p.id !== player.id);

  let waitingMessage = "";
  if (stage.get("name") == "Selection") {
    if (player.round.get("clicked") || player.round.get("role") === "speaker") {
      // Check if all players in the same group have responded

      const allGroupResponded = playersInGroup.every(
        (p) => p.round.get("role") === "speaker" || p.round.get("clicked")
      );

      if (allGroupResponded) {
        waitingMessage =
          "All players in group responded! Waiting for members of other groups to respond...";
      } else {
        waitingMessage = "Waiting for the players in your group to respond...";
      }
    }
  }

  let feedback = "";
  if (stage.get("name") == "Feedback") {
    if (player.round.get("role") == "listener") {
      // if player did not respond in time
      if (!player.round.get("clicked")) {
        feedback =
          "You did not respond in time. You earned no bonus this round.";
      } else if (correct) {
        feedback = "Correct! You earned three points.";
      } else {
        feedback =
          "Ooops, that wasn't the target! You earned no bonus this round.";
      }
    }
    if (player.round.get("role") == "speaker") {
      feedback = `You earned ${player.round.get("round_score")} ${
        player.round.get("round_score") == 1 ? `point` : `points`
      } this round.`;
    }
  }

  if (hasSubmitted && stage.get("name") == "Feedback") {
    return (
      <div className="text-center text-gray-400 pointer-events-none">
        Please wait for other player(s).
      </div>
    );
  }

  return (
    <div className="task">
      <div className="status">
        <div className="players card">
          <h3 style={{ textAlign: "center", marginBottom: "10px" }}>
            Your Group | Round {round.get("rep_num") + 1} of 8
          </h3>
          <div
            className="player-group"
            style={{
              display: "flex",
              justifyContent: "center",
              alignItems: "center",
              flexWrap: "wrap",
            }}
          >
            {renderPlayer(player, true)}
            {otherPlayers.map((p) => renderPlayer(p))}
          </div>
        </div>
      </div>
      <div className="board">
        <div className="prompt-container">
          <p className="instruction-prompt">
            {" "}
            {player.round.get("role") == "speaker"
              ? "You are the speaker. Please describe the picture in the box to the other players."
              : "You are a listener. Please click on the image that the speaker describes."}
          </p>
        </div>

        <div className="all-tangrams">
          <div className="tangrams grid">{tangramsToRender}</div>
        </div>

        {waitingMessage && (
          <h3
            style={{
              marginTop: 5,
              marginBottom: "auto",
              textAlign: "center",
              color: "#666",
              width: "100%",
            }}
          >
            {waitingMessage}
          </h3>
        )}

        {feedback && (
          <h3
            className="feedbackIndicator"
            style={{
              marginTop: 5,
              marginBottom: "auto",
              textAlign: "center",
              fontWeight: "bold",
              width: "100%",
            }}
          >
            <>{feedback}</>
          </h3>
        )}

        {stage.get("name") == "Feedback" && (
          <div
            style={{
              display: "flex",
              justifyContent: "center",
              marginTop: "1rem",
            }}
          >
            <Button
              handleClick={() => {
                player.stage.set("submit", true);
                setHasSubmitted(true);
              }}
            >
              Continue
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
