import {
  usePlayer,
  usePlayers,
  useRound,
  useGame,
  useStage,
} from "@empirica/core/player/classic/react";
import { Chat } from "./components/Chat";
import { hasSocialGuessing, isMixedCondition } from "./constants";
import { allGroupResponded } from "./groupResponse";
import { useEngagementLog } from "./instrumentation";

import { Loading } from "@empirica/core/player/react";
import { useEffect, useRef } from "react";
import { Profile } from "./Profile";
import { Task } from "./Task";

const roundSound = new Audio("round-sound.mp3");
const gameSound = new Audio("bell.mp3");

export function Game() {
  const game = useGame();
  const stage = useStage();
  const player = usePlayer();
  const players = usePlayers();
  const round = useRound();

  // Log tab-visibility, connectivity, and viewport changes for the duration of
  // gameplay, so idle classification can tell absence from inaction. The count
  // is surfaced on the container below so the end-to-end spec can see that a
  // real browser event reached the player scope.
  const engagementCount = useEngagementLog(player);

  // Play a sound when the game starts and when each round starts. Whether a
  // sound has played is tracked here, per game and round id, rather than by
  // writing a flag back to the game or round scope: those scopes are shared,
  // so a flag reset by the first client to see it silenced everyone else
  // (and nine clients racing to write it). The server still sets `justStarted`
  // on both scopes; nothing reads it here.
  const playedGameRef = useRef(null);
  const playedRoundRef = useRef(null);

  useEffect(() => {
    if (!game?.id || playedGameRef.current === game.id) return;
    playedGameRef.current = game.id;
    gameSound.play().catch((e) => console.warn("Error playing game sound:", e));
  }, [game?.id]);

  useEffect(() => {
    if (!round?.id || playedRoundRef.current === round.id) return;
    playedRoundRef.current = round.id;
    roundSound
      .play()
      .catch((e) => console.warn("Error playing round sound:", e));
  }, [round?.id]);

  // `usePlayer` is a subscription that is empty on the first render and again
  // whenever the participant context tears down (a dropped websocket does
  // exactly that). EmpiricaContext checks for a missing player, but that check
  // is in the parent: the subscription here fires on its own and re-renders
  // this component alone, so the parent never gets a say. Unguarded, the
  // render throws and React unmounts the whole app. Empirica's own components
  // guard the same way.
  // Placed below every hook above, so the hook order cannot change between
  // renders; `useEngagementLog` already tolerates a missing player.
  if (!player || !game) {
    return <Loading />;
  }

  // Get current group for chat display
  const playerGroup = player.get("current_group");
  const condition = game.get("condition");
  const phase_num = round?.get("phase_num");
  const isSocialMixed = hasSocialGuessing(condition) && phase_num === 2;

  // Check if all players in group have responded (see groupResponse.js)
  const playersInGroup = players.filter(
    (p) => p.get("current_group") === playerGroup && p.get("is_active")
  );
  const groupResponded = allGroupResponded(playersInGroup, {
    needsSocialGuess: isSocialMixed,
  });

  // Show chat for any group during Selection stage (groups A, B, C)
  const showChat =
    stage?.get("name") === "Selection" && !groupResponded && playerGroup;

  // In mixed conditions during Phase 2, use display_name and display_avatar
  const isMixed = isMixedCondition(condition) && phase_num === 2;

  // Custom player name function to show role (Speaker/Listener)
  const customPlayerName = (p) => {
    const displayName = isMixed ? p.round?.get("display_name") : p.get("name");
    const role = p.round?.get("role");
    const roleLabel = role === "speaker" ? "(Speaker)" : "(Listener)";
    return `${displayName || "Player"} ${roleLabel}`;
  };

  // Get game state for data attributes
  const block_num = round?.get("block_num");
  const target_num = round?.get("target_num");
  const stageName = stage?.get("name");

  return (
    <div
      className="h-full w-full flex"
      data-testid="game-container"
      data-game-phase={phase_num || 0}
      data-game-block={block_num ?? -1}
      data-game-round={target_num ?? -1}
      data-stage-name={stageName || "unknown"}
      data-condition={condition || "unknown"}
      data-player-group={playerGroup || "unknown"}
      data-engagement-count={engagementCount}
    >
      <div className="h-full w-full flex flex-col">
        <Profile />
        <div className="h-full flex items-start justify-center overflow-y-auto">
          <Task
            round={round}
            stage={stage}
            game={game}
            player={player}
            players={players}
          />
        </div>
      </div>

      {showChat && (
        <div className="h-full w-128 border-l flex justify-center items-center">
          <Chat
            player={player}
            scope={stage}
            attribute={`${playerGroup}_chat`}
            typingAttribute={`${playerGroup}_typing`}
            groupPlayers={playersInGroup}
            customPlayerName={customPlayerName}
          />
        </div>
      )}
    </div>
  );
}
