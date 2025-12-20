import React, { useState, useEffect } from "react";
import { Tangram } from "../components/Tangram.jsx";

export function Comprehension(props) {
  const { round, stage, game, player, players } = props;
  const target = player.stage.get("target");

  // participnats can freely select the tangram before submitting
  const [clickedTangram, setClickedTangram] = useState(
    player.stage.get("clicked_tangram")
  );
  useEffect(() => {
    setClickedTangram(player.stage.get("clicked_tangram"));
  }, [player.stage.get("clicked_tangram")]);

  const handleTangramClick = (tangram) => {
    player.stage.set("clicked_tangram", tangram);
    setClickedTangram(tangram);
  };

  // and freely select the group
  const [clickedGroup, setClickedGroup] = useState(null);
  const handleGroupClick = (group) => {
    setClickedGroup(group);
  };

  // if both are selected, then submit
  const handleSubmit = () => {
    if (clickedTangram && clickedGroup) {
      player.stage.set("clicked_tangram", clickedTangram);
      const selected_group = clickedGroup === "yes" ? player.get("group") : player.get("other_group");
      const ingroup = clickedGroup === "yes" ? "ingroup" : "outgroup";
      player.stage.set("clicked_group", selected_group);
      player.stage.set("clicked_ingroup", ingroup);

      player.stage.set("correctTangram", clickedTangram === target);
      player.stage.set("correctGroup", selected_group === player.stage.get("speaker_group"));
      player.stage.set("submit", true);
    }
  };

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
        onSelect={handleTangramClick}
      />
    ));
  }

  // Define the prompt
  const prompt = (
    <div>
      <p className="instruction-prompt">
        Speaker's description:{" "}
        <span
          style={{
            fontStyle: "italic",
            backgroundColor: "#f5f5f5",
            padding: "4px 8px",
            borderRadius: "4px",
            marginLeft: "8px",
            display: "inline-block",
            wordBreak: "break-word",
            maxWidth: "100%",
            overflowWrap: "break-word"
          }}
        >
          {player.stage.get("description")}
        </span>
      </p>
      <p className="instruction-prompt" style={{ marginTop: "15px" }}>
        Please select which picture you think they were describing.
      </p>
    </div>
  );

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
          Trial {stage.get("trial_num") + 1} out of 36
        </div>
        <div className="prompt-container">{prompt}</div>
      </div>
      <div className="all-tangrams">
        <div className="tangrams grid">{tangramsToRender}</div>
      </div>
      
      <div className="group-question" style={{ marginTop: "20px", textAlign: "center" }}>
        <p className="instruction-prompt">Please select which group you think the speaker was in.</p>
        <div className="group-options" style={{ margin: "15px 0" }}>
          <button 
            className={`group-option ${clickedGroup === "yes" ? "selected" : ""}`}
            onClick={() => handleGroupClick("yes")}
            style={{ 
              margin: "0 10px", 
              padding: "8px 16px", 
              backgroundColor: clickedGroup === "yes" ? "#4CAF50" : "#f5f5f5",
              color: clickedGroup === "yes" ? "white" : "black",
              border: "1px solid #ddd",
              borderRadius: "4px",
              cursor: "pointer"
            }}
          >
            The speaker was a member of my group
          </button>
          <button 
            className={`group-option ${clickedGroup === "no" ? "selected" : ""}`}
            onClick={() => handleGroupClick("no")}
            style={{ 
              margin: "0 10px", 
              padding: "8px 16px", 
              backgroundColor: clickedGroup === "no" ? "#4CAF50" : "#f5f5f5",
              color: clickedGroup === "no" ? "white" : "black",
              border: "1px solid #ddd",
              borderRadius: "4px",
              cursor: "pointer"
            }}
          >
            The speaker was a member of another group
          </button>
        </div>
      </div>
      
      <div className="submit-container" style={{ marginTop: "20px", textAlign: "center" }}>
        <button 
          onClick={handleSubmit}
          disabled={!clickedTangram || !clickedGroup}
          style={{
            padding: "10px 20px",
            fontSize: "16px",
            backgroundColor: clickedTangram && clickedGroup ? "#2196F3" : "#cccccc",
            color: "white",
            border: "none",
            borderRadius: "4px",
            cursor: clickedTangram && clickedGroup ? "pointer" : "not-allowed",
            opacity: clickedTangram && clickedGroup ? 1 : 0.7,
          }}
        >
          Submit
        </button>
      </div>
    </div>
  );
}
