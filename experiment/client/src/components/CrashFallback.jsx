import React from "react";
import { Alert } from "./Alert";
import { Button } from "./Button";

/**
 * Rendered by the Sentry error boundary in index.jsx when a render throws.
 *
 * Without a boundary, React unmounts the whole tree on any render error, so a
 * single bad read in one panel leaves the participant on a blank white page
 * with no idea whether the study crashed, whether they are still in the game,
 * or whether they will be paid. A reload is almost always the right move --
 * Empirica keeps a player's progress on the server, so it resumes where they
 * were -- and this is what tells them so.
 */
export function CrashFallback() {
  return (
    <div
      className="py-8 max-w-5xl mx-auto px-4 sm:px-6 lg:px-8"
      data-testid="crash-fallback"
      data-sentry-unmask
    >
      <Alert title="Something went wrong" kind="error">
        <p>
          The study hit an unexpected error in your browser. Your progress is
          saved on our server, so nothing you have done has been lost.
        </p>
        <p className="mt-2">
          Please reload the page. You will return to where you were.
        </p>
        <p className="mt-2">
          If reloading does not bring the study back, message us on Prolific
          and we will make sure you are paid for your time.
        </p>
      </Alert>
      <div className="mt-4">
        <Button handleClick={() => window.location.reload()} autoFocus>
          Reload the page
        </Button>
      </div>
    </div>
  );
}
