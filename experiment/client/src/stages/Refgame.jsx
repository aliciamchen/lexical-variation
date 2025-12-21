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
  const condition = game.get("condition");
  const phase_num = round.get("phase_num");
  const block_num = round.get("block_num");

  // Determine if social guessing is enabled
  const isSocialMixed = condition === "social_mixed" && phase_num === 2;
  const isListener = player.round.get("role") === "listener";

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
    // In mixed conditions during Phase 2, use display_name and display_avatar
    const isMixed = (condition === "refer_mixed" || condition === "social_mixed") && phase_num === 2;
    const displayName = isMixed ? p.round.get("display_name") : p.get("name");
    const displayAvatar = isMixed ? p.round.get("display_avatar") : p.get("avatar");

    return (
      <div className="player" key={p.id}>
        <span className="image">
          {displayAvatar && <img src={displayAvatar} alt="Player avatar" />}
        </span>
        <span className="name" style={{ color: "#374151" }}>
          {displayName || `Player ${p.index}`}
          {self
            ? " (You)"
            : p.round.get("role") === "listener"
            ? " (Listener)"
            : " (Speaker)"}
        </span>
      </div>
    );
  };

  // Use current_group for player grouping
  const playerGroup = player.get("current_group");
  const playersInGroup = players.filter((p) => p.get("current_group") === playerGroup && p.get("is_active"));
  const otherPlayers = playersInGroup.filter((p) => p.id !== player.id);

  // Get total blocks from game (set based on TEST_MODE)
  const phase1Blocks = game.get("phase1Blocks") || 6;
  const phase2Blocks = game.get("phase2Blocks") || 12;
  const totalBlocks = phase_num === 1 ? phase1Blocks : phase2Blocks;
  const displayBlockNum = block_num + 1;

  let waitingMessage = "";
  if (stage.get("name") == "Selection") {
    // For social_mixed, listeners need both tangram click AND social guess
    const hasClicked = player.round.get("clicked");
    const hasSocialGuess = player.round.get("social_guess");
    const playerResponded = player.round.get("role") === "speaker" ||
      (hasClicked && (!isSocialMixed || hasSocialGuess));

    if (playerResponded) {
      // Check if all players in the same group have responded
      const allGroupResponded = playersInGroup.every((p) => {
        if (p.round.get("role") === "speaker") return true;
        const pClicked = p.round.get("clicked");
        const pSocialGuess = p.round.get("social_guess");
        return pClicked && (!isSocialMixed || pSocialGuess);
      });

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
        feedback = "Correct! You earned 2 points for the tangram.";
        // Add social guess feedback if applicable
        if (isSocialMixed) {
          const socialCorrect = player.round.get("social_guess_correct");
          if (socialCorrect) {
            feedback += " You also correctly guessed the speaker's group (+2 points).";
          } else if (player.round.get("social_guess")) {
            feedback += " Your guess about the speaker's group was incorrect.";
          }
        }
      } else {
        feedback = "Ooops, that wasn't the target! You earned no tangram bonus this round.";
        // Add social guess feedback if applicable
        if (isSocialMixed) {
          const socialCorrect = player.round.get("social_guess_correct");
          if (socialCorrect) {
            feedback += " But you correctly guessed the speaker's group (+2 points).";
          } else if (player.round.get("social_guess")) {
            feedback += " Your guess about the speaker's group was also incorrect.";
          }
        }
      }
    }
    if (player.round.get("role") == "speaker") {
      const roundScore = player.round.get("round_score") || 0;
      const socialRoundScore = player.round.get("social_round_score") || 0;
      const totalScore = roundScore + socialRoundScore;

      feedback = `You earned ${totalScore} ${totalScore == 1 ? `point` : `points`} this round.`;
      if (isSocialMixed && socialRoundScore > 0) {
        feedback += ` (${roundScore} from tangrams, ${socialRoundScore} from social guessing)`;
      }
    }
  }

  if (hasSubmitted && stage.get("name") == "Feedback") {
    return (
      <div className="text-center text-gray-400 pointer-events-none">
        Please wait for other player(s).
      </div>
    );
  }

  // Social guess component for listeners in social_mixed condition
  const renderSocialGuess = () => {
    if (!isSocialMixed || !isListener || stage.get("name") !== "Selection") {
      return null;
    }

    const hasClicked = player.round.get("clicked");
    const hasSocialGuess = player.round.get("social_guess");

    // Only show after tangram is clicked
    if (!hasClicked) {
      return null;
    }

    if (hasSocialGuess) {
      return (
        <div className="social-guess-container" style={{
          marginTop: 16,
          padding: 16,
          backgroundColor: "#f0f9ff",
          borderRadius: 8,
          textAlign: "center"
        }}>
          <p style={{ color: "#666" }}>
            You guessed: <strong>{hasSocialGuess === "same_group" ? "Same group" : "Different group"}</strong>
          </p>
        </div>
      );
    }

    return (
      <div className="social-guess-container" style={{
        marginTop: 16,
        padding: 16,
        backgroundColor: "#fff7ed",
        borderRadius: 8,
        border: "2px solid #f97316"
      }}>
        <p style={{ textAlign: "center", marginBottom: 12, fontWeight: "bold" }}>
          Was the speaker in your original group (from Phase 1)?
        </p>
        <div style={{ display: "flex", gap: "1rem", justifyContent: "center" }}>
          <button
            className="button"
            onClick={() => player.round.set("social_guess", "same_group")}
            style={{
              padding: "8px 16px",
              backgroundColor: "#22c55e",
              color: "white",
              border: "none",
              borderRadius: 4,
              cursor: "pointer"
            }}
          >
            Yes, same group
          </button>
          <button
            className="button"
            onClick={() => player.round.set("social_guess", "different_group")}
            style={{
              padding: "8px 16px",
              backgroundColor: "#ef4444",
              color: "white",
              border: "none",
              borderRadius: 4,
              cursor: "pointer"
            }}
          >
            No, different group
          </button>
        </div>
        <p style={{ textAlign: "center", marginTop: 8, fontSize: "0.85rem", color: "#666" }}>
          You earn 2 points for a correct guess.
        </p>
      </div>
    );
  };

  return (
    <div className="task">
      <div className="status">
        <div className="players card">
          <h3 style={{ textAlign: "center", marginBottom: "10px" }}>
            Your Group | Phase {phase_num} - Block {displayBlockNum} of {totalBlocks}
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
              : "You are a listener. Please click on the image that the speaker describes." +
                (isSocialMixed ? " Then guess whether the speaker was in your original group." : "")}
          </p>
        </div>

        <div className="all-tangrams">
          <div className="tangrams grid">{tangramsToRender}</div>
        </div>

        {renderSocialGuess()}

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
