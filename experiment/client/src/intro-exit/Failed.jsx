import React from "react";
import { Alert } from "../components/Alert";

export function Failed() {
  return (
    <div className="py-8 max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
      <Alert title="Game Terminated">
        <p>
          Unfortunately, we have experienced an error. Please submit the
          following code to receive a partial payment: <strong>C7F5I0Y9</strong>
          .
        </p>
        <p className="pt-1">
          Thank you for your time and willingness to participate in our study.
        </p>
      </Alert>
    </div>
  );
}
