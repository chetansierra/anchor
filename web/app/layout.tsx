import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI solutions consultant — production-grade agents on your data",
  description:
    "Describe your AI problem and watch an agent scope it live — matched services, a tailored approach, a timeline, and proof. The demo is the product.",
};

const fontStack =
  '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif';

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body style={{ fontFamily: fontStack }}>{children}</body>
    </html>
  );
}
