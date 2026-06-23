import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "HackerLeap",
  description: "Let's crack coding interview",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
