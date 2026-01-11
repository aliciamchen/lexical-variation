import React from "react";
import { usePlayer } from "@empirica/core/player/classic/react";
import { Alert } from "../components/Alert";
import { Button } from "../components/Button";
import { LOBBY_TIMEOUT_PAY } from "../constants";

export function Sorry({ next }) {
  const player = usePlayer();
  const endedReason = player.get("ended");
  const partialPay = player.get("partialPay");
  const partialBasePay = player.get("partialBasePay");
  const partialBonus = player.get("partialBonus");
  const minutesSpent = player.get("minutesSpent");
  const gameStartTime = player.get("gameStartTime");

  // Detect lobby timeout: player never started a game (no gameStartTime)
  // and wasn't explicitly kicked for another reason
  const isLobbyTimeout = !gameStartTime &&
    endedReason !== "player timeout" &&
    endedReason !== "group disbanded";

  function handleSubmit(event) {
    event.preventDefault();
    player.set("exitSurvey", {
      gamefailed: isLobbyTimeout ? "lobby timeout" : (endedReason || "unknown"),
    });
    next();
  }

  // Different messages based on why the player was removed
  let title = "Game Ended";
  let message = "";
  let compensationCode = null;
  let compensationMessage = null;
  let showCompensation = true;

  if (isLobbyTimeout || endedReason === "lobby timeout") {
    title = "Waiting Room Timeout";
    message = (
      <>
        <p>
          Unfortunately, we were unable to find enough participants to start the game within
          the waiting time limit.
        </p>
        <p className="mt-2">
          We apologize for the wait. You will receive compensation for your time in the waiting room.
        </p>
      </>
    );
    compensationCode = "LOBBYTIMEOUT";
    compensationMessage = `$${LOBBY_TIMEOUT_PAY.toFixed(2)} for your waiting time`;
  } else if (endedReason === "player timeout") {
    title = "Removed for Inactivity";
    message = (
      <>
        <p>
          You were removed from the game because you were inactive for 2 consecutive rounds.
          This may have happened because you didn't send any messages or make any selections.
        </p>
        <p className="mt-2">
          We understand that technical issues or distractions can occur. If you believe this was
          an error, please contact the researcher on Prolific.
        </p>
      </>
    );
    // Idle players do NOT receive compensation
    showCompensation = false;
  } else if (endedReason === "group disbanded") {
    title = "Group Disbanded";
    const payAmount = partialPay != null ? partialPay.toFixed(2) : "0.00";
    const basePayAmount = partialBasePay != null ? partialBasePay.toFixed(2) : "0.00";
    const bonusAmount = partialBonus != null ? partialBonus.toFixed(2) : "0.00";
    const timeMsg = minutesSpent != null ? `${minutesSpent} minutes` : "your time";
    message = (
      <>
        <p>
          Unfortunately, too many members of your original group left the game, and we were
          unable to continue the experiment with the remaining players.
        </p>
        <p className="mt-2">
          This is not your fault - we apologize for the inconvenience. You will receive
          compensation proportional to the time you spent ({timeMsg}) plus any bonus you earned.
        </p>
      </>
    );
    compensationCode = "DISBANDED2026";
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

  return (
    <div className="py-8 max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
      <Alert title={title}>
        {message}
      </Alert>

      {showCompensation && compensationCode ? (
        <Alert title="Payment">
          <p>
            Please submit the following code on Prolific to receive {compensationMessage}:{" "}
            <strong>{compensationCode}</strong>
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
            If you believe this was an error, please contact the researcher on Prolific.
          </p>
        </Alert>
      )}

      <form onSubmit={handleSubmit}>
        <div className="mt-8">
          <Button type="submit">Submit</Button>
        </div>
      </form>
    </div>
  );
}
