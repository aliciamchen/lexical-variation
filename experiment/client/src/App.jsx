import { EmpiricaClassic } from "@empirica/core/player/classic";
import { EmpiricaContext } from "@empirica/core/player/classic/react";
import { EmpiricaMenu, EmpiricaParticipant } from "@empirica/core/player/react";
import React from "react";
import { Game } from "./Game";
import { ExitSurvey } from "./intro-exit/ExitSurvey";
import { Introduction } from "./intro-exit/Introduction";
import { ConsentPage } from "./intro-exit/Consent.jsx";
import { Sorry } from "./intro-exit/Sorry.jsx";
import { MyPlayerForm } from "./intro-exit/PlayerCreate.jsx";
import { EXIT_REASONS, PARTIAL_PAY_SURVEY_REASONS } from "./constants";

export default function App() {
  const urlParams = new URLSearchParams(window.location.search);
  const playerKey = urlParams.get("PROLIFIC_PID") || "";

  const { protocol, host } = window.location;
  const url = `${protocol}//${host}/query`;

  function introSteps({ game, player }) {
    // return []; // for testing
    return [Introduction];
  }

  // Empirica shows the exit steps as soon as `player.get("ended")` is set, so
  // this decides every screen a participant sees after leaving the game.
  function exitSteps({ game, player }) {
    // Use exitReason (our custom attribute) first: Empirica overwrites `ended`
    // with "game ended" when the game finishes and with "game terminated" when
    // the admin stops the batch (the server then also writes `exitReason`).
    const exitReason = player.get("exitReason");
    const ended = player.get("ended");
    const reason = exitReason || ended;

    if (reason === EXIT_REASONS.quizFailed) {
      // Three failed quiz attempts: no survey, no pay (Sorry explains).
      return [Sorry];
    } else if (PARTIAL_PAY_SURVEY_REASONS.includes(reason)) {
      // Removed through no fault of their own (group disbanded, too few groups
      // left, accuracy screen, or the researcher stopped the session): survey
      // first, then the partial code and prorated pay on Sorry.
      return [ExitSurvey, Sorry];
    } else if (reason === EXIT_REASONS.playerTimeout) {
      return [Sorry];
    } else if (ended === "game ended") {
      // Finished the game: the survey's last page shows the completion code
      // and stays up (there is no further step).
      return [ExitSurvey];
    } else {
      // Lobby timeout ("game failed") or anything unexpected.
      return [Sorry];
    }
  }

  return (
    <EmpiricaParticipant url={url} ns={playerKey} modeFunc={EmpiricaClassic}>
      <div className="h-screen relative">
        <EmpiricaMenu position="bottom-left" />
        <div className="h-full overflow-auto">
          <EmpiricaContext
            consent={ConsentPage}
            playerCreate={MyPlayerForm}
            introSteps={introSteps}
            exitSteps={exitSteps}
          >
            <Game />
          </EmpiricaContext>
        </div>
      </div>
    </EmpiricaParticipant>
  );
}
