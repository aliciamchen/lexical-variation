import { usePlayer, useGame } from "@empirica/core/player/classic/react";
import React, { useEffect, useRef, useState } from "react";
import { Alert } from "../components/Alert";
import { Button } from "../components/Button";
import {
  BASE_PAY,
  EXIT_REASONS,
  PARTIAL_PAY_SURVEY_REASONS,
  PROLIFIC_CODES,
} from "../constants";

// Which survey pages the saved answers already cover. Page 1 is the group
// questions, page 2 the demographics and the felt-human check; each is saved
// as a whole when its form is submitted, so a page counts as complete when
// every one of its required fields is present.
const page1Complete = (s) =>
  Boolean(
    s.understood &&
      s.groupIdentification &&
      s.groupCloseness &&
      s.groupLanguage &&
      (s.strategy || "").trim(),
  );
const page2Complete = (s) => Boolean(s.feltHuman && s.age && s.gender);

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
  // Collected for the RefBank reference-game standard, whose players table
  // records native language and race alongside age, gender and education
  // (https://refbank.github.io). Optional, like the rest of this page.
  const [nativeLanguage, setNativeLanguage] = useState("");
  const [race, setRace] = useState("");
  const [fair, setFair] = useState("");
  const [feedback, setFeedback] = useState("");

  // "required" = page 1 (group questions), "optional" = page 2 (demographics
  // and the felt-human check), "done" = confirmation with the completion code.
  // Every player who reaches the survey answers both pages: demographics feed
  // the attrition report and the felt-human item is an AI-use signal, so
  // removed players answer them too and are then routed to the Sorry page.
  //
  // The page is derived from what is already saved on the player rather than
  // held in React state, so a reload (or a reconnect that remounts the exit
  // steps) resumes at the first unanswered page instead of asking a completed
  // page again, and can never lose answers that were submitted.
  const saved = player.get("exitSurvey") || {};
  const page = !page1Complete(saved)
    ? "required"
    : !page2Complete(saved)
      ? "optional"
      : "done";

  // Use exitReason (our custom attribute) first: Empirica overwrites `ended`
  // with "game ended" when the game finishes and "game terminated" when the
  // admin stops the batch.
  const endedReason = player.get("exitReason") || player.get("ended");
  // Removed early through no fault of their own; paid base prorated to time
  // spent plus the bonus so far, with the partial code on the Sorry page.
  const isRemoved = PARTIAL_PAY_SURVEY_REASONS.includes(endedReason);

  // Get player's score and bonus
  const score = player.get("score") || 0;
  const bonus = player.get("bonus") || 0;

  // Partial pay info for removed players
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

  // Each submit merges into the saved object so that neither page can wipe
  // the other's answers.
  function handleRequiredSubmit(event) {
    event.preventDefault();
    if (!requiredComplete) return;
    player.set("exitSurvey", {
      ...(player.get("exitSurvey") || {}),
      understood,
      groupIdentification,
      groupCloseness,
      groupLanguage,
      strategy,
    });
  }

  const page2RequiredComplete = feltHuman && age && gender;

  function handleOptionalSubmit(event) {
    event.preventDefault();
    if (!page2RequiredComplete) return;
    player.set("exitSurvey", {
      ...(player.get("exitSurvey") || {}),
      feltHuman,
      age,
      gender,
      education,
      nativeLanguage,
      race,
      fair,
      feedback,
    });
  }

  // Removed players get their prorated pay and partial-completion code on the
  // Sorry page, so once both pages are saved they move on. Done in an effect
  // keyed on the derived page, so it also fires for a player who reloads after
  // finishing the survey; the ref stops it firing twice before Empirica
  // switches the step.
  const advancedRef = useRef(false);
  useEffect(() => {
    if (page === "done" && isRemoved && !advancedRef.current) {
      advancedRef.current = true;
      next();
    }
  }, [page, isRemoved]);

  // Build the header alert based on whether the game ended normally or the
  // player was removed early
  let headerAlert;
  if (isRemoved) {
    const payAmount = partialPay != null ? partialPay.toFixed(2) : "0.00";
    const basePayAmount =
      partialBasePay != null ? partialBasePay.toFixed(2) : "0.00";
    const bonusAmount = partialBonus != null ? partialBonus.toFixed(2) : "0.00";
    const timeMsg =
      minutesSpent != null ? `${minutesSpent} minutes` : "your time";

    let explanation;
    if (endedReason === EXIT_REASONS.groupDisbanded) {
      explanation = (
        <p>
          Unfortunately, too many members of your original group left the game,
          and we were unable to continue the experiment with the remaining
          players.
        </p>
      );
    } else if (endedReason === EXIT_REASONS.insufficientGroups) {
      explanation = (
        <p>
          Too many players in other groups left the game, so there were not
          enough groups left to continue.
        </p>
      );
    } else if (endedReason === EXIT_REASONS.lowAccuracy) {
      explanation = (
        <p>
          Unfortunately, your group's accuracy during Phase 1 was below the
          threshold required to continue to Phase 2.
        </p>
      );
    } else if (endedReason === EXIT_REASONS.gameTerminated) {
      explanation = <p>The researcher had to stop this session early.</p>;
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

  // Page 3: confirmation with the Prolific code. This is the last thing a
  // finisher sees, so it has no button: calling `next()` here would end the
  // exit steps and replace the code with Empirica's generic "Finished" page,
  // and a participant who had not yet copied the code would have no way back.
  // The code is also on `data-prolific-code` for the end-to-end tests.
  if (page === "done") {
    // Removed players are on their way to the Sorry page (see the effect above).
    if (isRemoved) return null;
    return (
      <div
        className="py-8 max-w-5xl mx-auto px-4 sm:px-6 lg:px-8"
        data-testid="exit-survey"
        data-ended-reason={endedReason || "game ended"}
        data-prolific-code={PROLIFIC_CODES.completion}
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
            payment: <strong>{PROLIFIC_CODES.completion}</strong>.
          </p>
          <p className="mt-2">
            You can close this tab once you have submitted the code.
          </p>
        </Alert>
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

                <div className="flex flex-row">
                  <div>
                    <label htmlFor="nativeLanguage" className={labelClassName}>
                      First language
                    </label>
                    <div className="mt-1">
                      <input
                        id="nativeLanguage"
                        name="nativeLanguage"
                        type="text"
                        autoComplete="off"
                        className={inputClassName}
                        placeholder="e.g. English"
                        value={nativeLanguage}
                        onChange={(e) => setNativeLanguage(e.target.value)}
                      />
                    </div>
                  </div>
                  <div className="ml-5">
                    <label htmlFor="race" className={labelClassName}>
                      Race or ethnicity
                    </label>
                    <div className="mt-1">
                      <input
                        id="race"
                        name="race"
                        type="text"
                        autoComplete="off"
                        className={inputClassName}
                        placeholder="Optional"
                        value={race}
                        onChange={(e) => setRace(e.target.value)}
                      />
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
                    {/* RefBank's categories, so the answers need no lossy
                        remapping when the data is contributed. "Some college"
                        and "less than high school" had no home in the old
                        options, so those participants had to pick something
                        inaccurate. */}
                    <Radio
                      selected={education}
                      name="education"
                      value="less-than-high-school"
                      label="Less than high school"
                      onChange={(e) => setEducation(e.target.value)}
                    />
                    <Radio
                      selected={education}
                      name="education"
                      value="high-school"
                      label="High school"
                      onChange={(e) => setEducation(e.target.value)}
                    />
                    <Radio
                      selected={education}
                      name="education"
                      value="some-college"
                      label="Some college, no degree"
                      onChange={(e) => setEducation(e.target.value)}
                    />
                    <Radio
                      selected={education}
                      name="education"
                      value="bachelors"
                      label="Bachelor's degree"
                      onChange={(e) => setEducation(e.target.value)}
                    />
                    <Radio
                      selected={education}
                      name="education"
                      value="advanced-degree"
                      label="Advanced degree (Master's, PhD, professional)"
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
