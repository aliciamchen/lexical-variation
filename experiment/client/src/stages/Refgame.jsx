import React, { useState, useEffect } from "react";
import { useStageTimer } from "@empirica/core/player/classic/react";
import { Tangram } from "../components/Tangram.jsx";
import { Button } from "../components/Button.jsx";
import { PHASE_1_BLOCKS, PHASE_2_BLOCKS, MAX_IDLE_ROUNDS, hasSocialGuessing, isMixedCondition } from "../constants";

export function Refgame(props) {
  const { round, stage, game, player, players } = props;
  const [hasSubmitted, setHasSubmitted] = useState(false);
  const [localTangramSelection, setLocalTangramSelection] = useState(null);
  const [localSocialGuess, setLocalSocialGuess] = useState(null);

  // Reset local state when stage/round changes
  useEffect(() => {
    if (stage.get("name") === "Feedback") {
      setHasSubmitted(false);
    }
    setLocalTangramSelection(null);
    setLocalSocialGuess(null);
  }, [stage.get("name"), round.get("target_num")]);

  const target = round.get("target");
  const shuffled_tangrams = player.get("shuffled_tangrams");
  // Use server-computed correctness to avoid race conditions where the
  // client has an optimistic "clicked" value that hasn't synced to the server.
  const correct = player.round.get("clicked_correct");

  // Compute target index for testing purposes
  const targetIndex = shuffled_tangrams
    ? shuffled_tangrams.indexOf(target)
    : -1;
  const condition = game.get("condition");
  const phase_num = round.get("phase_num");
  const block_num = round.get("block_num");

  // Determine if social guessing is enabled
  const isSocialMixed = hasSocialGuessing(condition) && phase_num === 2;
  const isListener = player.round.get("role") === "listener";
  const simultaneousMode =
    isSocialMixed && isListener && stage.get("name") === "Selection";

  // Auto-commit local selections when timer expires (safety net for simultaneous mode)
  const timer = useStageTimer();
  const remainingSeconds = timer?.remaining ? Math.round(timer.remaining / 1000) : null;

  useEffect(() => {
    if (
      simultaneousMode &&
      remainingSeconds !== null &&
      remainingSeconds <= 1 &&
      !player.round.get("clicked") &&
      (localTangramSelection || localSocialGuess)
    ) {
      if (localTangramSelection) {
        player.round.set("clicked", localTangramSelection);
      }
      if (localSocialGuess) {
        player.round.set("social_guess", localSocialGuess);
      }
    }
  }, [remainingSeconds]);

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
        {...(simultaneousMode
          ? {
              onSelect: setLocalTangramSelection,
              localSelection: localTangramSelection,
            }
          : {})}
      />
    ));
  }

  // Render player status indicator
  const renderPlayer = (p, self = false) => {
    // In mixed conditions during Phase 2, use display_name and display_avatar
    const isMixed = isMixedCondition(condition) && phase_num === 2;
    const displayName = isMixed ? p.round.get("display_name") : p.get("name");
    const displayAvatar = isMixed
      ? p.round.get("display_avatar")
      : p.get("avatar");

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
  const playersInGroup = players.filter(
    (p) => p.get("current_group") === playerGroup && p.get("is_active"),
  );
  const otherPlayers = playersInGroup.filter((p) => p.id !== player.id);

  // Check if group is smaller than expected (someone left/was idle)
  const expectedGroupSize = 3;
  const groupIsSmaller = playersInGroup.length < expectedGroupSize;

  // Check if speaker sent any messages (for idle speaker detection)
  // During Selection stage, use live stage chat; during Feedback, use saved round chat
  // (chat is saved to player.round at end of Selection stage in callbacks.js)
  const isSelectionStage = stage.get("name") === "Selection";
  const playerGroupChat = isSelectionStage
    ? stage.get(`${playerGroup}_chat`) || []
    : player.round.get("chat") || [];
  const speaker = playersInGroup.find((p) => p.round.get("role") === "speaker");
  const speakerSentMessage =
    speaker && playerGroupChat.some((msg) => msg.sender?.id === speaker.id);

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
    const playerResponded =
      player.round.get("role") === "speaker" ||
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
  if (stage.get("name") == "Feedback") {
    const pictureRoundScore = player.round.get("round_score") || 0;
    const socialRoundScore = player.round.get("social_round_score") || 0;
    const combinedScore =
      Math.round((pictureRoundScore + socialRoundScore) * 100) / 100;

    if (player.round.get("role") == "listener") {
      // Check if speaker was missing (kicked) or idle (didn't send any message)
      if (!speaker) {
        feedback =
          "Your speaker was removed from the game. A new speaker will be assigned.";
      } else if (!speakerSentMessage) {
        feedback =
          "The speaker did not send a message this round. No points were awarded.";
      } else if (!player.round.get("clicked")) {
        // Listener didn't respond in time
        feedback =
          "You did not respond in time. You earned no points this round.";
      } else if (isSocialMixed) {
        // Social mixed: show picture feedback + social feedback card + combined score
        const pictureFeedback = correct
          ? "Correct! You identified the target picture."
          : "That wasn't the target picture.";

        const socialGuess = player.round.get("social_guess");
        const socialCorrect = player.round.get("social_guess_correct");
        const speakerWasSameGroup = player.round.get("speaker_was_same_group");

        let socialCard = null;
        if (socialGuess) {
          const cardStyle = socialCorrect
            ? { backgroundColor: "#f0fdf4", color: "#16a34a" }
            : { backgroundColor: "#fef2f2", color: "#dc2626" };
          const prefix = socialCorrect ? "\u2713 " : "\u2717 ";
          const text = socialCorrect
            ? `Speaker identity guess correct: the speaker ${speakerWasSameGroup ? "was" : "was not"} a member of your original group.`
            : `Speaker identity guess incorrect: the speaker ${speakerWasSameGroup ? "was" : "was not"} a member of your original group.`;
          socialCard = (
            <div
              style={{
                ...cardStyle,
                fontWeight: "600",
                padding: "10px 14px",
                borderRadius: 6,
                margin: "10px auto",
                maxWidth: "70%",
                textAlign: "left",
              }}
            >
              {prefix}
              {text}
            </div>
          );
        }

        const pointsLine = `You earned ${combinedScore} ${combinedScore == 1 ? "point" : "points"} this round.`;
        feedback = (
          <>
            {pictureFeedback}
            {socialCard}
            {pointsLine}
          </>
        );
      } else if (correct) {
        feedback = `Correct! You earned ${pictureRoundScore} ${pictureRoundScore == 1 ? "point" : "points"}.`;
      } else {
        feedback =
          "Ooops, that wasn't the target! You earned no points this round.";
      }
    }
    if (player.round.get("role") == "speaker") {
      if (isSocialMixed) {
        const recognizedCount = player.round.get("social_recognized_count");
        const originalGroupListeners = player.round.get(
          "social_original_group_listeners",
        );

        let socialText = "";
        if (originalGroupListeners === 0) {
          socialText =
            "No members from your original group were listeners this round.";
        } else {
          socialText = `${recognizedCount} out of ${originalGroupListeners} ${originalGroupListeners == 1 ? "member" : "members"} from your original group recognized you this round.`;
        }

        let cardStyle;
        if (originalGroupListeners === 0) {
          // No original group listeners — neutral purple
          cardStyle = { backgroundColor: "#f5f3ff", color: "#7c3aed" };
        } else if (recognizedCount === 0) {
          // None recognized — red
          cardStyle = { backgroundColor: "#fef2f2", color: "#dc2626" };
        } else if (recognizedCount === originalGroupListeners) {
          // All recognized — green
          cardStyle = { backgroundColor: "#f0fdf4", color: "#16a34a" };
        } else {
          // Some recognized — purple
          cardStyle = { backgroundColor: "#f5f3ff", color: "#7c3aed" };
        }

        const socialCard = (
          <div
            style={{
              ...cardStyle,
              fontWeight: "600",
              padding: "10px 14px",
              borderRadius: 6,
              margin: "10px auto",
              width: "fit-content",
              maxWidth: "70%",
              textAlign: "center",
            }}
          >
            {socialText}
          </div>
        );

        const pointsLine = `You earned ${Math.round(combinedScore)} ${Math.round(combinedScore) == 1 ? "point" : "points"} this round.`;
        feedback = (
          <>
            {socialCard}
            {pointsLine}
          </>
        );
      } else {
        feedback = `You earned ${pictureRoundScore} ${pictureRoundScore == 1 ? "point" : "points"} this round.`;
      }
    }
  }

  // Check if player was idle in previous rounds — show warning for any idle count below threshold
  const idleRounds = player.get("idle_rounds") || 0;
  const showIdleWarning = idleRounds > 0 && idleRounds < MAX_IDLE_ROUNDS;

  if (hasSubmitted && stage.get("name") == "Feedback") {
    return (
      <div className="h-full w-full flex items-center justify-center text-gray-400 pointer-events-none">
        Please wait for other player(s).
      </div>
    );
  }

  // Commit both selections in simultaneous mode
  const handleSimultaneousSubmit = () => {
    if (!localTangramSelection || !localSocialGuess) return;
    player.round.set("clicked", localTangramSelection);
    player.round.set("social_guess", localSocialGuess);
  };

  // Social guess component for listeners in social_mixed condition
  const renderSocialGuess = () => {
    if (!isSocialMixed || !isListener || stage.get("name") !== "Selection") {
      return null;
    }

    // After submit, show confirmation
    const hasSocialGuess = player.round.get("social_guess");
    if (hasSocialGuess) {
      return (
        <div
          className="social-guess-container"
          style={{
            marginTop: 16,
            padding: 16,
            backgroundColor: "#f0f9ff",
            borderRadius: 8,
            textAlign: "center",
          }}
        >
          <p style={{ color: "#666" }}>
            You guessed:{" "}
            <strong>
              {hasSocialGuess === "same_group"
                ? "Same group"
                : "Different group"}
            </strong>
          </p>
        </div>
      );
    }

    // Toggle-style buttons using local state
    const currentGuess = localSocialGuess;
    return (
      <div
        className="social-guess-container"
        style={{
          marginTop: 16,
          padding: 16,
          backgroundColor: "#fff7ed",
          borderRadius: 8,
          border: "2px solid #f97316",
        }}
      >
        <p
          style={{ textAlign: "center", marginBottom: 12, fontWeight: "bold" }}
        >
          Was the speaker in your original group (from Phase 1)?
        </p>
        <div style={{ display: "flex", gap: "1rem", justifyContent: "center" }}>
          <button
            className="button"
            onClick={() => setLocalSocialGuess("same_group")}
            style={{
              padding: "8px 16px",
              backgroundColor:
                currentGuess === "same_group" ? "#4b5563" : "#9ca3af",
              color: "white",
              border: currentGuess === "same_group" ? "3px solid #000" : "none",
              borderRadius: 4,
              cursor: "pointer",
              fontWeight: currentGuess === "same_group" ? "bold" : "normal",
            }}
          >
            Yes, same group
          </button>
          <button
            className="button"
            onClick={() => setLocalSocialGuess("different_group")}
            style={{
              padding: "8px 16px",
              backgroundColor:
                currentGuess === "different_group" ? "#4b5563" : "#9ca3af",
              color: "white",
              border:
                currentGuess === "different_group" ? "3px solid #000" : "none",
              borderRadius: 4,
              cursor: "pointer",
              fontWeight:
                currentGuess === "different_group" ? "bold" : "normal",
            }}
          >
            No, different group
          </button>
        </div>

        {/* Submit button — only enabled when both selections are made */}
        <div
          style={{ display: "flex", justifyContent: "center", marginTop: 16 }}
        >
          <button
            data-testid="simultaneous-submit"
            className="button"
            onClick={handleSimultaneousSubmit}
            disabled={!localTangramSelection || !localSocialGuess}
            style={{
              padding: "10px 24px",
              backgroundColor:
                localTangramSelection && localSocialGuess
                  ? "#2563eb"
                  : "#9ca3af",
              color: "white",
              border: "none",
              borderRadius: 6,
              cursor:
                localTangramSelection && localSocialGuess
                  ? "pointer"
                  : "not-allowed",
              fontSize: "1rem",
              fontWeight: "bold",
            }}
          >
            Submit
          </button>
        </div>
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
            Your Group | Phase {phase_num} - Block {displayBlockNum} of{" "}
            {totalBlocks}
          </h3>
          {groupIsSmaller && (
            <p
              style={{
                textAlign: "center",
                fontSize: "0.85rem",
                color: "#dc2626",
                marginBottom: "8px",
                fontStyle: "italic",
              }}
            >
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
                (isSocialMixed
                  ? " You will be rewarded if listeners from your original group correctly identify you as a member of their group."
                  : "")
              : "You are a listener. Please click on the picture that the speaker describes." +
                (isSocialMixed
                  ? " Also guess whether the speaker was in your original group."
                  : "")}
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
            Your group's speaker was removed. A new speaker will be assigned
            next round.
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
            Warning: You have been inactive for {idleRounds} round(s). If you
            continue to be inactive, you will be removed from the experiment and
            will not receive any pay.
          </p>
        )}

        {stage.get("name") == "Feedback" &&
          isMixedCondition(condition) &&
          phase_num === 2 &&
          !(
            round.get("target_num") === 5 &&
            block_num >= (game.get("phase2Blocks") || PHASE_2_BLOCKS) - 1
          ) && (
            <p
              style={{
                marginTop: 12,
                textAlign: "center",
                color: "#6b7280",
                fontStyle: "italic",
                width: "100%",
              }}
            >
              Shuffling players for the next round...
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
