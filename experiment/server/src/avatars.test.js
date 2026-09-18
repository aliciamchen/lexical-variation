// Every avatar the game can show must exist on our own origin.
//
// Avatars used to be fetched from api.dicebear.com at play time, once per
// player per trial in the mixed conditions. They are now committed under
// client/public/avatars/ (see scripts/fetch-avatars.mjs). The risk that
// replaces the outage risk is a missing file: a seed the server generates but
// nobody downloaded renders as a broken image, and in the mixed conditions
// that is the identity cue the condition manipulates. So this enumerates every
// seed the server can produce and checks the file is there.
import { existsSync } from "fs";
import { fileURLToPath } from "url";
import { join } from "path";
import { describe, expect, it } from "vitest";
import {
  anonymousAvatarSeeds,
  avatarFileName,
  avatar_seeds,
  getAnonymousAvatarUrl,
  getAvatarUrl,
  GROUP_NAMES,
  GROUP_SIZE,
  NUM_TANGRAMS,
} from "./constants";

const avatarDir = fileURLToPath(new URL("../../client/public/avatars/", import.meta.url));

describe("avatar assets", () => {
  it("has a file for every player avatar", () => {
    const missing = avatar_seeds.filter((s) => !existsSync(join(avatarDir, avatarFileName(s))));
    expect(missing).toEqual([]);
  });

  it("has a file for every anonymous avatar a production game can generate", () => {
    const missing = anonymousAvatarSeeds().filter(
      (s) => !existsSync(join(avatarDir, avatarFileName(s))),
    );
    expect(missing).toEqual([]);
  });

  it("enumerates the seeds in the shape callbacks.js builds them", () => {
    // onRoundStart: `anon_block${blockNum}_trial${targetNum}_player${anonIndex}`
    const seeds = anonymousAvatarSeeds();
    expect(seeds).toContain("anon_block0_trial0_player0");
    // Six Phase 2 blocks x NUM_TANGRAMS trials x every seat in the game.
    expect(seeds).toHaveLength(6 * NUM_TANGRAMS * GROUP_NAMES.length * GROUP_SIZE);
    expect(new Set(seeds).size).toBe(seeds.length);
  });

  it("serves both kinds from our own origin, not a third party", () => {
    expect(getAvatarUrl("aria")).toBe("/avatars/aria.svg");
    expect(getAnonymousAvatarUrl("anon_block2_trial3_player4")).toBe(
      "/avatars/anon_block2_trial3_player4.svg",
    );
    for (const url of [getAvatarUrl("aria"), getAnonymousAvatarUrl("anon_block0_trial0_player0")]) {
      expect(url).not.toContain("dicebear");
      expect(url.startsWith("/")).toBe(true);
    }
  });

  it("keeps a seed that could escape its filename inside the directory", () => {
    expect(avatarFileName("../../etc/passwd")).toBe("______etc_passwd.svg");
  });
});
