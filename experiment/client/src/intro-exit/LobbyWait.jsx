import { usePlayer } from "@empirica/core/player/classic/react";
import { Loading } from "@empirica/core/player/react";
import React, { useEffect, useState } from "react";
import { LOBBY_TIMEOUT_MINUTES, LOBBY_TIMEOUT_PAY } from "../constants";

const twoDigits = (n) => String(n).padStart(2, "0");

/**
 * The waiting room, replacing Empirica's default lobby.
 *
 * The default says only "Waiting for other players / Please wait for the game
 * to be ready", with no sense of how long the wait can be and no mention of
 * the payment promised for a wait that comes to nothing (the only place that
 * appears is the last page of the instructions, several screens earlier). A
 * participant who gives up and closes the tab is still counted as ready by
 * Empirica, so the game starts with someone who is no longer there and their
 * group plays a member short until the idle threshold removes them. Telling
 * people what they are waiting for, how long it can take, and that they are
 * paid either way is the cheapest way to keep them in the tab.
 *
 * The elapsed time is this participant's own wait, counted from when this
 * screen mounted. It is deliberately not a countdown: the shared lobby timer
 * starts when the first player in the session becomes ready, not when each
 * participant arrives, so a countdown shown here would be wrong for everyone
 * who did not arrive first.
 */
export function LobbyWait() {
  const player = usePlayer();
  const [seconds, setSeconds] = useState(0);

  useEffect(() => {
    const id = setInterval(() => setSeconds((s) => s + 1), 1000);
    return () => clearInterval(id);
  }, []);

  if (!player) {
    return <Loading />;
  }

  const playerCount = player.get("treatment")?.playerCount;
  const elapsed = `${Math.floor(seconds / 60)}:${twoDigits(seconds % 60)}`;

  return (
    <div
      className="h-full flex items-center justify-center px-4"
      data-testid="lobby-screen"
      data-lobby-seconds={seconds}
      data-sentry-unmask
    >
      <div className="max-w-md text-center">
        <h3 className="text-lg font-medium text-gray-900">
          Waiting for other players
        </h3>
        <p className="mt-2 text-sm text-gray-500">
          The game begins as soon as{" "}
          {playerCount ? `${playerCount} players are` : "enough players are"}{" "}
          ready.
        </p>
        <p className="mt-4 text-3xl font-semibold tabular-nums text-empirica-500">
          {elapsed}
        </p>
        <p className="mt-1 text-xs uppercase tracking-wide text-gray-400">
          Time you have been waiting
        </p>
        <p className="mt-6 text-sm text-gray-500">
          Please keep this tab open and your sound on. A sound will play when
          the game starts.
        </p>
        <p className="mt-2 text-sm text-gray-500">
          {`We wait up to ${LOBBY_TIMEOUT_MINUTES} minutes for enough players. `}
          {`If we cannot find them, we will pay you $${LOBBY_TIMEOUT_PAY.toFixed(2)} `}
          {"for your time and give you a code to submit on Prolific."}
        </p>
      </div>
    </div>
  );
}
