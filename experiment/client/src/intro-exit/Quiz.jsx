import React, { useState } from "react";
import { usePlayer, useGame } from "@empirica/core/player/classic/react";
import { Loading } from "@empirica/core/player/react";
import { Button } from "../components/Button";
import { EXIT_REASONS, MAX_QUIZ_ATTEMPTS } from "../constants";

export function Quiz({ next }) {
  const player = usePlayer();
  const game = useGame();
  const condition = game?.get("treatment")?.condition;
  const [answers, setAnswers] = useState({});
  // Attempts are stored on the player record (not just React state) so a page
  // reload cannot reset the three-attempt limit.
  //
  // Read through a lazy initializer: the argument to useState is evaluated on
  // every render even though React keeps only the first, so a plain
  // `player.get(...)` here throws on any re-render in which the player
  // subscription is momentarily empty, and it throws inside the hook, where no
  // guard below it can help. The function form runs once, at mount, which
  // EmpiricaContext only reaches with a player present, so the persisted
  // attempt count is still read correctly.
  const [attempts, setAttempts] = useState(
    () => player?.get("quiz_attempts") || 0,
  );
  // Shown for the instant between the third failure and Empirica switching to
  // the exit steps (App.jsx routes a quiz failure to the Sorry page). A player
  // whose failure is already recorded never renders the quiz at all.
  const [failed, setFailed] = useState(false);

  // Below every hook, so the hook order cannot change between renders. See
  // Sorry.jsx for why a subscription-backed player has to be guarded at all.
  if (!player) {
    return <Loading />;
  }

  const baseQuestions = [
    {
      question: "What is the Speaker's job in each round?",
      choices: [
        "To click on the target picture as fast as possible.",
        "To describe the target picture so Listeners can identify it.",
        "To guess which picture the Listeners will choose.",
      ],
      correctAnswer:
        "To describe the target picture so Listeners can identify it.",
    },
    {
      question: "What happens if you are inactive for multiple rounds?",
      choices: [
        "Nothing, you can rejoin later.",
        "You will be removed from the game and lose your bonus.",
        "You will lose some bonus points but can continue playing.",
      ],
      correctAnswer:
        "You will be removed from the game and lose your bonus.",
    },
    {
      question: "What are you allowed to discuss in the chat?",
      choices: [
        "Anything related to the game.",
        "Only topics related to picking out the correct target picture.",
        "Personal topics to get to know your group members.",
      ],
      correctAnswer: "Only topics related to picking out the correct target picture.",
    },
    {
      question: "Select the true statement about the chat:",
      choices: [
        "Listeners can click on pictures at any time.",
        "Listeners must wait for the Speaker to send a message before they can click.",
      ],
      correctAnswer:
        "Listeners must wait for the Speaker to send a message before they can click.",
    },
    {
      question: "Select the true statement about the pictures:",
      choices: [
        "Everyone will see the same pictures in the same places in the grid.",
        "Everyone will see the same pictures, but the pictures will be mixed up and in different places for different people.",
      ],
      correctAnswer:
        "Everyone will see the same pictures, but the pictures will be mixed up and in different places for different people.",
    },
    {
      question: "Why won't descriptions like 'the one on the left' work?",
      choices: [
        "Because left and right are too vague.",
        "Because the pictures are in different positions for each player.",
        "Because you can only use one word to describe each picture.",
      ],
      correctAnswer:
        "Because the pictures are in different positions for each player.",
    },
  ];

  const questions = [...baseQuestions];

  if (condition === "social_first") {
    questions.push({
      question: "What will happen in Phase 2?",
      choices: [
        "You will stay in the same group as Phase 1.",
        "Players from all groups will be mixed together, and listeners will need to use speakers' descriptions to figure out whether they were in the same Phase 1 group.",
        "Each player will play individually without a group.",
      ],
      correctAnswer:
        "Players from all groups will be mixed together, and listeners will need to use speakers' descriptions to figure out whether they were in the same Phase 1 group.",
    });
  }

  const handleChoiceChange = (questionIndex, event) => {
    setAnswers({
      ...answers,
      [questionIndex]: event.target.value,
    });
  };

  const handleSubmit = (event) => {
    event.preventDefault();

    // Already out of attempts. Empirica clears `ended` when it reassigns a
    // player to another game in the same batch, so a player who failed three
    // times in a game that then filled without them can arrive back at the
    // quiz with their attempts spent and `ended` gone. `exitReason` survives
    // that, and is written only on a third failure, never on a pass, so it is
    // the safe test. Re-apply the exit rather than mark a fourth attempt.
    if (player.get("exitReason") === EXIT_REASONS.quizFailed) {
      setFailed(true);
      player.set("ended", EXIT_REASONS.quizFailed);
      return;
    }

    const allCorrect = questions.every(
      (q, index) => answers[index] === q.correctAnswer
    );

    // Attempts taken, recorded on both paths. Writing it only on failure made
    // the value mean "failed attempts" and left it empty for everyone who
    // passed first time, which is most participants: empty was then ambiguous
    // between "passed first try" and "this export predates the field", and
    // attrition.R's mean over the non-missing values silently excluded every
    // first-try pass. A first-try pass is 1.
    const attemptsTaken = attempts + 1;
    setAttempts(attemptsTaken);
    player.set("quiz_attempts", attemptsTaken);

    if (allCorrect) {
      alert("Congratulations, you answered all questions correctly!");
      next();
    } else {
      const newAttempts = attemptsTaken;

      if (newAttempts >= MAX_QUIZ_ATTEMPTS) {
        setFailed(true);
        player.set("exitReason", EXIT_REASONS.quizFailed);
        // Formally exit: Empirica excludes players with `ended` set from the
        // game's ready count and never reassigns them to another game. The
        // participant is routed to the Sorry page (quiz-failed message).
        player.set("ended", EXIT_REASONS.quizFailed);
      } else {
        alert(
          `Some answers are incorrect. You have ${
            MAX_QUIZ_ATTEMPTS - newAttempts
          } attempt(s) remaining. Please try again.`
        );
      }
    }
  };

  const radioStyle = {
    display: "block",
    margin: "8px 0",
  };

  const inputStyle = {
    marginRight: "10px",
  };

  // Show failure screen after 3 failed attempts
  if (failed) {
    return (
      <div
        className="py-8 max-w-5xl mx-auto px-4 sm:px-6 lg:px-8"
        data-testid="quiz-failed-screen"
        data-exit-reason="quiz_failed"
      >
        <div
          style={{
            padding: "20px",
            backgroundColor: "#fee2e2",
            border: "1px solid #ef4444",
            borderRadius: "8px",
            marginBottom: "20px",
          }}
        >
          <h2 style={{ color: "#dc2626", marginBottom: "10px" }}>
            Quiz Failed
          </h2>
          <p>
            Unfortunately, you have used all {MAX_QUIZ_ATTEMPTS} attempts and were
            not able to pass the comprehension quiz. You will not be able to
            participate in this study.
          </p>
          <p style={{ marginTop: "10px" }}>
            Please return this study on Prolific so another participant can take
            your place.
          </p>
          <p style={{ marginTop: "10px" }}>
            Thank you for your interest in our study.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div>
      <h1>Comprehension Quiz</h1>
      <p style={{ marginBottom: "20px", color: "#666" }}>
        Attempt {attempts + 1} of {MAX_QUIZ_ATTEMPTS}
      </p>
      <form>
        {questions.map((q, questionIndex) => (
          <div key={questionIndex} style={{ marginBottom: "20px" }}>
            <h2>{q.question}</h2>
            {q.choices.map((choice, index) => (
              <label key={index} style={radioStyle}>
                <input
                  type="radio"
                  style={inputStyle}
                  name={`question-${questionIndex}`}
                  value={choice}
                  checked={answers[questionIndex] === choice}
                  onChange={(e) => handleChoiceChange(questionIndex, e)}
                />
                {choice}
              </label>
            ))}
          </div>
        ))}
        <br></br>
        <Button handleClick={handleSubmit}>Submit</Button>
      </form>
    </div>
  );
}
