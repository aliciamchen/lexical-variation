import React from "react";
import { Sorry } from "../intro-exit/Sorry.jsx";

// Inactive just reuses Sorry component to avoid code duplication.
// This is shown in Task.jsx when a player is ended mid-game,
// before Empirica routes them to the exit flow.
export function Inactive() {
  return <Sorry />;
}
