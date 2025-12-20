import React from "react";
import { Button } from "../components/Button";

export function ConsentPage({ next }) {
  return (
    <div className="consent">
      <h1>Consent Form</h1>

      <p>
        Please read this consent agreement carefully before deciding whether to
        participate in this experiment.
      </p>
      <p>
        <strong>What you will do in this research:</strong> You will play a
        series of communication tasks with other participants.
      </p>
      <p>
        <strong>Time required:</strong> This study will take approximately 60
        minutes.
      </p>
      <p>
        <strong>Purpose of the research:</strong> The purpose is to understand
        how people think about communication in groups.
      </p>
      <p>
        <strong>Risks:</strong> There are no anticipated risks associated with
        participating in this study. The effects should be comparable to viewing
        a computer monitor and using a mouse for the duration of the experiment.
      </p>
      <p>
        <strong>Compensation:</strong> You will receive $12 for completing the
        experiment, with an additional performance bonus of up to $8.
      </p>
      <p>
        <strong>Confidentiality:</strong> Your participation in this study will
        remain confidential. No personally identifiable information will be
        collected. Your anonymous data may be shared with other researchers and
        used in future projects.
      </p>
      <p>
        <strong>Participation and withdrawal:</strong> Your participation in
        this study is completely voluntary and you may refuse to participate or
        choose to withdraw at any time without penalty or loss of benefits to
        which you are otherwise entitled.
      </p>
      <p>
        <strong>How to contact the researcher:</strong> If you have questions or
        concerns about your participation or payment, or want to request a
        summary of research findings, please contact
        <a href="mailto:aliciach@mit.edu">aliciach@mit.edu</a>.
      </p>
      <p>
        <strong>Who to contact about your rights in this research:</strong> For
        questions, concerns, suggestions, or complaints that have not been or
        cannot be addressed by the researcher, or to report research-related
        harm, please contact the Chairman of the Committee on the Use of Humans
        as Experimental Subjects, M.I.T., Room E25-143B, 77 Massachusetts Ave,
        Cambridge, MA 02139, phone 1-617-253-6787.
      </p>

      <div className="flex w-sw justify-center">
        <Button handleClick={next} autoFocus>
          <p>I consent</p>
        </Button>
      </div>
    </div>
  );
}
