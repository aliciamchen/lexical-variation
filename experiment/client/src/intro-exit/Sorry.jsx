import React from "react";
import { usePlayer } from "@empirica/core/player/classic/react";
import { Alert } from "../components/Alert";
import { Button } from "../components/Button";

export function Sorry({ next }) {
  const player = usePlayer();
  const endedReason = player.get("ended");

  function handleSubmit(event) {
    event.preventDefault();
    player.set("exitSurvey", {
      gamefailed: endedReason || "unknown",
    });
    next();
  }

  // Different messages based on why the player was removed
  let title = "Game Ended";
  let message = "";
  let compensationCode = "C1ISXUSE";
  let compensationMessage = "partial payment for your time";

  if (endedReason === "player timeout") {
    title = "Removed for Inactivity";
    message = (
      <>
        <p>
          You were removed from the game because you were inactive for 2 consecutive trials.
          This may have happened because you didn't send any messages or make any selections.
        </p>
        <p className="mt-2">
          We understand that technical issues or distractions can occur. If you believe this was
          an error, please contact the researcher on Prolific.
        </p>
      </>
    );
    compensationCode = "TIMEOUT2024";
    compensationMessage = "partial payment ($2)";
  } else if (endedReason === "group disbanded") {
    title = "Group Disbanded";
    message = (
      <>
        <p>
          Unfortunately, too many members of your original group left the game, and we were
          unable to continue the experiment with the remaining players.
        </p>
        <p className="mt-2">
          This is not your fault - we apologize for the inconvenience.
        </p>
      </>
    );
    compensationCode = "DISBANDED2024";
    compensationMessage = "partial payment based on your participation";
  } else if (endedReason === "lobby timeout") {
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
    compensationMessage = "partial payment ($2) for your waiting time";
  } else {
    // Default / unknown reason
    message = (
      <>
        <p>
          Unfortunately, we were unable to match you with other participants for
          a game or experienced an error. You will still be compensated for your
          time spent.
        </p>
        <p className="mt-2">
          If you would like to re-enter the queue, please contact the researcher
          on Prolific.
        </p>
      </>
    );
  }

  return (
    <div className="py-8 max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
      <Alert title={title}>
        {message}
      </Alert>
      <Alert title="Payment">
        <p>
          Please submit the following code on Prolific to receive {compensationMessage}:{" "}
          <strong>{compensationCode}</strong>
        </p>
        <p className="pt-1">
          Thank you for your time and willingness to participate in our study.
        </p>
      </Alert>

      <form onSubmit={handleSubmit}>
        <div className="mt-8">
          <Button type="submit">Submit</Button>
        </div>
      </form>
    </div>
  );
}
