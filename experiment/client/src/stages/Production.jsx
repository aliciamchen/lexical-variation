import React, { useEffect } from "react";
import { Tangram } from "../components/Tangram.jsx";

// Participants are asked to
// generate the best labels for inducing a particular audience (a member of their ‘own’ group or a member of the
//     ‘other’ group) to make one of two inferences (the ‘referential’ goal of choosing which tangram is being referred
//     to, or the ‘social’ goal of being identified as a member of the audience group).
export function Production(props) {
  const { round, stage, game, player, players } = props;
  const [description, setDescription] = React.useState("");

  const playerGroup = player.get("group");
  const playersInGroup = players.filter((p) => p.get("group") === playerGroup);
  const otherPlayersInGroup = playersInGroup.filter((p) => p.id !== player.id);
  const playersInOtherGroup = players.filter(
    (p) => p.get("group") !== playerGroup
  );

  // Make sure to reset the description when the stage changes
  useEffect(() => {
    setDescription("");
  }, [stage]);

  // Render player status indicator
  const renderPlayer = (p, self = false) => {
    return (
      <div className="player" key={p.id}>
        <span className="image">
          {p.get("avatar") && <img src={p.get("avatar")} alt="Player avatar" />}
        </span>
        <span className="name" style={{ color: p.get("name_color") || "#000" }}>
          {p.get("name") || `Player ${p.index}`}
          {self
            ? " (You)"
            : ""}
        </span>
      </div>
    );
  };

  const target = player.stage.get("target");
  const condition = player.stage.get("condition");

  let prompt;
  if (condition == "refer own") {
    prompt = (
      <>
        Please write a description to help a member of{" "}
        <span style={{ fontWeight: "bold" }}>your own</span> group{" "}
        <span style={{ fontWeight: "bold" }}>pick the correct picture</span>.
      </>
    );
  } else if (condition == "refer other") {
    prompt = (
      <>
        Please write a description to help a player{" "}
        <span style={{ fontWeight: "bold" }}>not in your</span> group{" "}
        <span style={{ fontWeight: "bold" }}>pick the correct picture</span>.
      </>
    );
  } else if (condition == "social own") {
    prompt = (
      <>
        Please write a description of the target picture, to help a member of{" "}
        <span style={{ fontWeight: "bold" }}>your own</span> group{" "}
        <span style={{ fontWeight: "bold" }}>
          identify you as a member of their group
        </span>
        .
      </>
    );
  }

  const shuffled_tangrams = player.get("shuffled_tangrams");

  let tangramsToRender;
  if (shuffled_tangrams) {
    tangramsToRender = shuffled_tangrams.map((tangram, i) => (
      <Tangram
        key={tangram}
        tangram={tangram}
        tangram_num={i}
        round={round}
        stage={stage}
        game={game}
        player={player}
        players={players}
        target={target}
      />
    ));
  }

  const handleSubmit = (e) => {
    e.preventDefault();
    player.stage.set("utterance", description);
    player.stage.set("submit", true);
  };

  if (player.stage.get("submit")) {
    return (
      <div className="task">
        <div className="board">
          <div className="prompt-container">
            <p className="instruction-prompt">Waiting for other players...</p>
          </div>
        </div>
      </div>
    );
  }
  return (
    <div className="task">
      <div className="board">
        <div className="trial-info">
          Trial {stage.get("trial_num") + 1} out of 18
        </div>

        <div className="prompt-container">
          <p className="instruction-prompt">{prompt}</p>
        </div>
        <div className="status">
          <div className="players card" style={{width: "60%"}}>
            <h3 style={{ textAlign: "center", marginBottom: "10px" }}>
              {condition.includes("own") ? "Your Group" : "Other Players"}
            </h3>
            <div
              className="player-group"
              style={{
                display: "flex",
                justifyContent: "center",
                alignItems: "center",
                flexWrap: "wrap",
              }}
            >
              {condition.includes("own") ? renderPlayer(player, true) : ""}
              {condition.includes("own")
                ? otherPlayersInGroup.map((p) => renderPlayer(p))
                : playersInOtherGroup.map((p) => renderPlayer(p))}
            </div>
          </div>
        </div>
      </div>
      <div className="all-tangrams">
        <div className="tangrams grid">{tangramsToRender}</div>
      </div>

      <div className="description-container">
        <form onSubmit={handleSubmit}>
          <textarea
            className="description-input"
            placeholder="Write your description here..."
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={4}
            required
          />
          <div className="submit-container">
            <button
              type="submit"
              className="submit-button"
              disabled={!description.trim()}
            >
              Submit Description
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
