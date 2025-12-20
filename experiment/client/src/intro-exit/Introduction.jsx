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
        In this task, you will play a series of communication tasks with other
        players. There are three different phases of the game. You should expect
        that the whole game will take approximately 60 minutes.
      </p>
      <p>
        You will receive a base pay of $12, plus a bonus of up to $10 for your
        performance in the game.
      </p>
      <p>
        Please only do this study if you will be available for the given amount
        of time, otherwise please return it. In this study, you will be
        interacting with other participants via a chat box. If you have concerns
        about the behavior of other participants or any other issues, please
        contact us via Prolific.{" "}
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
        In the first phase, you will be assigned to a group with 4 players,
        including yourself. You will play a communication game with the players
        in your group.
      </p>
      <p>
        Everyone playing the game sees the same set of 6 pictures, which will
        look something like this:
      </p>
      <div className="tangrams grid">{tangramsNoTarget}</div>
      <p>
        In each round, one of the players in the group is assigned the Speaker
        role and the others are assigned the Listener role.
      </p>
      <p>
        The Speaker sees a box secretly marking one of the pictures as the
        target:
      </p>
      <div className="tangrams grid">{tangramsWithTarget}</div>{" "}
      <p>
        The Speaker's job is to send a description of the target through the
        chatbox so that the Listeners are able to pick it out of the set. They
        can write whatever description they think will best allow the Listeners
        to identify the target. Please note that{" "}
        <b>the order of the pictures on your screen is scrambled</b>, so
        descriptions like "the one on the left" or "the third one" will not
        work. Also, please limit your description to the current target picture:{" "}
        <strong>
          do not discuss previous trials or chat about any other topics!
        </strong>
      </p>
      <p>
        After the Speaker sends a message, the Listeners read it and each click
        the picture they believe is the target. They are also allowed to respond
        by sending messages back through the chatbox until they are ready to
        make a selection. At that time, everyone will be given feedback: the
        Speaker sees which picture each of the Listeners selected, and the
        Listeners each see what the correct picture was.
      </p>
      <p>
        In each round, the Speaker communicates about each of the 6 pictures.
        Then, the Speaker role then rotates to the next player, and the next
        round begins.
      </p>
      <p>
        There are a total of 12 rounds in this phase, so each player will
        communicate about each of the 6 pictures twice.
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

  const names = ["Tima", "Sena", "Jumi", "Nesu"];

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
    {
      _id: 3,
      name: names[3],
      avatar: `instructions/savannah.png`,
      role: "listener",
    },
  ];

  return (
    <div className="mt-3 sm:mt-5 p-20">
      <h1>How to play</h1>
      <h2>Phase 1: Reference Game (continued)</h2>
      <p>
        To help you identify yourself and differentiate each other in the team,
        we will assign an icon and a name to you when the game starts (as shown
        in the following example). This also shows who has what role.
      </p>
      <div className="status">
        <div className="players card" style={{ width: "60%" }}>
          <h3 style={{ textAlign: "center", marginBottom: "10px" }}>
            Your Group | Round 1 of 12
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
        You and your teammates have 3 minutes to select an image each time. If
        you do not select an image in this time frame, you will automatically{" "}
        <strong>progress to the next stage when the time is up</strong> and will
        not get a bonus, so please stay focused.
      </p>
      <p>
        As a group, you will go through all the pictures 12 times, so each of
        the 6 pictures can appear as the target multiple times.
      </p>
      <p>
        You may communicate with your teammates through the in-game chat.
        Whatever you write will appear to your teammates. You can use the chat
        function however you like, but please note that{" "}
        <strong>
          the Speaker must send a message before Listeners can make their
          selections
        </strong>
        .
      </p>
      <p>
        Note that the game allows for simultaneous and real-time actions.{" "}
        <strong>
          If the experiment seems slow or glitchy, you can refresh the page.{" "}
        </strong>
        Each trial will only end after all the listeners have made a selection
        (or the timer runs out).
      </p>
    </div>
  );
}

export function Introduction5({ next }) {
  return (
    <div className="mt-3 sm:mt-5 p-20">
      <h1>How to play</h1>
      <h2>Scores and bonuses</h2>
      <p>
        In each task, we use "score" to evaluate the quality of the selections
        that you and your partner have made. Your total score will be calculated
        as the sum of the scores on each phase.
      </p>
      <p>
        Each time a <strong>Listener</strong> makes a correct selection, they
        get <strong>3 points</strong>.{" "}
      </p>
      <p>
        Both an incorrect selection and no selection (timing out) earn no
        points.
      </p>
      <p>
        The <strong>Speaker</strong> gets a bonus equal to{" "}
        <strong>the average</strong> of the Listeners's scores. For example, if
        all three listeners select the correct picture, the Speaker will get a
        bonus of 3 points. If two listeners select the correct picture and one
        does not, the Speaker will get a bonus of 2 points.
      </p>
      <p>
        At the end of the first phase, you will proceed to the next phases of
        the task. We will give you more information about these phases when you
        get there.
      </p>
      <p>
        There are a total of 486 points in all phases of the study. In addition
        to your base pay of $12, you will receive $0.02 per point, for a total
        bonus of up to $9.72.
      </p>
      <p>
        <strong>
          Remember, free riding is not permitted. If we detect that you are
          inactive, you will be removed from the game and will not receive your
          pay.
        </strong>
      </p>
      <p>
        After you pass the comprehension quiz, you will be put into a waiting
        lobby. When there are enough players to start the game, the game will
        begin. Please note that it might take 5-10 minutes to find enough
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
