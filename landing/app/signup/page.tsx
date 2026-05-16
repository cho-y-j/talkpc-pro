"use client";

import { useState } from "react";
import Link from "next/link";
import { Nav } from "@/components/Nav";
import { Footer } from "@/components/Footer";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE || "https://talkpc-pro.vercel.app";

export default function SignupPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [password2, setPassword2] = useState("");
  const [agreed, setAgreed] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState<{ license: string } | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (password !== password2) {
      setError("비밀번호가 일치하지 않습니다.");
      return;
    }
    if (password.length < 8) {
      setError("비밀번호는 8자 이상이어야 합니다.");
      return;
    }
    if (!agreed) {
      setError("이용약관과 개인정보처리방침에 동의해주세요.");
      return;
    }
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/auth/signup`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.detail || "가입 실패");
        return;
      }
      setSuccess({ license: data.license_key });
    } catch (e) {
      setError("네트워크 오류 — 잠시 후 다시 시도해주세요.");
    } finally {
      setLoading(false);
    }
  }

  if (success) {
    return (
      <>
        <Nav />
        <section className="flex min-h-[80vh] items-center bg-[color:var(--canvas)] px-6 py-24">
          <div className="mx-auto max-w-2xl text-center">
            <div
              className="mx-auto mb-8 flex h-16 w-16 items-center justify-center"
              style={{ background: "var(--primary)" }}
            >
              <svg
                width="32" height="32" viewBox="0 0 24 24"
                fill="none" stroke="white" strokeWidth="2"
              >
                <polyline points="20 6 9 17 4 12" />
              </svg>
            </div>
            <p className="t-uppercase text-[color:var(--body)]">가입 완료</p>
            <h1 className="t-display-lg mt-4">
              관리자 승인 대기 중입니다.
            </h1>
            <p className="t-body-md mt-6 text-[color:var(--body)]">
              가입이 접수되었습니다. 관리자 승인 후 이메일로 안내드리며,
              앱에서 같은 이메일/비밀번호로 로그인하시면 됩니다.
            </p>
            <div
              className="mx-auto mt-10 max-w-sm border border-[color:var(--hairline)] p-6"
              style={{ background: "var(--canvas-elevated)" }}
            >
              <p className="t-uppercase mb-3 text-[color:var(--body)]">
                라이선스 키
              </p>
              <p
                className="font-mono text-lg tracking-wide"
                style={{ color: "var(--primary)" }}
              >
                {success.license}
              </p>
            </div>
            <div className="mt-12 flex justify-center gap-4">
              <Link href="/download" className="btn-primary">
                앱 다운로드
              </Link>
              <Link href="/" className="btn-outline">
                홈으로
              </Link>
            </div>
          </div>
        </section>
        <Footer />
      </>
    );
  }

  return (
    <>
      <Nav />
      <section className="flex min-h-[80vh] items-center bg-[color:var(--canvas)] px-6 py-24">
        <div className="mx-auto w-full max-w-md">
          <p className="t-uppercase text-[color:var(--body)]">회원가입</p>
          <h1 className="t-display-lg mt-3">계정을 만들어보세요.</h1>
          <p className="t-body-md mt-4 text-[color:var(--body)]">
            가입 후 관리자 승인을 받으면 PC 앱에서 바로 사용 가능합니다.
          </p>

          <form onSubmit={onSubmit} className="mt-12 space-y-6">
            <div>
              <label className="t-uppercase mb-3 block text-[color:var(--body)]">
                이메일
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="input-dark"
                placeholder="you@example.com"
              />
            </div>
            <div>
              <label className="t-uppercase mb-3 block text-[color:var(--body)]">
                비밀번호 (8자 이상)
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={8}
                className="input-dark"
                placeholder="••••••••"
              />
            </div>
            <div>
              <label className="t-uppercase mb-3 block text-[color:var(--body)]">
                비밀번호 확인
              </label>
              <input
                type="password"
                value={password2}
                onChange={(e) => setPassword2(e.target.value)}
                required
                className="input-dark"
                placeholder="••••••••"
              />
            </div>

            <label className="flex cursor-pointer items-start gap-3 text-[13px] text-[color:var(--body)]">
              <input
                type="checkbox"
                checked={agreed}
                onChange={(e) => setAgreed(e.target.checked)}
                className="mt-1"
              />
              <span>
                <a
                  href={`${API_BASE}/terms`}
                  target="_blank"
                  className="underline hover:text-white"
                >
                  이용약관
                </a>{" "}
                및{" "}
                <a
                  href={`${API_BASE}/privacy`}
                  target="_blank"
                  className="underline hover:text-white"
                >
                  개인정보처리방침
                </a>
                에 동의합니다.
              </span>
            </label>

            {error && (
              <div
                className="border-l-2 px-4 py-3 text-sm"
                style={{
                  borderColor: "var(--warning)",
                  background: "rgba(241,58,44,0.08)",
                  color: "#ff8a80",
                }}
              >
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="btn-primary w-full"
            >
              {loading ? "가입 중..." : "가입하기"}
            </button>

            <p className="t-body-sm text-center">
              이미 계정이 있으신가요?{" "}
              <Link href="/download" className="text-white underline">
                앱에서 로그인
              </Link>
            </p>
          </form>
        </div>
      </section>
      <Footer />
    </>
  );
}
