import React from "react";
import { FRAMEWORK_AREAS } from "../lib/framework";
import type { Session } from "../lib/types";

export function FrameworkReviewPanel({
  session, busy, disabled, onRetry,
}: {
  session: Session;
  busy: boolean;
  disabled: boolean;
  onRetry: () => void;
}) {
  const review = session.framework_review;
  const current = review?.revision === session.revision && review.mode === session.mode;
  const status = busy
    ? "Mapping & checking your framework"
    : review && !current
      ? "Needs a fresh review"
      : session.gate.ready && current
        ? session.mode === "demo" ? "Scripted map available" : "Mapped and reviewed"
        : current && review.assessment
          ? "Decisions or details remain"
          : current
            ? "Independent review pending"
            : "Framework review required";
  return (
    <section className="framework-review" aria-label="Product framework">
      <div className="framework-heading">
        <h3>Product framework</h3>
        <span>{status}</span>
      </div>
      <p className="framework-note">
        {session.mode === "demo"
          ? "Scripted example · no model reasoning. Live mode reviews your actual product."
          : "Clarity needs connected journeys, system structure, recovery paths and concrete checks."}
      </p>
      {session.gate.blockers.length > 0 && (
        <details className="framework-blockers">
          <summary>What still needs work ({session.gate.blockers.length})</summary>
          <ul>{session.gate.blockers.map((blocker, index) => <li key={index}>{blocker}</li>)}</ul>
        </details>
      )}
      {current && review && (
        <details className="framework-map">
          <summary>Explore framework ({review.framework.sections.length} areas)</summary>
          {review.framework.sections.map((section) => (
            <details className="framework-area" key={section.area}>
              <summary>{FRAMEWORK_AREAS[section.area]}</summary>
              <ol>
                {section.entries.map((entry, index) => (
                  <li key={index}>
                    <div className="framework-entry-heading">
                      <strong>{entry.aspect.replaceAll("-", " ")}</strong>
                      <span className={`framework-tag ${entry.status}`}>
                        {entry.status === "confirmed" ? "Confirmed" : entry.status === "proposal" ? "Proposal" : "Unresolved"}
                      </span>
                    </div>
                    <p>{entry.text}</p>
                    <small>Sources: {entry.ledger_ids.join(", ")}</small>
                  </li>
                ))}
              </ol>
            </details>
          ))}
        </details>
      )}
      {!session.gate.ready && session.turns.length > 0 && (
        <button className="text-button framework-retry" onClick={onRetry} disabled={busy || disabled}>
          Review framework again
        </button>
      )}
    </section>
  );
}
