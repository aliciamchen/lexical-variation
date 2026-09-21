import {
  usePlayer,
  useRound,
  useStage,
  useGame,
} from "@empirica/core/player/classic/react";
import { Loading } from "@empirica/core/player/react";
import React from "react";
import { Avatar } from "./components/Avatar";
import { Timer } from "./components/Timer";

export function Profile() {
  const player = usePlayer();
  const round = useRound();
  const stage = useStage();
  const game = useGame();

  // `usePlayer` is a subscription that is empty on the first render and again
  // whenever the participant context tears down (a dropped websocket does
  // exactly that). EmpiricaContext checks for a missing player, but that check
  // is in the parent: the subscription here fires on its own and re-renders
  // this component alone, so the parent never gets a say. Unguarded, the
  // render throws and React unmounts the whole app. Empirica's own components
  // guard the same way.
  if (!player) {
    return <Loading />;
  }

  const score = player.get("score") || 0;
  const phase_num = round ? round.get("phase_num") : null;
  const originalGroup = player.get("original_group");
  const playerName = player.get("name");

  return (
    <div
      // Fluid up to a cap, not a hard floor. `min-w-lg md:min-w-2xl` pinned
      // this bar at 672px, and because it sits in the same flex row as the
      // chat, the game column could not shrink past that, so every pixel the
      // window lost came out of the chat: 342px of chat at a 1024px window
      // and 128px at 800px, which is unusable. Capped instead, the two
      // columns share the loss. (`m-x-auto` and `border-.5` were also dead:
      // neither is a class UnoCSS generates, so the bar has never been
      // centered and has never had a border.)
      className="w-full max-w-2xl mt-2 mx-auto px-3 py-2 text-gray-500 rounded-md grid grid-cols-3 items-center gap-2"
      // Readable in a Sentry replay: the round, the stage, the timer and the
      // score are what tell you where a participant was when something broke.
      data-sentry-unmask
      data-player-name={playerName}
      data-player-group={originalGroup}
    >
      <div className="leading-tight ml-1">
        <div className="text-gray-600 font-semibold">
          {round ? round.get("name") : ""}
        </div>
        <div className="text-empirica-500 font-medium">
          {stage ? stage.get("name") : ""}
        </div>
      </div>

      <Timer />

      <div className="flex space-x-3 items-center justify-end">
        <div className="flex flex-col items-center">
          <div className="text-xs font-semibold uppercase tracking-wide leading-none text-gray-400">
            Score
          </div>
          <div className="text-3xl font-semibold !leading-none tabular-nums">
            {score}
          </div>
        </div>
        <div className="h-11 w-11">
          <Avatar player={player} />
        </div>
      </div>
    </div>
  );
}
