import { describe, expect, it } from "vitest";
import { consumeEvents } from "./stream";

describe("streamed turn updates", () => {
  it("handles split UTF-8 characters and frames across chunks", async () => {
    const bytes = new TextEncoder().encode(
      'data: {"type":"stage","message":"Café"}\n\ndata: {"type":"done"}\n\n',
    );
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        for (let i = 0; i < bytes.length; i += 3)
          controller.enqueue(bytes.slice(i, i + 3));
        controller.close();
      },
    });
    const events: unknown[] = [];
    await consumeEvents(new Response(stream), (event) => events.push(event));
    expect(events).toEqual([
      { type: "stage", message: "Café" },
      { type: "done" },
    ]);
  });

  it("surfaces server error events", async () => {
    const response = new Response(
      'data: {"type":"error","message":"Model timed out"}\n\n',
    );
    await expect(consumeEvents(response, () => {})).rejects.toThrow(
      "Model timed out",
    );
  });

  it("handles CRLF frame delimiters split across network chunks", async () => {
    const bytes = new TextEncoder().encode(
      'data: {"type":"stage","message":"Café"}\r\n\r\ndata: {"type":"done"}\r\n\r\n',
    );
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        for (const byte of bytes) controller.enqueue(new Uint8Array([byte]));
        controller.close();
      },
    });
    const events: unknown[] = [];
    await consumeEvents(new Response(stream), (event) => events.push(event));
    expect(events).toEqual([
      { type: "stage", message: "Café" },
      { type: "done" },
    ]);
  });

  it("treats an interrupted stream as failure", async () => {
    const response = new Response(
      'data: {"type":"stage","message":"Extracting"}\n\n',
    );
    await expect(consumeEvents(response, () => {})).rejects.toThrow(
      "interrupted",
    );
  });
});
