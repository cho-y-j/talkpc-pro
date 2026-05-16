import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

export const metadata: Metadata = {
  title: "TalkPC Pro — 카카오톡 자동 메시지 발송 솔루션",
  description:
    "연락처, 템플릿, 알림톡을 한 곳에서. PC 기반 카카오톡 자동 발송 + 클라우드 동기화 + 라이선스 관리.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ko" className={`${inter.variable}`}>
      <body>{children}</body>
    </html>
  );
}
