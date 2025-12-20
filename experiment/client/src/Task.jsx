import { Loading } from "@empirica/core/player/react";
import React from "react";
import { Refgame } from "./stages/Refgame.jsx";
import { Production } from "./stages/Production.jsx";
import { Comprehension } from "./stages/Comprehension.jsx";
import { Transition } from "./stages/Transition.jsx";
import { Inactive } from "./stages/Inactive.jsx";

// TODO: Add the transitions between the phases
export function Task(props) {
  const { round, stage, game, player, players } = props;
  if (player.get("ended") === "player timeout") {
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
    case "speaker_prod":
      return (
        <Production
          round={round}
          stage={stage}
          game={game}
          player={player}
          players={players}
        />
      );
    case "comprehension":
      return (
        <Comprehension
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
