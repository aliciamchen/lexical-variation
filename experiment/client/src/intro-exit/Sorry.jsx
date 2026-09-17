import React from "react";
import { usePlayer } from "@empirica/core/player/classic/react";
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
  // Use exitReason (our custom attribute) first: Empirica overwrites `ended`
  // with "game ended" / "game terminated" / "game failed" itself.
  const exitReason = player.get("exitReason");
  const endedReason = exitReason || player.get("ended");
  const partialPay = player.get("partialPay");
  const partialBasePay = player.get("partialBasePay");
  const partialBonus = player.get("partialBonus");
  const gameStartTime = player.get("gameStartTime");

  // Lobby timeout: the player never started a game (no gameStartTime) and the
  // server did not remove them for one of its own reasons. Empirica writes
  // "game failed" to `ended` in that case, which is not a reason of ours, so
  // the absence of gameStartTime is what detects it.
  const isLobbyTimeout =
    !gameStartTime && !Object.values(EXIT_REASONS).includes(endedReason);

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
