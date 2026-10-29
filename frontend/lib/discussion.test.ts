import { expect, it } from "vitest";
import {
  discussionKey,
  matchesDiscussionSource,
  requestForDraft,
  settleDraft,
  startDifferentDraft,
  type DiscussionDraft,
  type DiscussionTarget,
} from "./discussion";
import { attachDictation } from "./dictation";
import type { SpeechRecognition } from "./speech";

const target: DiscussionTarget = {
  kind: "plan",
  requirements_revision: 3,
  plan_id: "p",
  plan_revision: 1,
  plan_hash: "a",
  node_id: "P1",
  node_hash: "b",
};
it("never binds an old displayed graph to a newer server thread", () => {
  const source = {
    plan_id: "p",
    revision: 1,
    content_hash: "a",
    requirements_revision: 3,
  };
  expect(matchesDiscussionSource(target, source)).toBe(true);
  expect(matchesDiscussionSource({ ...target, plan_hash: "new" }, source)).toBe(
    false,
  );
  expect(
    matchesDiscussionSource({ ...target, requirements_revision: 4 }, source),
  ).toBe(false);
  expect(matchesDiscussionSource(target)).toBe(false);
  expect(
    matchesDiscussionSource({
      ...target,
      kind: "intent",
      plan_id: null,
      plan_revision: null,
      plan_hash: null,
    }),
  ).toBe(true);
});
it("keeps drafts separate across sessions, nodes and plan bodies", () => {
  const key = discussionKey("s", target);
  expect(discussionKey("other", target)).not.toBe(key);
  expect(discussionKey("s", { ...target, node_id: "P2" })).not.toBe(key);
  expect(discussionKey("s", { ...target, node_hash: "new" })).not.toBe(key);
});
it("retains the exact request ID after an uncertain delivery", () => {
  const draft: DiscussionDraft = {
    text: "  Preview before saving.  ",
    mode: "direction",
  };
  const request = requestForDraft(draft, target, () => "one");
  expect(request.text).toBe(draft.text);
  expect(
    requestForDraft({ ...draft, pending: request }, target, () => "two"),
  ).toEqual(request);
  expect(() =>
    requestForDraft(
      { ...draft, pending: request },
      { ...target, node_id: "P2" },
    ),
  ).toThrow(/different section/);
});
it("only clears text after its matching completed request, preserving newer edits", () => {
  const draft: DiscussionDraft = {
    text: "Keep this edit",
    mode: "question",
    pending: {
      request_id: "one",
      target,
      mode: "question",
      text: "Old question",
    },
  };
  expect(settleDraft(draft, "one", "complete").text).toBe("Keep this edit");
  expect(
    settleDraft({ ...draft, text: "Old question" }, "one", "complete").text,
  ).toBe("");
  expect(settleDraft(draft, "other", "complete")).toEqual(draft);
  expect(settleDraft(draft, "one", "uncertain").pending).toEqual(draft.pending);
  expect(settleDraft(draft, "one", "failed")).toEqual({
    text: draft.text,
    mode: draft.mode,
  });
});

it("lets a user leave a terminal uncertain request without replaying or allocating another request", () => {
  const pending = {
    request_id: "old",
    target,
    mode: "direction" as const,
    text: "Original exact direction",
  };
  const draft: DiscussionDraft = {
    text: pending.text,
    mode: "direction",
    pending,
  };
  const uncertain = { request_id: "old", status: "uncertain" as const };
  let allocated = 0;
  const fresh = startDifferentDraft(draft, uncertain);
  expect(fresh).toEqual({ text: "", mode: "question" });
  expect(allocated).toBe(0);
  expect(pending.text).toBe("Original exact direction");
  expect(
    startDifferentDraft({ ...draft, text: "Newer unsent edit" }, uncertain)
      .text,
  ).toBe("Newer unsent edit");
  expect(
    startDifferentDraft(draft, { request_id: "old", status: "pending" }),
  ).toEqual(draft);
  expect(
    startDifferentDraft(draft, { request_id: "other", status: "uncertain" }),
  ).toEqual(draft);
  expect(startDifferentDraft(draft, undefined)).toEqual(draft);
  const next = requestForDraft(
    { ...fresh, text: "A genuinely new question" },
    target,
    () => `new-${++allocated}`,
  );
  expect(next.request_id).toBe("new-1");
  expect(next.text).toBe("A genuinely new question");
  expect(allocated).toBe(1);
});
it("dictation produces editable text and ignores delayed callbacks after disposal", () => {
  const recognition = {
    start() {},
    stop() {},
    abort() {},
    onresult: null,
    onerror: null,
    onend: null,
  } as unknown as SpeechRecognition;
  const texts: string[] = [];
  const states: string[] = [];
  const capture = attachDictation(
    recognition,
    "My vision",
    (text) => texts.push(text),
    (state) => states.push(state),
    () => {},
  );
  capture.start();
  const callback = recognition.onresult!;
  callback({
    resultIndex: 0,
    results: [{ isFinal: true, 0: { transcript: "save a preview" } }],
  });
  expect(texts).toEqual(["My vision save a preview"]);
  capture.stop();
  expect(states.at(-1)).toBe("stopping");
  capture.dispose();
  callback({
    resultIndex: 0,
    results: [{ isFinal: true, 0: { transcript: "wrong node" } }],
  });
  expect(texts).toHaveLength(1);
  expect(recognition.onresult).toBeNull();
});
it("dictation reports permission denial without submitting or leaking callbacks", () => {
  const recognition = {
    start() {},
    stop() {},
    abort() {},
    onresult: null,
    onerror: null,
    onend: null,
  } as unknown as SpeechRecognition;
  const errors: string[] = [];
  const capture = attachDictation(
    recognition,
    "",
    () => {},
    () => {},
    (error) => errors.push(error),
  );
  capture.start();
  recognition.onerror!({ error: "not-allowed" });
  expect(errors[0]).toMatch(/permission/i);
  expect(recognition.onresult).toBeNull();
  capture.dispose();
});
it("ignores queued dictation after normal completion and tolerates browser teardown errors", () => {
  const recognition = {
    start() {},
    stop() {
      throw new Error("already stopped");
    },
    abort() {
      throw new Error("already aborted");
    },
    onresult: null,
    onerror: null,
    onend: null,
  } as unknown as SpeechRecognition;
  const texts: string[] = [];
  const capture = attachDictation(
    recognition,
    "",
    (text) => texts.push(text),
    () => {},
    () => {},
  );
  capture.start();
  const late = recognition.onresult!;
  recognition.onend!();
  late({
    resultIndex: 0,
    results: [{ isFinal: true, 0: { transcript: "too late" } }],
  });
  expect(texts).toEqual([]);
  expect(() => capture.dispose()).not.toThrow();
});
