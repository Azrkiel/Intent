import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Intent — Think it. Clarify it. Build it.",
  description:
    "Turn a rough idea into an evidence-backed build brief, one useful question at a time.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" data-scroll-behavior="smooth">
      <body>{children}</body>
    </html>
  );
}
