import { Loading } from "@empirica/core/player/react";
import React from "react";
import { Refgame } from "./stages/Refgame.jsx";
import { Transition } from "./stages/Transition.jsx";

export function Task(props) {
  const { round, stage, game, player, players } = props;

  // A removed player never reaches this component: Empirica shows the exit
  // steps as soon as `ended` is set (see exitSteps in App.jsx), and the
  // server writes `ended` in the same callback as `is_active`. This only
  // covers the instant between the two updates, should they ever be split.
  if (!player.get("is_active")) {
    return <Loading />;
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
