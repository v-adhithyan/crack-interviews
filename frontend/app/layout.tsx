import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Crack Interviews",
  description: "Personal Python interview practice",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
