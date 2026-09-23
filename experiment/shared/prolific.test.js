import { describe, expect, it } from "vitest";
import { PROLIFIC_CODES, prolificCompletionUrl } from "./constants.js";

// The three completion URLs configured on the Prolific study. If a code is
// rotated in constants.js, the study's completion paths must change with it.
describe("prolificCompletionUrl", () => {
  it("builds the finished-game completion URL", () => {
    expect(prolificCompletionUrl(PROLIFIC_CODES.completion)).toBe(
      "https://app.prolific.com/submissions/complete?cc=C2I8XDMC",
    );
  });

  it("builds the lobby-timeout completion URL", () => {
    expect(prolificCompletionUrl(PROLIFIC_CODES.lobbyTimeout)).toBe(
      "https://app.prolific.com/submissions/complete?cc=CMZUY3MK",
    );
  });

  it("builds the partial-payment completion URL", () => {
    expect(prolificCompletionUrl(PROLIFIC_CODES.partial)).toBe(
      "https://app.prolific.com/submissions/complete?cc=CFTYDMIY",
    );
  });

  it("escapes a code that is not URL-safe", () => {
    expect(prolificCompletionUrl("A B&C")).toBe(
      "https://app.prolific.com/submissions/complete?cc=A%20B%26C",
    );
  });
});
