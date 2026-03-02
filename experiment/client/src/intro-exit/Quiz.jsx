import React, { useState } from "react";
import { usePlayer, useGame } from "@empirica/core/player/classic/react";
import { Button } from "../components/Button";

export function Quiz({ next }) {
  const player = usePlayer();
  const game = useGame();
  const condition = game?.get("treatment")?.condition;
  const [answers, setAnswers] = useState({});
  const [attempts, setAttempts] = useState(0);
  const [failed, setFailed] = useState(
    player.get("exitReason") === "quiz failed"
  );

  const MAX_ATTEMPTS = 3;

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
        "You will be removed from the game and will not receive your pay.",
        "You will lose some bonus points but can continue playing.",
      ],
      correctAnswer:
        "You will be removed from the game and will not receive your pay.",
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

  if (condition === "exp2_refer_goal") {
    questions.push({
      question: "What will happen in Phase 2?",
      choices: [
        "You will stay in the same group as Phase 1.",
        "Players from all groups will be mixed together.",
        "Each player will play individually without a group.",
      ],
      correctAnswer: "Players from all groups will be mixed together.",
    });
  } else if (condition === "exp2_social_goal") {
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

    const allCorrect = questions.every(
      (q, index) => answers[index] === q.correctAnswer
    );

    if (allCorrect) {
      alert("Congratulations, you answered all questions correctly!");
      // Clear any prior quiz failure so it doesn't poison the exit flow
      if (player.get("exitReason") === "quiz failed") {
        player.set("exitReason", null);
      }
      next();
    } else {
      const newAttempts = attempts + 1;
      setAttempts(newAttempts);

      if (newAttempts >= MAX_ATTEMPTS) {
        setFailed(true);
        player.set("exitReason", "quiz failed");
      } else {
        alert(
          `Some answers are incorrect. You have ${
            MAX_ATTEMPTS - newAttempts
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
            Unfortunately, you have used all {MAX_ATTEMPTS} attempts and were
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
        Attempt {attempts + 1} of {MAX_ATTEMPTS}
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
