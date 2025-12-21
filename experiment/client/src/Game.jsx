import {
  Chat,
  usePlayer,
  usePlayers,
  useRound,
  useGame,
  useStage,
} from "@empirica/core/player/classic/react";

import { React, useEffect } from "react";
import { Profile } from "./Profile";
import { Task } from "./Task";

const roundSound = new Audio("round-sound.mp3");
const gameSound = new Audio("bell.mp3");

export function Game() {
  const game = useGame();
  const stage = useStage();
  const player = usePlayer();
  const players = usePlayers();
  const round = useRound();

  // play sounds when the round or game changes
  useEffect(() => {
    if (game.get("justStarted")) {
      gameSound
        .play()
        .catch((e) => console.warn("Error playing game sound:", e));
      game.set("justStarted", false);
    }
  }, [game.get("justStarted")]);

  useEffect(() => {
    if (round?.get("justStarted")) {
      roundSound
        .play()
        .catch((e) => console.warn("Error playing round sound:", e));
      round.set("justStarted", false);
    }
  }, [round?.get("justStarted")]);

  // Get current group for chat display
  const playerGroup = player.get("current_group");
  const condition = game.get("condition");
  const phase_num = round?.get("phase_num");
  const isSocialMixed = condition === "social_mixed" && phase_num === 2;

  // Check if all players in group have responded
  const playersInGroup = players.filter(
    (p) => p.get("current_group") === playerGroup && p.get("is_active")
  );
  const allGroupResponded = playersInGroup.every((p) => {
    if (p.round.get("role") === "speaker") return true;
    const clicked = p.round.get("clicked");
    const socialGuess = p.round.get("social_guess");
    return clicked && (!isSocialMixed || socialGuess);
  });

  // Show chat for any group during Selection stage (groups A, B, C)
  const showChat =
    stage?.get("name") === "Selection" &&
    !allGroupResponded &&
    playerGroup;

  return (
    <div className="h-full w-full flex">
      <div className="h-full w-full flex flex-col">
        <Profile />
        <div className="h-full flex items-center justify-center">
          <Task
            round={round}
            stage={stage}
            game={game}
            player={player}
            players={players}
          />
        </div>
      </div>

      {showChat && (
        <div className="h-full w-128 border-l flex justify-center items-center">
          <Chat player={player} scope={stage} attribute={`${playerGroup}_chat`} />
        </div>
      )}
    </div>
  );
}
