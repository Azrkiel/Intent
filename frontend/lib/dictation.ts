import type { SpeechRecognition } from "./speech";

export type DictationState = "idle" | "listening" | "stopping";
export function attachDictation(
  recognition: SpeechRecognition,
  initialText: string,
  onText: (text: string) => void,
  onState: (state: DictationState) => void,
  onError: (message: string) => void,
) {
  let live = true;
  function dispose() {
    live = false;
    recognition.onresult = recognition.onerror = recognition.onend = null;
    try {
      recognition.abort();
    } catch {
      /* Recognition may have already ended. */
    }
  }
  function finish(message?: string) {
    if (!live) return;
    dispose();
    onState("idle");
    if (message) onError(message);
  }
  recognition.lang = "en-US";
  recognition.interimResults = true;
  recognition.continuous = true;
  recognition.onresult = (event) => {
    if (!live) return;
    const transcript = Array.from(event.results)
      .map((result) => result[0].transcript)
      .join(" ");
    onText([initialText, transcript].filter(Boolean).join(" "));
  };
  recognition.onerror = (event) => {
    finish(
      event.error === "not-allowed" || event.error === "service-not-allowed"
        ? "Microphone permission was denied. You can keep typing."
        : "Dictation stopped. Your transcript is still editable; you can keep typing.",
    );
  };
  recognition.onend = () => finish();
  return {
    start() {
      try {
        recognition.start();
        if (live) onState("listening");
      } catch {
        finish("Dictation could not start. You can keep typing.");
      }
    },
    stop() {
      if (live) {
        onState("stopping");
        try {
          recognition.stop();
        } catch {
          finish("Dictation has stopped. You can keep typing.");
        }
      }
    },
    dispose,
  };
}
