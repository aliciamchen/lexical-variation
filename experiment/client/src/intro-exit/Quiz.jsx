import React, { useState } from "react";
import { Button } from "../components/Button";

export function Quiz({ next }) {
  const [answers, setAnswers] = useState({});
  const [attempts, setAttempts] = useState(0);
  const [failed, setFailed] = useState(false);

  const MAX_ATTEMPTS = 3;

  const questions = [
    {
      question:
        "How many participants will be in your group, including yourself?",
      choices: ["2", "3", "4", "9"],
      correctAnswer: "3",
    },
    {
      question: "How many pictures will be shown at a time?",
      choices: ["2", "4", "6", "8"],
      correctAnswer: "6",
    },
    {
      question: "In each trial, how many players are Listeners?",
      choices: ["1", "2", "3", "4"],
      correctAnswer: "2",
    },
    {
      question: "Select the true statement about scoring:",
      choices: [
        "Listeners earn 2 points for correct selections; Speakers earn 1 point per correct listener.",
        "Speakers earn 3 points for each correct listener; Listeners earn 1 point.",
        "Everyone earns the same points regardless of role.",
      ],
      correctAnswer:
        "Listeners earn 2 points for correct selections; Speakers earn 1 point per correct listener.",
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
  ];

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
      next();
    } else {
      const newAttempts = attempts + 1;
      setAttempts(newAttempts);

      if (newAttempts >= MAX_ATTEMPTS) {
        setFailed(true);
      } else {
        alert(
          `Some answers are incorrect. You have ${MAX_ATTEMPTS - newAttempts} attempt(s) remaining. Please try again.`
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
      <div className="py-8 max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
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
            Unfortunately, you have used all {MAX_ATTEMPTS} attempts and were not able to
            pass the comprehension quiz. You will not be able to participate in
            this study.
          </p>
          <p style={{ marginTop: "10px" }}>
            Please submit the following code on Prolific to receive partial
            compensation for your time: <strong>QUIZFAIL2024</strong>
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
