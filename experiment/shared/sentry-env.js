/**
 * Build-time guard for the Sentry DSN.
 *
 * The client reads the DSN from `import.meta.env.VITE_SENTRY_DSN`, which Vite
 * compiles into the bundle when `empirica bundle` runs on the developer's
 * machine. Nothing on the server can supply it later, so a bundle built
 * without it ships with Sentry silently disabled. The Vite config points
 * `envDir` at the repository root so the single root `.env` is the source, and
 * calls `assertSentryDsn` so a production build without a DSN fails loudly.
 * Set ALLOW_NO_SENTRY=1 to build deliberately without Sentry.
 */
import { existsSync, readFileSync } from "fs";
import { join } from "path";

/** Minimal .env parser: KEY=VALUE lines, optional quotes, # comments. */
export function readEnvFile(envDir, filename = ".env") {
  const file = join(envDir, filename);
  if (!existsSync(file)) return {};
  const out = {};
  for (const raw of readFileSync(file, "utf8").split(/\r?\n/)) {
    const line = raw.trim();
    if (!line || line.startsWith("#")) continue;
    const eq = line.indexOf("=");
    if (eq === -1) continue;
    const key = line.slice(0, eq).trim().replace(/^export\s+/, "");
    let value = line.slice(eq + 1).trim();
    if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) {
      value = value.slice(1, -1);
    }
    out[key] = value;
  }
  return out;
}

/** The DSN the build will use: shell environment first, then the root .env. */
export function resolveSentryDsn({ envDir, env = process.env }) {
  return env.VITE_SENTRY_DSN || readEnvFile(envDir).VITE_SENTRY_DSN || "";
}

/**
 * Throw if a production build has no DSN. Dev servers and test builds are
 * not gated; ALLOW_NO_SENTRY=1 skips the check for a deliberate no-Sentry build.
 */
export function assertSentryDsn({ command, envDir, env = process.env }) {
  if (command !== "build") return;
  if (env.ALLOW_NO_SENTRY === "1") return;
  if (resolveSentryDsn({ envDir, env })) return;
  throw new Error(
    `VITE_SENTRY_DSN is not set. The Sentry DSN is compiled into the client bundle at build time, ` +
      `so put it in ${join(envDir, ".env")} (see .env.example) or export it in the shell before running ` +
      `\`empirica bundle\`. To build without Sentry on purpose, set ALLOW_NO_SENTRY=1.`,
  );
}
