import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";

const intentFont = localFont({
  src: "./fonts/Antonio-Variable.ttf",
  variable: "--font-intent",
  weight: "100 700",
  display: "swap",
  adjustFontFallback: false,
});

export const metadata: Metadata = {
  title: "Intent — Think it. Clarify it. Build it.",
  description:
    "Turn a rough idea into an evidence-backed build brief, one useful question at a time.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={intentFont.variable} data-scroll-behavior="smooth">
      <body>{children}</body>
    </html>
  );
}
