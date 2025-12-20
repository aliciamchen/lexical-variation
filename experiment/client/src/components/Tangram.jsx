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
    background: "url(tangram_" + tangram + ".png)",
    backgroundSize: "cover",
    width: "17vh",
    height: "17vh",
    gridRow: row,
    gridColumn: column,
    margin: "0.8rem",
  };

  // Phase 1: Refgame
  if (round.get("phase") == "refgame") {
    // Red group and blue groups play games separately
    const playerGroup = player.get("group");
    const playersInGroup = players.filter((p) => p.get("group") == playerGroup);
    const playerGroupSpeaker = playersInGroup.filter(
      (p) => p.round.get("role") == "speaker"
    )[0];

    const handleClick = (e) => {
      console.log("click2");
      if (stage.get("name") == "Feedback") {
        return;
      }

      const playerGroupChat = stage.get(`${playerGroup}_chat`) || [];
      const speakerMsgs = _.filter(playerGroupChat, (msg) => {
        return msg.sender.id == playerGroupSpeaker.id;
      });

      // only register click for listener and only after the speaker has sent a message
      if (
        (stage.get("name") == "Selection") &
        (speakerMsgs.length > 0) &
        !player.round.get("clicked") &
        (player.round.get("role") == "listener")
      ) {
        player.round.set("clicked", tangram);
        setTimeout(() => player.stage.set("submit", true), 3000); 
      }
      // end stage if all listeners have clicked
      const listeners = playersInGroup.filter(
        (p) => p.round.get("role") == "listener"
      );
      const allClicked = _.every(listeners, (p) => p.round.get("clicked"));

      if (allClicked) {
        console.log(playersInGroup);
        // end stage
        playersInGroup.forEach((p) => {
          p.stage.set("submit", true);
        });
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

  // Phase 2: Production
  // just show the tangram grid with target highlighted; no interaction
  if (round.get("phase") == "speaker_prod") {
    if (tangram == target) {
      _.extend(mystyle, {
        outline: `10px solid #000`,
        zIndex: "9",
      });
    }
    return <div style={mystyle}></div>;
  }

  // Phase 3: Comprehension
  // participants click on the tangram they think the speaker is describing
  if (round.get("phase") == "comprehension") {
    const handleClick = (e) => {
      console.log("click2");

      const clickedTangram = player.stage.get("clicked_tangram");
      if (clickedTangram === tangram) {
        // if this is the same tangram that was clicked before, do nothing
        return;
      }

      if (typeof onSelect === "function") {
        onSelect(tangram);
      }
    };
    if (tangram == player.stage.get("clicked_tangram")) {
      mystyle = {
        ...mystyle,
        outline: `10px solid #A9A9A9`,
        zIndex: "9",
      };
    }
    return <div onClick={handleClick} style={mystyle}></div>;
  }
  
  // default case
  return <div style={mystyle}></div>;
}
