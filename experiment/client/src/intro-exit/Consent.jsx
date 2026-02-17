import React from "react";
import { Button } from "../components/Button";
import { ESTIMATED_TIME, BASE_PAY, MAX_BONUS } from "../constants";

export function ConsentPage({ next }) {
  return (
    <div className="consent">
      <h1>Consent Form</h1>
      <p>
        Please read this consent agreement carefully before deciding whether to
        participate in this experiment.
      </p>
      <p>
        <b>Purpose:</b> The purpose of this study is to understand how people
        communicate in groups.
      </p>
      <p>
        <b>Procedure:</b> In this study, you will play a series of communication
        tasks with other participants.
      </p>
      <p>
        <b>Payment:</b> Given the estimated duration of 60 minutes, you will
        receive
        <b>$15</b> for successfully completing the survey.
      </p>
      <p>
        <b>Risks and benefits:</b> There are no risks associated with
        participating in this study. There are no direct benefits associated
        with participating in this study, aside from monetary compensation.
      </p>
      <p>
        <b>Use of data by study researchers:</b> The research team led by
        Rebecca Saxe at MIT will have access to your answers.
      </p>
      <p>
        <b>Publication of results:</b> The results of the research may be
        presented at scientific meetings or published in scientific journals.
        Raw data may be published, but that data will not be able to be used to
        identify you.
      </p>
      <p>
        <b>Research contact information:</b> This study is run by Rebecca Saxe
        at MIT. If you have any questions or concerns about this study, or in
        the very unlikely event of a research-related injury, please contact
        saxe@mit.edu or 617-258-0721.
      </p>
      <p>
        <b>Research rights information:</b> You are not waiving any legal
        claims, rights, or remedies because of your participation in this
        research study. If you feel you have been treated unfairly, or if you
        have questions regarding your rights as a research subject, you may
        contact the Chairman of the Committee on the Use of Humans as
        Experimental Subjects, M.I.T., Room E25-143B, 77 Massachusetts Ave,
        Cambridge, MA 02139, phone 1-617-253-6787. If you have any questions or
        issues completing the survey, please email Alicia Chen: aliciach@mit.edu
        or Rebecca Saxe (PI): saxe@mit.edu
      </p>
      <div className="flex w-sw justify-center">
        <Button handleClick={next} autoFocus>
          <p>I consent</p>
        </Button>
      </div>
    </div>
  );
}
