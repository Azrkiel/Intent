import type { StreamEvent } from "./types";

export async function consumeEvents(
  response: Response,
  onEvent: (event: StreamEvent) => void,
) {
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(
      typeof body.detail === "string"
        ? body.detail
        : `Request failed (${response.status})`,
    );
  }
  if (!response.body) throw new Error("The server returned an empty stream.");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let pending = "";
  let done = false;
  try {
    while (true) {
      const chunk = await reader.read();
      pending = (
        pending + decoder.decode(chunk.value, { stream: !chunk.done })
      ).replace(/\r\n/g, "\n");
      let end: number;
      while ((end = pending.indexOf("\n\n")) >= 0) {
        const frame = pending.slice(0, end);
        pending = pending.slice(end + 2);
        const data = frame
          .split("\n")
          .filter((line) => line.startsWith("data: "))
          .map((line) => line.slice(6))
          .join("\n");
        if (!data) continue;
        const event = JSON.parse(data) as StreamEvent;
        onEvent(event);
        if (event.type === "error")
          throw new Error(event.message || "The model pass failed.");
        if (event.type === "done") done = true;
      }
      if (chunk.done) break;
    }
    if (!done)
      throw new Error(
        "The connection was interrupted. Your saved ledger is still available.",
      );
  } finally {
    await reader.cancel().catch(() => {});
    reader.releaseLock();
  }
}

export async function api<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(
    `/api${path}`,
    body === undefined
      ? { cache: "no-store" }
      : {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
  );
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : `Request failed (${response.status}).`,
    );
  }
  return response.json();
}
