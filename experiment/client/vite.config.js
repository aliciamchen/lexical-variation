import react from "@vitejs/plugin-react";
import builtins from "rollup-plugin-polyfill-node";
import { defineConfig, searchForWorkspaceRoot } from "vite";
import restart from "vite-plugin-restart";
import UnoCSS from "unocss/vite";
import dns from "dns";
import { execSync } from "child_process";
import { fileURLToPath } from "url";
import { assertSentryDsn } from "../shared/sentry-env.js";

// The single .env at the repository root supplies VITE_SENTRY_DSN to the client
// build (and the server hostname to copy_tajriba.sh). Vite would otherwise only
// look for .env files inside client/.
const envDir = fileURLToPath(new URL("../..", import.meta.url));

dns.setDefaultResultOrder("verbatim");

// Which build an error came from. `empirica bundle` runs from inside the
// repository, so the commit is the natural version: Sentry then reports the
// release an issue was first seen in and flags one that reappears in a later
// build as a regression rather than quietly reopening it. A working tree with
// uncommitted changes is marked, because "abc1234-dirty" is a truthful answer
// to "which code is deployed" and a bare sha would not be.
function gitRelease() {
  try {
    const sha = execSync("git rev-parse --short HEAD", {
      cwd: fileURLToPath(new URL(".", import.meta.url)),
      stdio: ["ignore", "pipe", "ignore"],
    })
      .toString()
      .trim();
    // Tracked changes only: an untracked scratch file in the working tree is
    // not part of what gets built, so it must not make the release read dirty.
    const dirty = execSync("git status --porcelain --untracked-files=no", {
      cwd: fileURLToPath(new URL(".", import.meta.url)),
      stdio: ["ignore", "pipe", "ignore"],
    })
      .toString()
      .trim();
    return dirty ? `${sha}-dirty` : sha;
  } catch {
    // Building outside a checkout: better to ship no release than to fail.
    return "unknown";
  }
}

const builtinsPlugin = {
  ...builtins({ include: ["fs/promises"] }),
  name: "rollup-plugin-polyfill-node",
};

// https://vitejs.dev/config/
export default defineConfig(({ command }) => {
  // A production bundle without a DSN would ship with Sentry silently disabled.
  assertSentryDsn({ command, envDir });
  return {
  envDir,
  optimizeDeps: {
    exclude: ["@empirica/tajriba", "@empirica/core"],
  },
  server: {
    port: 8844,
    open: false,
    strictPort: true,
    host: "0.0.0.0",
    hmr: {
      host: "localhost",
      protocol: "ws",
      port: 8844,
    },
    fs: {
      allow: [
        // search up for workspace root
        searchForWorkspaceRoot(process.cwd()),
      ],
    },
  },
  build: {
    minify: false,
    target: "esnext",
    sourcemap: true,
    rollupOptions: {
      preserveEntrySignatures: "strict",
      plugins: [builtinsPlugin],
      output: {
        sourcemap: true,
      },
    },
  },
  clearScreen: false,
  plugins: [
    restart({
      restart: [
        "./uno.config.cjs",
        "./node_modules/@empirica/core/dist/**/*.{js,ts,jsx,tsx,css}",
        "./node_modules/@empirica/core/assets/**/*.css",
      ],
    }),
    UnoCSS(),
    react(),
  ],
  define: {
    "process.env": {
      NODE_ENV: process.env.NODE_ENV || "development",
      TEST_MODE: process.env.TEST_MODE || "false",
    },
    __APP_RELEASE__: JSON.stringify(gitRelease()),
  },
  };
});
