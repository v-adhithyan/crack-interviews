import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "HackerLeap Code",
  description: "Let's crack coding interview",
  icons: {
    icon: "/icon.svg",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
