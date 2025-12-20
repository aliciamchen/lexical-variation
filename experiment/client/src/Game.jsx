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

  // right now this is repeating code - fix later
  const playerGroup = player.get("group");
  const playersInGroup = players.filter((p) => p.get("group") === playerGroup);
  const allGroupResponded = playersInGroup.every(
    (p) => p.round.get("role") === "speaker" || p.round.get("clicked")
  );

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

      {player.get("group") == "red" &&
        stage.get("name") == "Selection" &&
        !allGroupResponded && (
          <div className="h-full w-128 border-l flex justify-center items-center">
            <Chat player={player} scope={stage} attribute="red_chat" />
          </div>
        )}

      {player.get("group") == "blue" &&
        stage.get("name") == "Selection" &&
        !allGroupResponded && (
          <div className="h-full w-128 border-l flex justify-center items-center">
            <Chat player={player} scope={stage} attribute="blue_chat" />
          </div>
        )}
    </div>
  );
}
