import { Loading } from "@empirica/core/player/react";
import React from "react";
import { Refgame } from "./stages/Refgame.jsx";
import { Transition } from "./stages/Transition.jsx";
import { Inactive } from "./stages/Inactive.jsx";

export function Task(props) {
  const { round, stage, game, player, players } = props;

  // Check if player has been removed
  if (player.get("ended") === "player timeout" || player.get("ended") === "group disbanded") {
    return <Inactive />;
  }

  // Check if player is active
  if (!player.get("is_active")) {
    return <Inactive />;
  }

  switch (round.get("phase")) {
    case "refgame":
      return (
        <Refgame
          round={round}
          stage={stage}
          game={game}
          player={player}
          players={players}
        />
      );
    case "transition":
      return (
        <Transition
          round={round}
          stage={stage}
          game={game}
          player={player}
          players={players}
        />
      );
    default:
      return <Loading />;
  }
}
