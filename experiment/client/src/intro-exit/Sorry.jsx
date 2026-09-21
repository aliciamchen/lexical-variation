import React from "react";
import { usePlayer } from "@empirica/core/player/classic/react";
import { Loading } from "@empirica/core/player/react";
import { Alert } from "../components/Alert";
import {
  EXIT_REASONS,
  LOBBY_TIMEOUT_PAY,
  PARTIAL_PAY_SURVEY_REASONS,
  PROLIFIC_CODES,
} from "../constants";

const money = (amount) => (amount != null ? amount.toFixed(2) : "0.00");

export function Sorry() {
  const player = usePlayer();

  // `usePlayer` is a subscription: empty on the first render, and empty again
  // whenever the participant context tears down, which a dropped websocket
  // does. EmpiricaContext's own check does not protect this component -- the
  // subscription here fires independently and re-renders this component
  // alone, without consulting the parent. Unguarded, that render throws, and
  // React unmounts the whole app, so a participant holding their completion
  // code gets a blank page. This happened in production on 2026-09-19.
  if (!player) {
    return <Loading />;
  }

  // Use exitReason (our custom attribute) first: Empirica overwrites `ended`
  // with "game ended" / "game terminated" / "game failed" itself.
  const exitReason = player.get("exitReason");
  const endedReason = exitReason || player.get("ended");
  const partialPay = player.get("partialPay");
  const partialBasePay = player.get("partialBasePay");
  const partialBonus = player.get("partialBonus");
  const gameStartTime = player.get("gameStartTime");

  // The player waited and never played. `gameStartTime` is written in
  // onGameStart, so its absence covers two ways of getting here: the lobby
  // timed out (Empirica writes "game failed"), or the researcher stopped the
  // batch while this player was still waiting. The second writes "game
  // terminated" like any other stopped game, but a game that never started
  // never reaches onGameEnded, so no pay was ever computed for them; treating
  // them as a lobby timeout is both true to what happened and the only branch
  // that shows a code the payment tooling can find.
  //
  // A quiz failure is the one other way to have no gameStartTime, and it is
  // not a lobby timeout: they are owed nothing. The branch below handles them
  // first, but this flag is also what `data-exit-reason` reports, so it has
  // to exclude them here rather than rely on the ordering.
  const isLobbyTimeout =
    !gameStartTime && endedReason !== EXIT_REASONS.quizFailed;

  // Different messages based on why the player was removed
  let title = "Game Ended";
  let message = "";
  let compensationCode = null;
  let compensationMessage = null;
  let showCompensation = true;

  if (endedReason === EXIT_REASONS.quizFailed) {
    title = "Quiz Failed";
    message = (
      <>
        <p>
          Unfortunately, you were not able to pass the comprehension quiz. You
          will not be able to participate in this study.
        </p>
        <p className="mt-2">
          Please return this study on Prolific so another participant can take
          your place.
        </p>
      </>
    );
    showCompensation = false;
  } else if (isLobbyTimeout) {
    title = "Participant Recruitment Issue";
    message = (
      <>
        <p>
          Unfortunately, we were unable to find enough participants to start a
          new game, or the players you were assigned to play with have already
          found partners and started.
        </p>
        <p className="mt-2">
          We apologize for the inconvenience. You will receive compensation for
          your time spent.
        </p>
      </>
    );
    compensationCode = PROLIFIC_CODES.lobbyTimeout;
    compensationMessage = `$${LOBBY_TIMEOUT_PAY.toFixed(2)} for your time spent`;
  } else if (endedReason === EXIT_REASONS.playerTimeout) {
    title = "Removed for Inactivity";
    message = (
      <>
        <p>
          You were removed from the game because you were inactive for multiple
          consecutive rounds. This may have happened because you didn't send any
          messages or make any selections.
        </p>
        <p className="mt-2">
          You will be paid for the time you spent in the game, but the bonus is
          forfeited when a player is removed for inactivity. We understand that
          technical issues or distractions can occur. If you believe this was an
          error, please contact the researcher on Prolific.
        </p>
      </>
    );
    // Prorated base pay for time spent; no bonus (see server/src/compensation.js)
    compensationCode = PROLIFIC_CODES.partial;
    compensationMessage = `$${money(partialBasePay)} for the time you spent (base pay only, no bonus)`;
  } else if (PARTIAL_PAY_SURVEY_REASONS.includes(endedReason)) {
    // These players already saw the full explanation on the ExitSurvey page.
    // This page just shows the Prolific completion code.
    title = "Completion Code";
    message = (
      <p>
        Thank you for completing the exit survey. Please use the code below to
        receive your payment.
      </p>
    );
    compensationCode = PROLIFIC_CODES.partial;
    compensationMessage = `$${money(partialPay)} ($${money(partialBasePay)} base + $${money(partialBonus)} bonus)`;
  } else if (partialPay != null) {
    // An unrecognized reason, but the server computed pay for this player, so
    // they were in a game that ended early. Never tell such a player they get
    // nothing: show the partial code and what they are owed.
    message = (
      <p>
        The session ended early. We apologize for the inconvenience; please use
        the code below to receive your payment.
      </p>
    );
    compensationCode = PROLIFIC_CODES.partial;
    compensationMessage = `$${money(partialPay)} ($${money(partialBasePay)} base + $${money(partialBonus)} bonus)`;
  } else {
    // Default / unknown reason with nothing owed
    message = (
      <>
        <p>
          Unfortunately, we were unable to match you with other participants for
          a game or experienced an error.
        </p>
        <p className="mt-2">
          If you would like to re-enter the queue, please contact the researcher
          on Prolific.
        </p>
      </>
    );
    showCompensation = false;
  }

  // Determine exit reason for data attribute
  let dataExitReason = endedReason || "unknown";
  if (isLobbyTimeout) dataExitReason = "lobby_timeout";

  return (
    <div
      className="py-8 max-w-5xl mx-auto px-4 sm:px-6 lg:px-8"
      data-testid="sorry-screen"
      data-exit-reason={dataExitReason}
      data-prolific-code={
        showCompensation && compensationCode ? compensationCode : "none"
      }
      data-partial-pay={money(partialPay)}
      data-player-id={player?.id || "unknown"}
    >
      <Alert title={title}>{message}</Alert>

      {showCompensation && compensationCode ? (
        <Alert title="Payment">
          <p>
            Please submit the following code on Prolific to receive{" "}
            {compensationMessage}: <strong>{compensationCode}</strong>
          </p>
          <p className="pt-1">
            Thank you for your time and willingness to participate in our study.
          </p>
        </Alert>
      ) : (
        <Alert title="Payment">
          <p>
            Unfortunately, you will not receive compensation for this session.
          </p>
          <p className="pt-1">
            If you believe this was an error, please contact the researcher on
            Prolific.
          </p>
        </Alert>
      )}
    </div>
  );
}
