import React, { useState, useEffect, useRef } from "react";
import { useStageTimer } from "@empirica/core/player/classic/react";
import { Tangram } from "../components/Tangram.jsx";
import { Button } from "../components/Button.jsx";
import {
  GROUP_SIZE,
  PHASE_1_BLOCKS,
  PHASE_2_BLOCKS,
  MAX_IDLE_ROUNDS,
  ROUNDS_PER_BLOCK,
  hasSocialGuessing,
  isMixedCondition,
} from "../constants";
import { allGroupResponded, playerHasResponded } from "../groupResponse";

export function Refgame(props) {
  const { round, stage, game, player, players } = props;
  const [hasSubmitted, setHasSubmitted] = useState(false);
  const [localTangramSelection, setLocalTangramSelection] = useState(null);
  const [localSocialGuess, setLocalSocialGuess] = useState(null);
  // When each local choice was actually made. In the social conditions the two
  // choices are committed together on submit, so without these the commit time
  // would be the only record and the moment of choosing -- and which of the two
  // came first -- would be lost. Refs, so recording a time never re-renders.
  const localTangramAtRef = useRef(null);
  const localSocialGuessAtRef = useRef(null);

  // Reset local state when stage/round changes
  useEffect(() => {
    if (stage.get("name") === "Feedback") {
      setHasSubmitted(false);
    }
    setLocalTangramSelection(null);
    setLocalSocialGuess(null);
    localTangramAtRef.current = null;
    localSocialGuessAtRef.current = null;
  }, [stage.get("name"), round.get("target_num")]);

  // Stamp, once per player-round, when the Selection stage first rendered for
  // this participant. Response times are measured against this rather than the
  // server's stage start: both ends then come from the same client clock, so
  // skew between participants' machines cannot contaminate them.
  useEffect(() => {
    if (
      stage.get("name") === "Selection" &&
      !player.round.get("selection_rendered_at")
    ) {
      player.round.set("selection_rendered_at", Date.now());
    }
  }, [stage.get("name"), round.get("target_num")]);

  // Record a local choice together with the moment it was made. A participant
  // who changes their mind before submitting overwrites both, so these are the
  // time of the choice actually submitted, not of the first one considered.
  const chooseTangram = (tangram) => {
    localTangramAtRef.current = Date.now();
    setLocalTangramSelection(tangram);
  };
  const chooseSocialGuess = (guess) => {
    localSocialGuessAtRef.current = Date.now();
    setLocalSocialGuess(guess);
  };

  // Write both local choices and their timestamps onto the player-round.
  // `clicked_at` stays the commit time; `tangram_selected_at` is when the
  // participant chose, which is what a response time needs and what differs
  // between the simultaneous and immediate paths.
  const commitLocalSelections = () => {
    if (localTangramSelection) {
      player.round.set("clicked", localTangramSelection);
      player.round.set("clicked_at", Date.now());
      player.round.set("tangram_selected_at", localTangramAtRef.current);
    }
    if (localSocialGuess) {
      player.round.set("social_guess", localSocialGuess);
      player.round.set("social_guess_selected_at", localSocialGuessAtRef.current);
    }
  };

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

  // Use current_group for player grouping
  const playerGroup = player.get("current_group");
  const playersInGroup = players.filter(
    (p) => p.get("current_group") === playerGroup && p.get("is_active"),
  );
  const otherPlayers = playersInGroup.filter((p) => p.id !== player.id);

  // Check if speaker sent any messages (for idle speaker detection)
  // During Selection stage, use live stage chat; during Feedback, use saved round chat
  // (chat is saved to player.round at end of Selection stage in callbacks.js)
  const isSelectionStage = stage.get("name") === "Selection";
  const playerGroupChat = isSelectionStage
    ? stage.get(`${playerGroup}_chat`) || []
    : player.round.get("chat") || [];
  const speaker = playersInGroup.find((p) => p.round.get("role") === "speaker");
  const speakerSentMessage = Boolean(
    speaker && playerGroupChat.some((msg) => msg.sender?.id === speaker.id),
  );

  // Check if speaker is missing (was kicked mid-block)
  const speakerMissing = !speaker && isListener;

  // Auto-commit local selections when timer expires (safety net for simultaneous mode)
  const timer = useStageTimer();
  const remainingSeconds = timer?.remaining ? Math.round(timer.remaining / 1000) : null;

  useEffect(() => {
    if (
      simultaneousMode &&
      // Nothing can have been chosen before the speaker's description (the
      // tangrams and the guess buttons are both locked until then), and a
      // guess about a speaker who said nothing is unscored (scoring.js), so
      // there is nothing worth committing.
      speakerSentMessage &&
      remainingSeconds !== null &&
      remainingSeconds <= 1 &&
      !player.round.get("clicked") &&
      (localTangramSelection || localSocialGuess)
    ) {
      commitLocalSelections();
    }
  }, [remainingSeconds, localTangramSelection, localSocialGuess, speakerSentMessage]);

  // Whether this player, and then the whole group, has responded this round
  // (see groupResponse.js; Game.jsx hides the chat on the same rule).
  const playerResponded = playerHasResponded(player, {
    needsSocialGuess: isSocialMixed,
  });
  const groupResponded = allGroupResponded(playersInGroup, {
    needsSocialGuess: isSocialMixed,
  });

  // Auto-submit this player's stage once everyone in the group has responded.
  // Done per player, and only after their own selection is on the round, so a
  // submit cannot reach the server before the click it depends on. An effect
  // rather than a write during render: a render must not have side effects,
  // and this one used to fire on every re-render of the waiting screen.
  useEffect(() => {
    if (
      isSelectionStage &&
      playerResponded &&
      groupResponded &&
      !player.stage?.get("submit")
    ) {
      player.stage?.set("submit", true);
    }
  }, [isSelectionStage, playerResponded, groupResponded, round.get("target_num")]);

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
              onSelect: chooseTangram,
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
          {displayName || "Player"}
          {self
            ? " (You)"
            : p.round.get("role") === "listener"
              ? " (Listener)"
              : " (Speaker)"}
        </span>
      </div>
    );
  };

  // Check if group is smaller than expected (someone left/was idle)
  const groupIsSmaller = playersInGroup.length < GROUP_SIZE;

  // Get total blocks from game (set based on TEST_MODE)
  const phase1Blocks = game.get("phase1Blocks") || PHASE_1_BLOCKS;
  const phase2Blocks = game.get("phase2Blocks") || PHASE_2_BLOCKS;
  const totalBlocks = phase_num === 1 ? phase1Blocks : phase2Blocks;
  const displayBlockNum = block_num + 1;

  let waitingMessage = "";
  if (isSelectionStage && playerResponded) {
    if (groupResponded) {
      // Check if there are multiple groups (TEST_MODE has only 1 group)
      const activeGroups = game.get("active_groups") || [];
      if (activeGroups.length > 1) {
        waitingMessage =
          "All players in group responded! Waiting for members of other groups to respond...";
      } else {
        waitingMessage = "All players responded!";
      }
    } else {
      waitingMessage = "Waiting for the players in your group to respond...";
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
    commitLocalSelections();
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

    // Toggle-style buttons using local state. Locked until the speaker has
    // described the target, the same gate the tangrams use (Tangram.jsx): a
    // guess made before any description has no language to judge, and the
    // server does not score one (scoring.js). The panel itself stays visible
    // so listeners know the question is coming.
    const guessEnabled = speakerSentMessage;
    const currentGuess = localSocialGuess;
    const guessButtonStyle = (value) => ({
      padding: "8px 16px",
      backgroundColor: currentGuess === value ? "#4b5563" : "#9ca3af",
      color: "white",
      border: currentGuess === value ? "3px solid #000" : "none",
      borderRadius: 4,
      cursor: guessEnabled ? "pointer" : "not-allowed",
      opacity: guessEnabled ? 1 : 0.6,
      fontWeight: currentGuess === value ? "bold" : "normal",
    });
    return (
      <div
        className="social-guess-container"
        data-guess-enabled={guessEnabled}
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
        {!guessEnabled && (
          <p
            style={{
              textAlign: "center",
              marginBottom: 12,
              color: "#9a3412",
              fontStyle: "italic",
            }}
          >
            Waiting for the speaker's description
          </p>
        )}
        <div style={{ display: "flex", gap: "1rem", justifyContent: "center" }}>
          <button
            className="button"
            disabled={!guessEnabled}
            onClick={() => chooseSocialGuess("same_group")}
            style={guessButtonStyle("same_group")}
          >
            Yes, same group
          </button>
          <button
            className="button"
            disabled={!guessEnabled}
            onClick={() => chooseSocialGuess("different_group")}
            style={guessButtonStyle("different_group")}
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
      // Readable in a Sentry replay (see index.jsx): the block header, the role
      // instruction and the feedback line. The chat lives outside this
      // subtree, so message text stays masked.
      data-sentry-unmask
      data-tangram-set={game.get("tangram_set")}
      data-target={target}
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

        {/* Idle rounds are counted at the end of Feedback, so the warning is
            shown in the following Selection stage as well as in Feedback. */}
        {showIdleWarning && (
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
            continue to be inactive, you will be removed from the experiment,
            paid only for the time you spent, and lose your bonus.
          </p>
        )}

        {stage.get("name") == "Feedback" &&
          isMixedCondition(condition) &&
          phase_num === 2 &&
          // ...except after the very last round, when there is nothing to shuffle for
          !(
            round.get("target_num") === ROUNDS_PER_BLOCK - 1 &&
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
