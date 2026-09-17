import React, { useState } from "react";
import { Button } from "../components/Button";

export function MyPlayerForm({ onPlayerID, connecting }) {
  // Prolific opens the study link with the participant's id in PROLIFIC_PID,
  // so the field is filled from it and locked: an id typed by hand is how
  // payments end up not matching a submission. Without the parameter (local
  // testing, the Playwright suite) the field stays editable, and the id is
  // whatever is typed.
  const prolificPid =
    new URLSearchParams(window.location.search).get("PROLIFIC_PID") || "";
  const fromLink = prolificPid !== "";
  const [playerID, setPlayerID] = useState(prolificPid);

  const handleSubmit = (evt) => {
    evt.preventDefault();
    if (!playerID || playerID.trim() === "") {
      return;
    }

    onPlayerID(playerID.trim());
  };

  return (
    <div className="consent">
      <h1>{fromLink ? "Confirm your Prolific ID" : "Enter your Prolific ID"}</h1>
      <p>
        {fromLink
          ? "This is used to verify your participation and ensure you receive your payment."
          : "Please enter your Prolific ID below. This is used to verify your participation and ensure you receive your payment."}
      </p>

      <form onSubmit={handleSubmit}>
        <fieldset disabled={connecting} style={{ border: "none", padding: 0 }}>
          <label
            htmlFor="playerID"
            style={{
              display: "block",
              fontSize: "1.1em",
              fontWeight: "bold",
              marginBottom: "0.5em",
            }}
          >
            Prolific ID
          </label>
          <input
            id="playerID"
            name="playerID"
            type="text"
            autoComplete="off"
            required
            autoFocus={!fromLink}
            readOnly={fromLink}
            aria-readonly={fromLink}
            value={playerID}
            onChange={(e) => setPlayerID(e.target.value)}
            style={{
              width: "100%",
              padding: "0.6em",
              fontSize: "1.1em",
              border: "1px solid #ccc",
              borderRadius: "6px",
              marginBottom: fromLink ? "0.5em" : "1.5em",
              backgroundColor: fromLink ? "#f3f4f6" : "white",
              color: fromLink ? "#374151" : "inherit",
            }}
          />
          {fromLink && (
            <p
              style={{
                fontSize: "0.9em",
                color: "#6b7280",
                marginBottom: "1.5em",
              }}
            >
              Your Prolific ID was filled in from the study link.
            </p>
          )}

          <div className="flex w-sw justify-center">
            <Button type="submit" autoFocus={fromLink}>
              Enter
            </Button>
          </div>
        </fieldset>
      </form>
    </div>
  );
}
