import { useStageTimer } from "@empirica/core/player/classic/react";
import React from "react";
import _ from "lodash";
import { useGame } from "@empirica/core/player/classic/react";

export function Tangram(props) {
  const {
    tangram,
    tangram_num,
    stage,
    player,
    players,
    round,
    game,
    target,
    onSelect,
    ...rest
  } = props;

  // Make tangram grid
  const row = 1 + Math.floor(tangram_num / 3);
  const column = 1 + (tangram_num % 3);
  let mystyle = {
    background: "url(tangram_" + tangram + ".svg)",
    backgroundSize: "85%",
    backgroundRepeat: "no-repeat",
    backgroundPosition: "center",
    width: "12vh",
    height: "12vh",
    gridRow: row,
    gridColumn: column,
    margin: "0.8rem",
  };

  // Phase 1 and Phase 2: Refgame
  if (round.get("phase") == "refgame") {
    // Groups play games separately (use current_group for mixed conditions)
    const playerGroup = player.get("current_group");
    const playersInGroup = players.filter((p) => p.get("current_group") == playerGroup && p.get("is_active"));
    const playerGroupSpeaker = playersInGroup.filter(
      (p) => p.round.get("role") == "speaker"
    )[0];

    // Get condition info for social_mixed handling
    const condition = game.get("condition");
    const phase_num = round.get("phase_num");
    const isSocialMixed = condition === "social_mixed" && phase_num === 2;

    // Check if tangram is clickable (listener in Selection stage, speaker has sent message)
    const playerGroupChat = stage.get(`${playerGroup}_chat`) || [];
    const speakerMsgs = _.filter(playerGroupChat, (msg) => {
      return msg.sender.id == playerGroupSpeaker?.id;
    });
    const isClickable =
      stage.get("name") === "Selection" &&
      player.round.get("role") === "listener" &&
      speakerMsgs.length > 0 &&
      !player.round.get("clicked");

    // Add pointer cursor when clickable
    if (isClickable) {
      _.extend(mystyle, { cursor: "pointer" });
    }

    const handleClick = (e) => {
      if (stage.get("name") == "Feedback") {
        return;
      }

      // Only register click for listener and only after the speaker has sent a message
      // (isClickable already checks these conditions, but re-check for safety)
      if (isClickable) {
        player.round.set("clicked", tangram);

        // Check if all listeners have now responded (only after registering a click)
        const listeners = playersInGroup.filter(
          (p) => p.round.get("role") === "listener"
        );
        const allResponded = _.every(listeners, (p) => {
          const clicked = p.round.get("clicked");
          const socialGuess = p.round.get("social_guess");
          return clicked && (!isSocialMixed || socialGuess);
        });

        // Double-check we're still in Selection before auto-submitting
        if (allResponded && stage.get("name") === "Selection") {
          playersInGroup.forEach((p) => {
            p.stage.set("submit", true);
          });
        }
      }
    };

    // Highlight target object for speaker
    if ((target == tangram) & (player.round.get("role") == "speaker")) {
      _.extend(mystyle, {
        outline: "10px solid #000",
        zIndex: "9",
      });
    }

    // Show listeners what they've clicked
    if (
      (stage.get("name") == "Selection") &
      (tangram == player.round.get("clicked"))
    ) {
      _.extend(mystyle, {
        outline: `10px solid #A9A9A9`,
        zIndex: "9",
      });
    }

    // Feedback
    let feedback = [];
    if (stage.get("name") == "Feedback") {
      playersInGroup.forEach((p, index) => {
        if (p.round.get("clicked") == tangram) {
          feedback.push(
            <img
              key={`avatar-${index}`}
              src={p.get("avatar")}
              alt="Player avatar"
            />
          );
        }
      });
    }
    if (
      (stage.get("name") == "Feedback") &
      _.some(playersInGroup, (p) => p.round.get("clicked") == tangram)
    ) {
      const color = tangram == target ? "green" : "red";
      _.extend(mystyle, {
        outline: `10px solid ${color}`,
        zIndex: "9",
      });
    }

    return (
      <div onClick={handleClick} style={mystyle}>
        <div className="feedback"> {feedback}</div>
      </div>
    );
  }

  // Old Phase 2 (Production) and Phase 3 (Comprehension) are removed in new experiment design
  
  // default case
  return <div style={mystyle}></div>;
}
