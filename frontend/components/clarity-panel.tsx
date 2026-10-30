import React from "react";
import { FIELD_LABELS, NORTH_STAR_ORDER, type NorthStarField } from "../lib/clarity";
import type { Session } from "../lib/types";

export function ClarityPanel({
  session, busy, disabled, onConfirm, onCorrect, onVeto, onRetry,
}: {
  session: Session;
  busy: boolean;
  disabled: boolean;
  onConfirm: (field: NorthStarField, textHash: string) => void;
  onCorrect: (field: NorthStarField) => void;
  onVeto: (decisionId: string) => void;
  onRetry: () => void;
}) {
  const clarity = session.clarity;
  const current = clarity?.revision === session.revision && clarity.mode === session.mode;
  const readout = session.clarity_readout;
  const choices = current ? clarity!.decisions.filter((d) => d.status === "delegated") : [];
  const filled = current ? clarity!.claims.filter((c) => c.status === "proposal") : [];
  const status = busy
    ? "Checking your intent"
    : clarity && !current
      ? "Needs a fresh check"
      : session.gate.ready && current
        ? session.mode === "demo" ? "Scripted check complete" : "Clear and reviewed"
        : current ? "Details remain" : "Clarity check required";
  return (
    <section className="framework-review clarity-panel" aria-label="Clarity">
      <div className="framework-heading">
        <h3>Clarity</h3>
        <span>{status}</span>
      </div>
      <p className="framework-note">
        {session.mode === "demo"
          ? "Scripted example · no model reasoning. Live mode checks your actual words."
          : "Intent keeps asking until each part of your North Star passes its checks."}
      </p>
      {current && readout && (
        <p className="clarity-readout">
          {readout.statements} statements mapped · {readout.unmapped_words} words unmapped ·{" "}
          {readout.choices_made} choices made for you · {readout.decisions_open} decisions need you ·{" "}
          {readout.scenarios} scenarios to confirm
        </p>
      )}
      {current && clarity && (
        <ol className="north-star">
          {NORTH_STAR_ORDER.map((name) => {
            const field = clarity.fields.find((item) => item.field === name);
            const readback = field && field.failing.length === 1 && field.failing[0] === "G3" && field.judgement;
            return (
              <li key={name}>
                <div className="framework-entry-heading">
                  <strong>{FIELD_LABELS[name]}</strong>
                  <span className={`framework-tag ${field?.passed ? "confirmed" : "unresolved"}`}>
                    {field?.passed ? "Clear" : field?.text ? "Needs detail" : "Not answered"}
                  </span>
                </div>
                {field?.text && <p>{field.text}</p>}
                {readback && (
                  <div className="clarity-readback">
                    <p>I understood: {field.judgement!.readback}</p>
                    <button className="text-button" disabled={busy || disabled}
                      onClick={() => onConfirm(name, field.text_hash)}>That&apos;s right</button>
                    <button className="text-button" disabled={busy || disabled}
                      onClick={() => onCorrect(name)}>Correct it</button>
                  </div>
                )}
              </li>
            );
          })}
        </ol>
      )}
      {choices.length > 0 && (
        <details className="framework-map" open>
          <summary>Choices I made for you ({choices.length})</summary>
          <ul>
            {choices.map((decision) => (
              <li key={decision.id}>
                {decision.question} <strong>{decision.outcome}</strong>
                <small> {decision.because}</small>{" "}
                <button className="text-button" disabled={busy || disabled}
                  onClick={() => onVeto(decision.id)}>Veto</button>
              </li>
            ))}
          </ul>
        </details>
      )}
      {filled.length > 0 && (
        <details className="framework-map">
          <summary>What I filled in for you ({filled.length})</summary>
          <ul>
            {filled.map((claim) => (
              <li key={claim.id}>{claim.text} <small>{claim.id}</small></li>
            ))}
          </ul>
        </details>
      )}
      {current && clarity && clarity.scenarios.length > 0 && (
        <details className="framework-map">
          <summary>Scenarios to approve ({clarity.scenarios.length})</summary>
          <ol>
            {clarity.scenarios.map((scenario) => (
              <li key={scenario.id}>
                <strong>{scenario.title}</strong>
                <p>Given {scenario.given}, when {scenario.when}, then {scenario.then}.</p>
                <small>Claims: {scenario.claims.join(", ")}</small>
              </li>
            ))}
          </ol>
        </details>
      )}
      {current && clarity?.review && (
        <p className="clarity-review">
          {clarity.review.trusted ? "Review verified" : "Review not verified"}: caught{" "}
          {clarity.review.caught.length} of {clarity.review.canaries.length} planted defects
        </p>
      )}
      {session.gate.blockers.length > 0 && (
        <details className="framework-blockers">
          <summary>What still needs work ({session.gate.blockers.length})</summary>
          <ul>{session.gate.blockers.map((blocker, index) => <li key={index}>{blocker}</li>)}</ul>
        </details>
      )}
      {!session.gate.ready && session.turns.length > 0 && (
        <button className="text-button framework-retry" onClick={onRetry} disabled={busy || disabled}>
          Check clarity again
        </button>
      )}
    </section>
  );
}
