import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "TalkPC Pro Admin",
  description: "관리자 패널",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ko" className="h-full antialiased">
      <body className="min-h-full">{children}</body>
    </html>
  );
}
