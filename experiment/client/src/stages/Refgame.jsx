import React, { useState, useEffect } from "react";
import { Tangram } from "../components/Tangram.jsx";
import { Button } from "../components/Button.jsx";
import { PHASE_1_BLOCKS, PHASE_2_BLOCKS, MAX_IDLE_ROUNDS } from "../constants";

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

  // Compute target index for testing purposes
  const targetIndex = shuffled_tangrams ? shuffled_tangrams.indexOf(target) : -1;
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

  // Check if group is smaller than expected (someone left/was idle)
  const expectedGroupSize = 3;
  const groupIsSmaller = playersInGroup.length < expectedGroupSize;

  // Check if speaker sent any messages (for idle speaker detection)
  // During Selection stage, use live stage chat; during Feedback, use saved round chat
  // (chat is saved to player.round at end of Selection stage in callbacks.js)
  const isSelectionStage = stage.get("name") === "Selection";
  const playerGroupChat = isSelectionStage
    ? (stage.get(`${playerGroup}_chat`) || [])
    : (player.round.get("chat") || []);
  const speaker = playersInGroup.find((p) => p.round.get("role") === "speaker");
  const speakerSentMessage = speaker && playerGroupChat.some((msg) => msg.sender?.id === speaker.id);

  // Check if speaker is missing (was kicked mid-block)
  const speakerMissing = !speaker && isListener;

  // Get total blocks from game (set based on TEST_MODE)
  const phase1Blocks = game.get("phase1Blocks") || PHASE_1_BLOCKS;
  const phase2Blocks = game.get("phase2Blocks") || PHASE_2_BLOCKS;
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
        // Check if there are multiple groups (TEST_MODE has only 1 group)
        const activeGroups = game.get("active_groups") || [];
        if (activeGroups.length > 1) {
          waitingMessage =
            "All players in group responded! Waiting for members of other groups to respond...";
        } else {
          waitingMessage = "All players responded!";
        }
        // Auto-submit this player's stage when all in group have responded
        if (!player.stage?.get("submit")) {
          player.stage?.set("submit", true);
        }
      } else {
        waitingMessage = "Waiting for the players in your group to respond...";
      }
    }
  }

  let feedback = "";
  let socialFeedback = "";
  if (stage.get("name") == "Feedback") {
    if (player.round.get("role") == "listener") {
      // Check if speaker was missing (kicked) or idle (didn't send any message)
      if (!speaker) {
        feedback = "Your speaker was removed from the game. A new speaker will be assigned.";
      } else if (!speakerSentMessage) {
        feedback = "The speaker did not send a message this round. No points were awarded.";
      } else if (!player.round.get("clicked")) {
        // Listener didn't respond in time
        feedback = "You did not respond in time. You earned no points this round.";
      } else if (correct) {
        feedback = "Correct! You earned 2 points for the picture.";
      } else {
        feedback = "Ooops, that wasn't the target! You earned no points this round from guessing the picture.";
      }
    }
    if (player.round.get("role") == "speaker") {
      const roundScore = player.round.get("round_score") || 0;
      feedback = `You earned ${roundScore} ${roundScore == 1 ? `point` : `points`} this round from picture guessing.`;
    }

    // Add social feedback for social_mixed condition in Phase 2
    if (isSocialMixed) {
      socialFeedback = "Total in-group guessing score will be shown at the end of the experiment.";
    }
  }

  // Check if player was idle in previous rounds — show warning for any idle count below threshold
  const idleRounds = player.get("idle_rounds") || 0;
  const showIdleWarning = idleRounds > 0 && idleRounds < MAX_IDLE_ROUNDS;

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
          You'll see how well you did at the end of the game.
        </p>
      </div>
    );
  };

  return (
    <div
      className="task"
      data-target-index={targetIndex}
      data-role={player.round.get("role")}
      data-current-group={playerGroup}
    >
      <div className="status">
        <div className="players card">
          <h3 style={{ textAlign: "center", marginBottom: "10px" }}>
            Your Group | Phase {phase_num} - Block {displayBlockNum} of {totalBlocks}
          </h3>
          {groupIsSmaller && (
            <p style={{
              textAlign: "center",
              fontSize: "0.85rem",
              color: "#dc2626",
              marginBottom: "8px",
              fontStyle: "italic"
            }}>
              Your group is smaller because a player left or was inactive.
            </p>
          )}
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
              ? "You are the speaker. Please describe the picture in the box to the other players." +
                (isSocialMixed ? " You will also be rewarded if listeners from your original group correctly identify you as a member of their group." : "")
              : "You are a listener. Please click on the picture that the speaker describes." +
                (isSocialMixed ? " Then guess whether the speaker was in your original group." : "")}
          </p>
        </div>

        <div className="all-tangrams">
          <div className="tangrams grid">{tangramsToRender}</div>
        </div>

        {renderSocialGuess()}

        {speakerMissing && isSelectionStage && (
          <h3
            style={{
              marginTop: 5,
              marginBottom: "auto",
              textAlign: "center",
              color: "#dc2626",
              fontStyle: "italic",
              width: "100%",
            }}
          >
            Your group's speaker was removed. A new speaker will be assigned next round.
          </h3>
        )}

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

        {socialFeedback && stage.get("name") == "Feedback" && (
          <p
            style={{
              marginTop: 8,
              textAlign: "center",
              color: "#6b7280",
              fontStyle: "italic",
              width: "100%",
            }}
          >
            {socialFeedback}
          </p>
        )}

        {showIdleWarning && stage.get("name") == "Feedback" && (
          <p
            style={{
              marginTop: 12,
              textAlign: "center",
              color: "#dc2626",
              fontWeight: "bold",
              width: "100%",
              backgroundColor: "#fee2e2",
              padding: "8px 12px",
              borderRadius: "6px",
            }}
          >
            Warning: You have been inactive for {idleRounds} round(s). If you continue to be inactive, you will be removed from the experiment and will not receive any pay.
          </p>
        )}

        {stage.get("name") == "Feedback" &&
          (condition === "refer_mixed" || condition === "social_mixed") &&
          phase_num === 2 &&
          round.get("target_num") === 5 &&
          block_num < (game.get("phase2Blocks") || PHASE_2_BLOCKS) - 1 && (
          <p
            style={{
              marginTop: 12,
              textAlign: "center",
              color: "#6b7280",
              fontStyle: "italic",
              width: "100%",
            }}
          >
            Shuffling players for the next block...
          </p>
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
                player.stage?.set("submit", true);
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
