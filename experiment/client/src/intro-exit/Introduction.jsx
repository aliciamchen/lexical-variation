import React, { useState } from "react";
import { Button } from "../components/Button";
import { Quiz } from "./Quiz";
import _ from "lodash";

export function Introduction({ next }) {
  const [currentIndex, setCurrentIndex] = useState(0);

  const instructionComponents = [
    <Introduction1 />,
    <Introduction2 />,
    <Introduction3 />,
    <Introduction4 />,
    <Introduction5 />,
    <Quiz next={next} />,
  ];

  const prevPage = () => {
    if (currentIndex > 0) {
      setCurrentIndex(currentIndex - 1);
    }
  };

  const nextPage = () => {
    if (currentIndex < instructionComponents.length - 1) {
      setCurrentIndex(currentIndex + 1);
    }
  };

  if (currentIndex === instructionComponents.length - 1) {
    return (
      <div className="instructions">
        {instructionComponents[currentIndex]}
        <div className="flex w-sw justify-center">
          <Button handleClick={prevPage} autoFocus>
            Prev
          </Button>
        </div>
      </div>
    );
  } else {
    return (
      <div className="instructions">
        {instructionComponents[currentIndex]}
        <div className="flex w-sw justify-center space-x-4">
          <Button handleClick={prevPage} autoFocus>
            Prev
          </Button>
          <Button handleClick={nextPage} autoFocus>
            Next
          </Button>
        </div>
      </div>
    );
  }
}

export function Introduction1({ next }) {
  return (
    <div className="mt-3 sm:mt-5 p-20">
      <h1>How to play</h1>
      <p>
        Please pay attention to the instructions! There is a quiz at the end. If
        your answers indicate that you have not read the instructions, you will
        not be able to continue.
      </p>
    </div>
  );
}

export function Introduction2({ next }) {
  return (
    <div className="mt-3 sm:mt-5 p-20">
      <h1>How to play</h1>
      <p>
        In this task, you will play a series of communication games with other
        players. The game has two phases. You should expect
        that the whole game will take approximately <strong>30-45 minutes</strong>.
      </p>
      <p>
        You will receive a base pay of <strong>$10</strong>, plus a bonus of up to <strong>$5.40</strong> based on your
        performance in the game.
      </p>
      <p>
        Please only do this study if you will be available for the given amount
        of time, otherwise please return it. In this study, you will be
        interacting with other participants via a chat box. If you have concerns
        about the behavior of other participants or any other issues, please
        contact us via Prolific.
      </p>
    </div>
  );
}

export function Introduction3({ next }) {
  let sampleTangrams = ["A", "B", "C", "D", "E", "F"];
  let tangramsNoTarget;
  let tangramsWithTarget;
  let sampleTarget = "C";

  tangramsNoTarget = sampleTangrams.map((tangram, index) => (
    <TangramInstructions
      key={tangram}
      tangram={tangram}
      target={"null"}
      tangram_num={index}
    />
  ));

  tangramsWithTarget = sampleTangrams.map((tangram, index) => (
    <TangramInstructions
      key={tangram}
      tangram={tangram}
      target={sampleTarget}
      tangram_num={index}
    />
  ));

  return (
    <div className="mt-3 sm:mt-5 p-20">
      <h1>How to play</h1>
      <h2>Phase 1: Reference Game</h2>
      <p>
        In the first phase, you will be assigned to a group with <strong>3 players</strong>,
        including yourself. You will play a communication game with the players
        in your group.
      </p>
      <p>
        Everyone playing the game sees the same set of 6 pictures, which will
        look something like this:
      </p>
      <div className="tangrams grid">{tangramsNoTarget}</div>
      <p>
        In each trial, one of the players in the group is assigned the <strong>Speaker</strong> role and the other two are assigned the <strong>Listener</strong> role.
      </p>
      <p>
        The Speaker sees a box secretly marking one of the pictures as the
        target:
      </p>
      <div className="tangrams grid">{tangramsWithTarget}</div>
      <p>
        The Speaker's job is to send a description of the target through the
        chatbox so that the Listeners are able to pick it out of the set. They
        can write whatever description they think will best allow the Listeners
        to identify the target. Please note that{" "}
        <strong>the order of the pictures on your screen is scrambled</strong>, so
        descriptions like "the one on the left" or "the third one" will not
        work.
      </p>
      <p>
        <strong>Important:</strong> Please limit your messages to describing the current target picture.{" "}
        <strong>Do not discuss previous trials, use codewords, or chat about any other topics!</strong>
      </p>
      <p>
        After the Speaker sends a message, the Listeners read it and each click
        the picture they believe is the target. <strong>Listeners cannot click until the Speaker sends a message.</strong> Listeners can also respond
        by sending messages back through the chatbox. At the end of each trial, everyone will be given feedback about the correct picture.
      </p>
    </div>
  );
}

