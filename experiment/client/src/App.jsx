import { EmpiricaClassic } from "@empirica/core/player/classic";
import { EmpiricaContext } from "@empirica/core/player/classic/react";
import { EmpiricaMenu, EmpiricaParticipant } from "@empirica/core/player/react";
import React from "react";
import { Game } from "./Game";
import { ExitSurvey } from "./intro-exit/ExitSurvey";
import { Introduction } from "./intro-exit/Introduction";
import { ConsentPage } from "./intro-exit/Consent.jsx";
import { Sorry } from "./intro-exit/Sorry.jsx";
import { Failed } from "./intro-exit/Failed.jsx";

export default function App() {
  const urlParams = new URLSearchParams(window.location.search);
  const playerKey = urlParams.get("participantKey") || "";

  const { protocol, host } = window.location;
  const url = `${protocol}//${host}/query`;

  function introSteps({ game, player }) {
    // return []; // for testing
    return [ConsentPage, Introduction];
  }

  function exitSteps({ game, player }) {
    const ended = player.get("ended");
    if (ended === "game ended") {
      return [ExitSurvey];
    } else if (ended === "game terminated") {
      return [Failed];
    } else if (
      ended === "group disbanded" ||
      ended === "low accuracy" ||
      ended === "insufficient groups after accuracy check"
    ) {
      return [ExitSurvey, Sorry];
    } else {
      return [Sorry];
    }
  }

  return (
    <EmpiricaParticipant url={url} ns={playerKey} modeFunc={EmpiricaClassic}>
      <div className="h-screen relative">
        <EmpiricaMenu position="bottom-left" />
        <div className="h-full overflow-auto">
          <EmpiricaContext introSteps={introSteps} exitSteps={exitSteps}>
            <Game />
          </EmpiricaContext>
        </div>
      </div>
    </EmpiricaParticipant>
  );
}
