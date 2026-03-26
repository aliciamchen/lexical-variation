import { usePlayer, useGame } from "@empirica/core/player/classic/react";
import React, { useState } from "react";
import { Alert } from "../components/Alert";
import { Button } from "../components/Button";
import { BASE_PAY } from "../constants";

export function ExitSurvey({ next }) {
  const labelClassName = "block text-sm font-medium text-gray-700 my-2";
  const inputClassName =
    "appearance-none block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-empirica-500 focus:border-empirica-500 sm:text-sm";
  const player = usePlayer();
  const game = useGame();
  const condition = game?.get("treatment")?.condition;
  const groupLabel = condition === "refer_separated" ? "your group" : "your Phase 1 group";

  // Required fields
  const [understood, setUnderstood] = useState("");
  const [groupIdentification, setGroupIdentification] = useState("");
  const [groupCloseness, setGroupCloseness] = useState("");
  const [groupLanguage, setGroupLanguage] = useState("");
  const [strategy, setStrategy] = useState("");
  const [feltHuman, setFeltHuman] = useState("");

  // Optional fields
  const [age, setAge] = useState("");
  const [gender, setGender] = useState("");
  const [education, setEducation] = useState("");
  const [fair, setFair] = useState("");
  const [feedback, setFeedback] = useState("");

  // "required" = page 1 done, "optional" = page 2 done
  const [page, setPage] = useState("required");

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

  const requiredComplete =
    understood &&
    groupIdentification &&
    groupCloseness &&
    groupLanguage &&
    strategy.trim();

  function handleRequiredSubmit(event) {
    event.preventDefault();
    if (!requiredComplete) return;
    player.set("exitSurvey", {
      understood,
      groupIdentification,
      groupCloseness,
      groupLanguage,
      strategy,
    });
    if (isDisbanded) {
      next();
    } else {
      setPage("optional");
    }
  }

  const page2RequiredComplete = feltHuman && age && gender;

  function handleOptionalSubmit(event) {
    event.preventDefault();
    if (!page2RequiredComplete) return;
    player.set("exitSurvey", {
      ...player.get("exitSurvey"),
      feltHuman,
      age,
      gender,
      education,
      fair,
      feedback,
    });
    setPage("done");
  }

  // Build the header alert based on whether game ended normally or was disbanded
  let headerAlert;
  if (isDisbanded) {
    const payAmount = partialPay != null ? partialPay.toFixed(2) : "0.00";
    const basePayAmount =
      partialBasePay != null ? partialBasePay.toFixed(2) : "0.00";
    const bonusAmount = partialBonus != null ? partialBonus.toFixed(2) : "0.00";
    const timeMsg =
      minutesSpent != null ? `${minutesSpent} minutes` : "your time";

    let explanation;
    if (endedReason === "group disbanded") {
      explanation = (
        <p>
          Unfortunately, too many members of your original group left the game,
          and we were unable to continue the experiment with the remaining
          players.
        </p>
      );
    } else if (endedReason === "low accuracy") {
      explanation = (
        <p>
          Unfortunately, your group's accuracy during Phase 1 was below the
          threshold required to continue to Phase 2.
        </p>
      );
    } else {
      explanation = (
        <p>
          Unfortunately, too many groups did not meet the accuracy threshold
          during Phase 1, and we were unable to continue the experiment.
        </p>
      );
    }

    headerAlert = (
      <Alert title="Game Ended Early">
        {explanation}
        <p className="mt-2">
          This is not your fault - we apologize for the inconvenience. You will
          receive compensation of <strong>${payAmount}</strong> ($
          {basePayAmount} base + ${bonusAmount} bonus) for {timeMsg} spent.
        </p>
        <p className="mt-2">
          Please complete this survey to receive your Prolific completion code.
          When you submit the code, Prolific will ask you to return your study.
          This is so that you don't get penalized; we will still send you your
          pay.
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

  // Page 3: Confirmation with Prolific code
  if (page === "done") {
    return (
      <div
        className="py-8 max-w-5xl mx-auto px-4 sm:px-6 lg:px-8"
        data-testid="exit-survey"
        data-ended-reason={endedReason || "game ended"}
      >
        <Alert title="Thank you!">
          <p>
            Just so you know: you were always playing with real humans
            throughout the game.
          </p>
          <p className="mt-2">
            You earned <strong>{score} points</strong> for a bonus of{" "}
            <strong>${bonus.toFixed(2)}</strong>.
          </p>
          <p className="mt-2">
            Your base pay is <strong>${BASE_PAY.toFixed(2)}</strong>, so your
            total compensation is{" "}
            <strong>${(BASE_PAY + bonus).toFixed(2)}</strong>.
          </p>
          <p className="mt-2">
            Please submit the following code on Prolific to receive your
            payment: <strong>C2I8XDMC</strong>.
          </p>
        </Alert>
        <div className="mt-8">
          <Button handleClick={() => next()}>Finish</Button>
        </div>
      </div>
    );
  }

  // Page 2: Optional questions
  if (page === "optional") {
    return (
      <div
        className="py-8 max-w-5xl mx-auto px-4 sm:px-6 lg:px-8"
        data-testid="exit-survey"
        data-ended-reason={endedReason || "game ended"}
      >
        <form
          className="mt-12 space-y-8 divide-y divide-gray-200"
          onSubmit={handleOptionalSubmit}
        >
          <div className="space-y-8 divide-y divide-gray-200">
            <div>
              <div>
                <h3 className="text-lg leading-6 font-medium text-gray-900">
                  Exit survey (page 2)
                </h3>
              </div>

              <div className="space-y-8 mt-6">
                <div className="flex flex-row">
                  <div>
                    <label htmlFor="age" className={labelClassName}>
                      Age <span className="text-red-500">*</span>
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
                    <label htmlFor="gender" className={labelClassName}>
                      Gender <span className="text-red-500">*</span>
                    </label>
                    <div className="mt-1">
                      <select
                        id="gender"
                        name="gender"
                        className={inputClassName}
                        value={gender}
                        onChange={(e) => setGender(e.target.value)}
                      >
                        <option value="">-- Select --</option>
                        <option value="male">Male</option>
                        <option value="female">Female</option>
                        <option value="non-binary">Non-binary</option>
                        <option value="other">Other</option>
                        <option value="prefer-not-to-say">
                          Prefer not to say
                        </option>
                      </select>
                    </div>
                  </div>
                </div>

                <div>
                  <label className={labelClassName}>
                    Did you feel like you were playing with other humans? <span className="text-red-500">*</span>
                  </label>
                  <div className="grid gap-2">
                    <Radio
                      selected={feltHuman}
                      name="feltHuman"
                      value="yes"
                      label="Yes"
                      onChange={(e) => setFeltHuman(e.target.value)}
                    />
                    <Radio
                      selected={feltHuman}
                      name="feltHuman"
                      value="no"
                      label="No"
                      onChange={(e) => setFeltHuman(e.target.value)}
                    />
                  </div>
                </div>

                <hr className="border-gray-300" />

                <div>
                  <label className={labelClassName}>
                    Highest education qualification
                  </label>
                  <div className="grid gap-2">
                    <Radio
                      selected={education}
                      name="education"
                      value="high-school"
                      label="High School"
                      onChange={(e) => setEducation(e.target.value)}
                    />
                    <Radio
                      selected={education}
                      name="education"
                      value="bachelor"
                      label="US Bachelor's Degree"
                      onChange={(e) => setEducation(e.target.value)}
                    />
                    <Radio
                      selected={education}
                      name="education"
                      value="master"
                      label="Master's or higher"
                      onChange={(e) => setEducation(e.target.value)}
                    />
                    <Radio
                      selected={education}
                      name="education"
                      value="other"
                      label="Other"
                      onChange={(e) => setEducation(e.target.value)}
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-x-6 gap-y-3">
                  <label className={labelClassName}>
                    Do you feel the pay was fair?
                  </label>

                  <label className={labelClassName}>
                    Feedback, including problems you encountered.
                  </label>

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
                  <Button type="submit" disabled={!page2RequiredComplete}>Submit</Button>
                </div>
              </div>
            </div>
          </div>
        </form>
      </div>
    );
  }

  // Page 1: Required questions
  return (
    <div
      className="py-8 max-w-5xl mx-auto px-4 sm:px-6 lg:px-8"
      data-testid="exit-survey"
      data-ended-reason={endedReason || "game ended"}
    >
      {headerAlert}

      <form
        className="mt-12 space-y-8 divide-y divide-gray-200"
        onSubmit={handleRequiredSubmit}
      >
        <div className="space-y-8 divide-y divide-gray-200">
          <div>
            <div>
              <h3 className="text-lg leading-6 font-medium text-gray-900">
                Exit survey
              </h3>
              <p className="mt-1 text-sm text-gray-500">
                Thank you for participating in the study! Please answer the
                following short survey. Please be honest, your responses will
                not affect your pay in any way.
              </p>
            </div>

            <div className="space-y-8 mt-6">
              <div>
                <label className={labelClassName}>
                  Did you understand the instructions? <span className="text-red-500">*</span>
                </label>
                <div className="grid gap-2">
                  <Radio
                    selected={understood}
                    name="understood"
                    value="yes"
                    label="Yes"
                    onChange={(e) => setUnderstood(e.target.value)}
                  />
                  <Radio
                    selected={understood}
                    name="understood"
                    value="no"
                    label="No"
                    onChange={(e) => setUnderstood(e.target.value)}
                  />
                </div>
              </div>

              <div>
                <label className={labelClassName}>
                  How much did you feel a sense of being a part of {groupLabel}? <span className="text-red-500">*</span>
                </label>
                <div className="flex items-center gap-2 mt-1">
                  <span className="text-sm text-gray-500">Not at all</span>
                  <div className="flex gap-3">
                    {[1, 2, 3, 4, 5, 6, 7].map((val) => (
                      <label key={val} className="flex flex-col items-center text-sm text-gray-700">
                        <input
                          type="radio"
                          name="groupIdentification"
                          value={val}
                          checked={groupIdentification === String(val)}
                          onChange={(e) => setGroupIdentification(e.target.value)}
                          className="mb-1"
                        />
                        {val}
                      </label>
                    ))}
                  </div>
                  <span className="text-sm text-gray-500">Very much</span>
                </div>
              </div>

              <div>
                <label className={labelClassName}>
                  How close did you feel to the people in {groupLabel}? <span className="text-red-500">*</span>
                </label>
                <div className="flex items-center gap-2 mt-1">
                  <span className="text-sm text-gray-500">Not at all</span>
                  <div className="flex gap-3">
                    {[1, 2, 3, 4, 5, 6, 7].map((val) => (
                      <label key={val} className="flex flex-col items-center text-sm text-gray-700">
                        <input
                          type="radio"
                          name="groupCloseness"
                          value={val}
                          checked={groupCloseness === String(val)}
                          onChange={(e) => setGroupCloseness(e.target.value)}
                          className="mb-1"
                        />
                        {val}
                      </label>
                    ))}
                  </div>
                  <span className="text-sm text-gray-500">Very much</span>
                </div>
              </div>

              <div>
                <label className={labelClassName}>
                  Did you notice your group developing its own way of describing
                  the pictures? <span className="text-red-500">*</span>
                </label>
                <div className="grid gap-2">
                  <Radio
                    selected={groupLanguage}
                    name="groupLanguage"
                    value="yes"
                    label="Yes"
                    onChange={(e) => setGroupLanguage(e.target.value)}
                  />
                  <Radio
                    selected={groupLanguage}
                    name="groupLanguage"
                    value="no"
                    label="No"
                    onChange={(e) => setGroupLanguage(e.target.value)}
                  />
                </div>
              </div>

              <div>
                <label htmlFor="strategy" className={labelClassName}>
                  What was your strategy in the game? <span className="text-red-500">*</span>
                </label>
                <textarea
                  className={inputClassName}
                  dir="auto"
                  id="strategy"
                  name="strategy"
                  rows={3}
                  value={strategy}
                  onChange={(e) => setStrategy(e.target.value)}
                />
              </div>

              <div className="mb-12">
                <Button type="submit" disabled={!requiredComplete}>Next</Button>
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
