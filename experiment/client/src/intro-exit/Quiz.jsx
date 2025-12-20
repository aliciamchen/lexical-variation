import React, { useState } from "react";
import { Button } from "../components/Button";

export function Quiz({ next }) {
  const [answers, setAnswers] = useState({});

  const questions = [
    {
      question:
        "How many participants will play at the same time on your team, including yourself?",
      choices: ["1", "2", "4", "8"],
      correctAnswer: "4",
    },
    {
      question: "How many pictures will be shown at a time?",
      choices: ["2", "4", "6", "8"],
      correctAnswer: "6",
    },
    {
      question: "Select the true statement about the score:",
      choices: [
        "The speaker gets more points if more Listeners make the right choice.",
        "The Speaker gets more points if 1 or 2 Listeners make the right choice.",
      ],
      correctAnswer:
        "The speaker gets more points if more Listeners make the right choice.",
    },
    {
      question: "Select the true statement about the chat:",
      choices: [
        "Anyone can send messages through the chat.",
        "Only the Speaker can send messages through the chat.",
      ],
      correctAnswer: "Anyone can send messages through the chat.",
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
      alert("Some answers are incorrect. Please try again.");
    }
  };

  const radioStyle = {
    display: "block",
    margin: "8px 0",
  };

  const inputStyle = {
    marginRight: "10px",
  };

  return (
    <div>
      <h1>Comprehension Quiz</h1>
      <form>
        {questions.map((q, questionIndex) => (
          <div key={questionIndex}>
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