export function Introduction4({ next }) {
  const renderPlayer = (p, self = false) => {
    return (
      <div className="player" key={p._id}>
        <span className="image">
          {p.avatar && <img src={p.avatar} alt="Player avatar" />}
        </span>
        <span className="name">
          {p.name || `Player ${p.index}`}
          {self
            ? " (You) (Listener)"
            : p.role === "listener"
            ? " (Listener)"
            : " (Speaker)"}
        </span>
      </div>
    );
  };

  const names = ["Repi", "Minu", "Laju"];

  const player = {
    _id: 0,
    name: names[0],
    avatar: `/instructions/aaron.png`,
    role: "listener",
  };

  const otherPlayers = [
    {
      _id: 1,
      name: names[1],
      avatar: `instructions/muhammad.png`,
      role: "speaker",
    },
    {
      _id: 2,
      name: names[2],
      avatar: `instructions/nathaniel.png`,
      role: "listener",
    },
  ];

  return (
    <div className="mt-3 sm:mt-5 p-20">
      <h1>How to play</h1>
      <h2>Phase 1: Reference Game (continued)</h2>
      <p>
        To help you identify yourself and differentiate each other in the group,
        we will assign an icon and a name to you when the game starts (as shown
        in the following example). This also shows who has what role.
      </p>
      <div className="status">
        <div className="players card" style={{ width: "60%" }}>
          <h3 style={{ textAlign: "center", marginBottom: "10px" }}>
            Your Group | Phase 1 - Block 1 of 6
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
            {renderPlayer(player, true)}
            {otherPlayers.map((p) => renderPlayer(p))}
          </div>
        </div>
      </div>
      <p>
        You and your group have <strong>45 seconds</strong> to select an image each trial. If
        you do not select an image in this time frame, you will automatically{" "}
        <strong>progress to the next stage when the time is up</strong> and will
        not get a bonus, so please stay focused.
      </p>
      <p>
        Each block consists of 6 trials (one for each picture). The Speaker role rotates each block. In Phase 1, there are <strong>6 blocks</strong>, so each player will be the Speaker for 2 blocks.
      </p>
      <p>
        <strong>Important:</strong> If you are inactive for 2 consecutive trials (no messages or selections), you will be removed from the game.
      </p>
      <p>
        Note that the game allows for simultaneous and real-time actions.{" "}
        <strong>
          If the experiment seems slow or glitchy, you can refresh the page.
        </strong>
      </p>
    </div>
  );
}

export function Introduction5({ next }) {
  return (
    <div className="mt-3 sm:mt-5 p-20">
      <h1>How to play</h1>
      <h2>Phase 2 and Scoring</h2>
      <p>
        After completing Phase 1 with your group, you will continue to Phase 2.
        Phase 2 also consists of 6 blocks. You will receive specific instructions
        about Phase 2 when you get there.
      </p>
      <h3>Scoring</h3>
      <p>
        Your performance earns you points which determine your bonus:
      </p>
      <ul style={{ marginLeft: 20 }}>
        <li>Each time a <strong>Listener</strong> correctly identifies the target, they earn <strong>2 points</strong>.</li>
        <li>The <strong>Speaker</strong> earns <strong>1 point</strong> for each Listener who correctly identifies the target.</li>
        <li>No points are awarded for incorrect selections or timeouts.</li>
      </ul>
      <p>
        At the end of the game, your total points are converted to a bonus at a rate of <strong>$0.05 per point</strong>.
      </p>
      <h3>Important Rules</h3>
      <p>
        <strong>Remember, free riding is not permitted.</strong> If we detect that you are
        inactive, you will be removed from the game and will not receive your
        full pay.
      </p>
      <p>
        After you pass the comprehension quiz, you will be put into a waiting
        lobby. When there are enough players to start the game, the game will
        begin. Please note that it might take a few minutes to find enough
        players.
      </p>
      <p>If you experience issues, please contact us on Prolific.</p>
    </div>
  );
}

export function TangramInstructions(props) {
  const { tangram, target, tangram_num } = props;
  const row = 1 + Math.floor(tangram_num / 3);
  const column = 1 + (tangram_num % 3);
  let mystyle = {
    background: "url(tangram_" + tangram + ".png)",
    backgroundSize: "cover",
    width: "17vh",
    height: "17vh",
    gridRow: row,
    gridColumn: column,
    margin: "0.8rem",
  };

  if (tangram == target) {
    _.extend(mystyle, {
      border: "10px solid black",
      zIndex: 9,
    });
  }

  return <div style={mystyle}></div>;
}
