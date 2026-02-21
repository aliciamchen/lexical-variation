import { usePlayer } from "@empirica/core/player/classic/react";
import React, { useState } from "react";
import { Alert } from "../components/Alert";
import { Button } from "../components/Button";
import { BASE_PAY } from "../constants";

export function ExitSurvey({ next }) {
  const labelClassName = "block text-sm font-medium text-gray-700 my-2";
  const inputClassName =
    "appearance-none block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-empirica-500 focus:border-empirica-500 sm:text-sm";
  const player = usePlayer();

  const [age, setAge] = useState("");
  const [gender, setGender] = useState("");
  const [strength, setStrength] = useState("");
  const [fair, setFair] = useState("");
  const [feedback, setFeedback] = useState("");
  const [education, setEducation] = useState("");
  const [understood, setUnderstood] = useState("");

  // Use exitReason (our custom attribute) first — Empirica can overwrite
  // "ended" to "game ended" when the game finishes, clobbering our value.
  const endedReason = player.get("exitReason") || player.get("ended");
  const isDisbanded =
    endedReason === "group disbanded" ||
    endedReason === "low accuracy" ||
    endedReason === "insufficient groups after accuracy check";

  // Get player's score and bonus
  const score = player.get("score") || 0;
  const bonus = player.get("bonus") || 0;

  // Partial pay info for disbanded players
  const partialPay = player.get("partialPay");
  const partialBasePay = player.get("partialBasePay");
  const partialBonus = player.get("partialBonus");
  const minutesSpent = player.get("minutesSpent");

  const [submitted, setSubmitted] = useState(false);

  function handleSubmit(event) {
    event.preventDefault();
    player.set("exitSurvey", {
      age,
      gender,
      strength,
      fair,
      feedback,
      education,
      understood,
    });
    if (isDisbanded) {
      // Go directly to Sorry page which shows the code
      next();
    } else {
      setSubmitted(true);
    }
  }

  function handleEducationChange(e) {
    setEducation(e.target.value);
  }

  function handleUnderstoodChange(e) {
    setUnderstood(e.target.value);
  }

  if (submitted) {
    return (
      <div className="py-8 max-w-5xl mx-auto px-4 sm:px-6 lg:px-8" data-testid="exit-survey" data-ended-reason={endedReason || "game ended"}>
        <Alert title="Thank you!">
          <p>
            You earned <strong>{score} points</strong> for a bonus of{" "}
            <strong>${bonus.toFixed(2)}</strong>.
          </p>
          <p className="mt-2">
            Your base pay is <strong>${BASE_PAY.toFixed(2)}</strong>, so your
            total compensation is{" "}
            <strong>${(BASE_PAY + bonus).toFixed(2)}</strong>.
          </p>
          <p className="mt-2">
            Please submit the following code on Prolific to receive your payment:{" "}
            <strong>C2I8XDMC</strong>.
          </p>
        </Alert>
        <div className="mt-8">
          <Button handleClick={() => next()}>Finish</Button>
        </div>
      </div>
    );
  }

  // Build the header alert based on whether game ended normally or was disbanded
  let headerAlert;
  if (isDisbanded) {
    const payAmount = partialPay != null ? partialPay.toFixed(2) : "0.00";
    const basePayAmount = partialBasePay != null ? partialBasePay.toFixed(2) : "0.00";
    const bonusAmount = partialBonus != null ? partialBonus.toFixed(2) : "0.00";
    const timeMsg = minutesSpent != null ? `${minutesSpent} minutes` : "your time";

    let explanation;
    if (endedReason === "group disbanded") {
      explanation = (
        <p>
          Unfortunately, too many members of your original group left the game, and we were
          unable to continue the experiment with the remaining players.
        </p>
      );
    } else if (endedReason === "low accuracy") {
      explanation = (
        <p>
          Unfortunately, your group's accuracy during Phase 1 was below the threshold required
          to continue to Phase 2.
        </p>
      );
    } else {
      explanation = (
        <p>
          Unfortunately, too many groups did not meet the accuracy threshold during Phase 1,
          and we were unable to continue the experiment.
        </p>
      );
    }

    headerAlert = (
      <Alert title="Game Ended Early">
        {explanation}
        <p className="mt-2">
          This is not your fault - we apologize for the inconvenience. You will receive
          compensation of <strong>${payAmount}</strong> (${basePayAmount} base + ${bonusAmount} bonus)
          for {timeMsg} spent.
        </p>
        <p className="mt-2">
          Please complete this survey to receive your Prolific completion code.
        </p>
      </Alert>
    );
  } else {
    headerAlert = (
      <Alert title="Game Complete!">
        <p>
          You earned <strong>{score} points</strong> for a bonus of{" "}
          <strong>${bonus.toFixed(2)}</strong>.
        </p>
        <p className="mt-2">
          Your base pay is <strong>${BASE_PAY.toFixed(2)}</strong>, so your
          total compensation is{" "}
          <strong>${(BASE_PAY + bonus).toFixed(2)}</strong>.
        </p>
        <p className="mt-2">
          Please complete this survey to receive your Prolific completion code.
        </p>
      </Alert>
    );
  }

  return (
    <div className="py-8 max-w-5xl mx-auto px-4 sm:px-6 lg:px-8" data-testid="exit-survey" data-ended-reason={endedReason || "game ended"}>
      {headerAlert}

      <form
        className="mt-12 space-y-8 divide-y divide-gray-200"
        onSubmit={handleSubmit}
      >
        <div className="space-y-8 divide-y divide-gray-200">
          <div>
            <div>
              <h3 className="text-lg leading-6 font-medium text-gray-900">
                Exit Survey
              </h3>
              <p className="mt-1 text-sm text-gray-500">
                Thank you for participating in the study! Please answer the
                following short survey. Please be honest, your responses will
                not affect your pay in any way. You do not have to provide any
                information you feel uncomfortable with.
              </p>
            </div>

            <div className="space-y-8 mt-6">
              <div className="flex flex-row">
                <div>
                  <label htmlFor="email" className={labelClassName}>
                    Age
                  </label>
                  <div className="mt-1">
                    <input
                      id="age"
                      name="age"
                      type="number"
                      autoComplete="off"
                      className={inputClassName}
                      value={age}
                      onChange={(e) => setAge(e.target.value)}
                    />
                  </div>
                </div>
                <div className="ml-5">
                  <label htmlFor="email" className={labelClassName}>
                    Gender
                  </label>
                  <div className="mt-1">
                    <input
                      id="gender"
                      name="gender"
                      autoComplete="off"
                      className={inputClassName}
                      value={gender}
                      onChange={(e) => setGender(e.target.value)}
                    />
                  </div>
                </div>
              </div>

              <div>
                <label className={labelClassName}>
                  Highest Education Qualification
                </label>
                <div className="grid gap-2">
                  <Radio
                    selected={education}
                    name="education"
                    value="high-school"
                    label="High School"
                    onChange={handleEducationChange}
                  />
                  <Radio
                    selected={education}
                    name="education"
                    value="bachelor"
                    label="US Bachelor's Degree"
                    onChange={handleEducationChange}
                  />
                  <Radio
                    selected={education}
                    name="education"
                    value="master"
                    label="Master's or higher"
                    onChange={handleEducationChange}
                  />
                  <Radio
                    selected={education}
                    name="education"
                    value="other"
                    label="Other"
                    onChange={handleEducationChange}
                  />
                </div>
              </div>

              <div>
                <label className={labelClassName}>
                  Did you understand the instructions?
                </label>
                <div className="grid gap-2">
                  <Radio
                    selected={understood}
                    name="understood"
                    value="yes"
                    label="Yes"
                    onChange={handleUnderstoodChange}
                  />
                  <Radio
                    selected={understood}
                    name="understood"
                    value="no"
                    label="No"
                    onChange={handleUnderstoodChange}
                  />
                </div>
              </div>

              <div className="grid grid-cols-3 gap-x-6 gap-y-3">
                <label className={labelClassName}>
                  How would you describe your strategy in the game?
                </label>

                <label className={labelClassName}>
                  Do you feel the pay was fair?
                </label>

                <label className={labelClassName}>
                  Feedback, including problems you encountered.
                </label>

                <textarea
                  className={inputClassName}
                  dir="auto"
                  id="strength"
                  name="strength"
                  rows={4}
                  value={strength}
                  onChange={(e) => setStrength(e.target.value)}
                />

                <textarea
                  className={inputClassName}
                  dir="auto"
                  id="fair"
                  name="fair"
                  rows={4}
                  value={fair}
                  onChange={(e) => setFair(e.target.value)}
                />

                <textarea
                  className={inputClassName}
                  dir="auto"
                  id="feedback"
                  name="feedback"
                  rows={4}
                  value={feedback}
                  onChange={(e) => setFeedback(e.target.value)}
                />
              </div>

              <div className="mb-12">
                <Button type="submit">Submit</Button>
              </div>
            </div>
          </div>
        </div>
      </form>
    </div>
  );
}

export function Radio({ selected, name, value, label, onChange }) {
  return (
    <label className="text-sm font-medium text-gray-700">
      <input
        className="mr-2 shadow-sm sm:text-sm"
        type="radio"
        name={name}
        value={value}
        checked={selected === value}
        onChange={onChange}
      />
      {label}
    </label>
  );
}
