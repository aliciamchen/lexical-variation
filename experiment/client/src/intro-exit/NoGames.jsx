import React from "react";
import { Alert } from "../components/Alert";

/**
 * Shown when Empirica has no game for this participant: either every place in
 * the session has been taken, or no batch is running yet.
 *
 * Empirica's built-in screen says "There are currently no available
 * experiments ... come back at a later date", which gives a Prolific
 * participant nothing to act on: no completion code, no instruction, and no
 * record of them anywhere (they never register a player, so they appear in no
 * export and the payment tooling cannot find them). Left alone they wait, or
 * their submission is auto-approved at the full study reward. The policy here
 * is to ask them to return the submission, which costs them nothing and frees
 * the place.
 *
 * The copy has to serve the early arrival as well as the late one, because
 * `experimentOpen` is also false before the session's batch is created.
 */
export function NoGames() {
  return (
    <div
      className="py-8 max-w-5xl mx-auto px-4 sm:px-6 lg:px-8"
      data-testid="no-games-screen"
      data-sentry-unmask
    >
      <Alert title="This session is full">
        <p>
          Every place in this session has already been taken, so there is no
          game left for you to join. We are sorry for the wasted trip.
        </p>
        <p className="mt-2">
          Please return your submission on Prolific. Returning a study does not
          count against you.
        </p>
        <p className="mt-2">
          If you are early and the session has not started yet, wait a moment
          and reload this page before returning.
        </p>
      </Alert>
    </div>
  );
}
