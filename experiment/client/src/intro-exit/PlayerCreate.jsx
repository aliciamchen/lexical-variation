import React, { useState } from "react";
import { Button } from "../components/Button";

export function MyPlayerForm({ onPlayerID, connecting }) {
  const [playerID, setPlayerID] = useState("");

  const handleSubmit = (evt) => {
    evt.preventDefault();
    if (!playerID || playerID.trim() === "") {
      return;
    }

    onPlayerID(playerID);
  };

  return (
    <div className="consent">
      <h1>Enter your Prolific ID</h1>
      <p>
        Please enter your Prolific ID below. This is used to verify your
        participation and ensure you receive your payment.
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
            autoFocus
            value={playerID}
            onChange={(e) => setPlayerID(e.target.value)}
            style={{
              width: "100%",
              padding: "0.6em",
              fontSize: "1.1em",
              border: "1px solid #ccc",
              borderRadius: "6px",
              marginBottom: "1.5em",
            }}
          />

          <div className="flex w-sw justify-center">
            <Button type="submit" autoFocus>
              Enter
            </Button>
          </div>
        </fieldset>
      </form>
    </div>
  );
}
