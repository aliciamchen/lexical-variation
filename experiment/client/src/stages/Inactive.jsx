import React from "react";
import { Alert } from "../components/Alert.jsx";
import { Button } from "../components/Button.jsx";

export function Inactive() {
  return (
    <div className="py-8 max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
      <Alert title="No Game Available">
        <p>
          Unfortunately, you have been declared inactive and will not be able
          continue with the game.
        </p>
      </Alert>
      <Alert title="Payment">
        <p className="pt-1">
          Thank you for your time and willingness to participate in our study.
        </p>
      </Alert>
    </div>
  );
}
