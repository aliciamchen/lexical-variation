import React from "react";
import { prolificCompletionUrl } from "../constants";

// Styled like the secondary Button, but a real link: following it in the same
// tab completes the Prolific submission and closes the experiment's websocket,
// so a finished participant stops holding a server subscription open.
const linkClass =
  "inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-empirica-600 hover:bg-empirica-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-empirica-500";

/**
 * The way back to Prolific from an exit screen: a link that submits `code`
 * through Prolific's completion URL, with the code printed underneath for a
 * participant whose link does not work.
 */
export function ProlificCompletion({ code }) {
  return (
    <div className="mt-4" data-testid="prolific-completion">
      <a
        href={prolificCompletionUrl(code)}
        className={linkClass}
        data-sentry-unmask
        data-testid="prolific-completion-link"
      >
        Return to Prolific to complete your submission
      </a>
      <p className="mt-3 text-sm">
        If the button does not work, enter this code on Prolific:{" "}
        <strong>{code}</strong>
      </p>
    </div>
  );
}
