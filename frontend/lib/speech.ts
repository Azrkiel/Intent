export interface RecognitionResult {
  isFinal: boolean;
  0: { transcript: string };
}
export interface SpeechRecognition {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  onresult:
    | ((event: {
        resultIndex: number;
        results: ArrayLike<RecognitionResult>;
      }) => void)
    | null;
  onerror: ((event: { error: string }) => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
  abort(): void;
}
type Constructor = new () => SpeechRecognition;
export function recognitionConstructor(): Constructor | undefined {
  if (typeof window === "undefined") return undefined;
  const browser = window as Window & {
    SpeechRecognition?: Constructor;
    webkitSpeechRecognition?: Constructor;
  };
  return browser.SpeechRecognition || browser.webkitSpeechRecognition;
}
export function speak(text: string) {
  if (!("speechSynthesis" in window)) return;
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.rate = 1;
  window.speechSynthesis.speak(utterance);
}
