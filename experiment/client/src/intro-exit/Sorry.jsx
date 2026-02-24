import React from "react";
import { usePlayer } from "@empirica/core/player/classic/react";
import { Alert } from "../components/Alert";
import { LOBBY_TIMEOUT_PAY } from "../constants";

export function Sorry() {
  const player = usePlayer();
  // Use exitReason (our custom attribute) first — Empirica can overwrite
  // "ended" to "game ended" when the game finishes, clobbering our value.
  const exitReason = player.get("exitReason");
  const endedReason = exitReason || player.get("ended");
  const partialPay = player.get("partialPay");
  const partialBasePay = player.get("partialBasePay");
  const partialBonus = player.get("partialBonus");
  const gameStartTime = player.get("gameStartTime");

  // Detect lobby timeout: player never started a game (no gameStartTime)
  // and wasn't explicitly kicked for another reason
  const isLobbyTimeout =
    !gameStartTime &&
    endedReason !== "player timeout" &&
    endedReason !== "group disbanded" &&
    endedReason !== "quiz failed";

  // Different messages based on why the player was removed
  let title = "Game Ended";
  let message = "";
  let compensationCode = null;
  let compensationMessage = null;
  let showCompensation = true;

  if (endedReason === "quiz failed") {
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
  } else if (isLobbyTimeout || endedReason === "lobby timeout") {
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
    compensationCode = "CMZUY3MK";
    compensationMessage = `$${LOBBY_TIMEOUT_PAY.toFixed(2)} for your time spent`;
  } else if (endedReason === "player timeout") {
    title = "Removed for Inactivity";
    message = (
      <>
        <p>
          You were removed from the game because you were inactive for multiple
          consecutive rounds. This may have happened because you didn't send any
          messages or make any selections.
        </p>
        <p className="mt-2">
          We understand that technical issues or distractions can occur. If you
          believe this was an error, please contact the researcher on Prolific.
        </p>
      </>
    );
    // Idle players do NOT receive compensation
    showCompensation = false;
  } else if (
    endedReason === "group disbanded" ||
    endedReason === "low accuracy" ||
    endedReason === "insufficient groups after accuracy check"
  ) {
    // These players already saw the full explanation on the ExitSurvey page.
    // This page just shows the Prolific completion code.
    title = "Completion Code";
    const payAmount = partialPay != null ? partialPay.toFixed(2) : "0.00";
    const basePayAmount =
      partialBasePay != null ? partialBasePay.toFixed(2) : "0.00";
    const bonusAmount = partialBonus != null ? partialBonus.toFixed(2) : "0.00";
    message = (
      <p>
        Thank you for completing the exit survey. Please use the code below to
        receive your payment.
      </p>
    );
    compensationCode = "CFTYDMIY";
    compensationMessage = `$${payAmount} ($${basePayAmount} base + $${bonusAmount} bonus)`;
  } else {
    // Default / unknown reason
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
      data-partial-pay={partialPay?.toFixed(2) || "0.00"}
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
