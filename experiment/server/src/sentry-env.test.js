import { describe, it, expect } from "vitest";
import { mkdtempSync, writeFileSync } from "fs";
import { tmpdir } from "os";
import { join } from "path";
import { assertSentryDsn, readEnvFile, resolveSentryDsn } from "../../shared/sentry-env.js";

const dirWith = (content) => {
  const d = mkdtempSync(join(tmpdir(), "sentry-env-"));
  if (content !== null) writeFileSync(join(d, ".env"), content);
  return d;
};

describe("readEnvFile", () => {
  it("parses KEY=VALUE lines, quotes, comments, and export prefixes", () => {
    const d = dirWith('# comment\nEMPIRICA_SERVER=host.example.com\nVITE_SENTRY_DSN="https://abc@o1.ingest.example/1"\nexport SENTRY_ORG=\'my-org\'\n\nBROKEN LINE\n');
    expect(readEnvFile(d)).toEqual({
      EMPIRICA_SERVER: "host.example.com",
      VITE_SENTRY_DSN: "https://abc@o1.ingest.example/1",
      SENTRY_ORG: "my-org",
    });
  });
  it("returns an empty object when there is no .env", () => {
    expect(readEnvFile(dirWith(null))).toEqual({});
  });
});

describe("resolveSentryDsn", () => {
  it("prefers the shell environment over the .env file", () => {
    const d = dirWith("VITE_SENTRY_DSN=from-file\n");
    expect(resolveSentryDsn({ envDir: d, env: { VITE_SENTRY_DSN: "from-shell" } })).toBe("from-shell");
    expect(resolveSentryDsn({ envDir: d, env: {} })).toBe("from-file");
  });
});

describe("assertSentryDsn", () => {
  it("fails a production build with no DSN anywhere", () => {
    const d = dirWith("EMPIRICA_SERVER=host.example.com\n");
    expect(() => assertSentryDsn({ command: "build", envDir: d, env: {} })).toThrow(/VITE_SENTRY_DSN is not set/);
    expect(() => assertSentryDsn({ command: "build", envDir: dirWith(null), env: {} })).toThrow();
  });
  it("passes when the DSN is in the root .env or the shell", () => {
    expect(() => assertSentryDsn({ command: "build", envDir: dirWith("VITE_SENTRY_DSN=x\n"), env: {} })).not.toThrow();
    expect(() => assertSentryDsn({ command: "build", envDir: dirWith(null), env: { VITE_SENTRY_DSN: "x" } })).not.toThrow();
  });
  it("does not gate the dev server, and honors ALLOW_NO_SENTRY=1", () => {
    const d = dirWith(null);
    expect(() => assertSentryDsn({ command: "serve", envDir: d, env: {} })).not.toThrow();
    expect(() => assertSentryDsn({ command: "build", envDir: d, env: { ALLOW_NO_SENTRY: "1" } })).not.toThrow();
  });
});
