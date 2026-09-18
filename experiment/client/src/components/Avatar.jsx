import React from "react";
import { AVATAR_PLACEHOLDER } from "../constants";

export function Avatar({ player }) {
  // Falls back to the neutral placeholder rather than interpolating a missing
  // attribute, which rendered src="undefined" and a broken image.
  return (
    <img
      className="h-full w-full rounded-md shadow bg-white p-1"
      src={player.get("avatar") || AVATAR_PLACEHOLDER}
      alt="Avatar"
    />
  );
}
