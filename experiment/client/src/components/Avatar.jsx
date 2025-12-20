import React from "react";

export function Avatar({ player }) {
  return (
    <img
      className="h-full w-full rounded-md shadow bg-white p-1"
      src={`${player.get("avatar")}`}
      alt="Avatar"
    />
  );
}
