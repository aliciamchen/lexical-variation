import { describe, it, expect } from "vitest";
import { isSendKey } from "./chat-input.js";

const key = (over = {}) => ({ key: "Enter", shiftKey: false, isComposing: false, keyCode: 13, ...over });

describe("isSendKey", () => {
  it("sends on a plain Enter", () => {
    expect(isSendKey(key())).toBe(true);
  });

  it("does not send on Shift+Enter, which makes a newline", () => {
    expect(isSendKey(key({ shiftKey: true }))).toBe(false);
  });

  it("does not send on any other key", () => {
    expect(isSendKey(key({ key: "a", keyCode: 65 }))).toBe(false);
    expect(isSendKey(key({ key: "Escape", keyCode: 27 }))).toBe(false);
  });

  // The whole reason this function exists: an IME's commit keystroke reaches
  // the page as Enter, and sending on it truncates the description mid-word.
  it("does not send while an input method editor is composing", () => {
    expect(isSendKey(key({ isComposing: true }))).toBe(false);
  });

  it("does not send on the legacy keyCode 229 composition signal", () => {
    expect(isSendKey(key({ keyCode: 229, isComposing: false }))).toBe(false);
  });

  it("sends on the Enter that follows composition, once it has ended", () => {
    expect(isSendKey(key({ isComposing: false, keyCode: 13 }))).toBe(true);
  });

  it("is safe with no event", () => {
    expect(isSendKey(undefined)).toBe(false);
  });
});
