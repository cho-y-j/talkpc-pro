import Link from "next/link";
import { Nav } from "@/components/Nav";
import { Footer } from "@/components/Footer";

const GITHUB_RELEASES =
  "https://github.com/cho-y-j/talkpc-pro/releases/latest";

export default function DownloadPage() {
  return (
    <>
      <Nav />
      <section className="bg-[color:var(--canvas)] py-24">
        <div className="mx-auto max-w-[1280px] px-6">
          <p className="t-uppercase text-[color:var(--body)]">Download</p>
          <h1 className="t-display-xl mt-3 max-w-3xl">
            TalkPC Pro for Windows.
          </h1>
          <p className="t-body-md mt-6 max-w-2xl text-[color:var(--body)]">
            Windows 10 / 11 64-bit 지원. 설치 후 가입한 계정으로 로그인하면
            바로 사용 가능합니다.
          </p>

          <div className="mt-12 grid gap-8 lg:grid-cols-2">
            <div className="border border-[color:var(--hairline)] p-10">
              <p className="t-uppercase text-[color:var(--body)]">최신 버전</p>
              <div className="mt-4 flex items-baseline gap-3">
                <span className="text-4xl font-medium">v1.0.0</span>
                <span className="t-body-sm">Windows x64</span>
              </div>
              <ul className="mt-8 space-y-3 text-[14px] text-[color:var(--body)]">
                <li>· Windows 10 / 11 64-bit</li>
                <li>· 약 250MB (PaddleOCR 모델 포함)</li>
                <li>· 카카오톡 PC 설치 필수</li>
              </ul>
              <a
                href={GITHUB_RELEASES}
                target="_blank"
                rel="noopener noreferrer"
                className="btn-primary mt-10 w-full"
              >
                Windows 다운로드
              </a>
              <p className="t-caption mt-4 text-center">
                GitHub Releases 페이지로 이동합니다.
              </p>
            </div>

            <div
              className="border border-[color:var(--hairline)] p-10"
              style={{ background: "var(--canvas-elevated)" }}
            >
              <p className="t-uppercase text-[color:var(--body)]">설치 가이드</p>
              <h2 className="t-title-md mt-4">처음 사용하시나요?</h2>
              <ol className="mt-6 space-y-4 text-[14px]">
                <Step n="1" title="가입">
                  <Link href="/signup" className="underline">
                    회원가입 페이지
                  </Link>
                  에서 이메일/비밀번호로 가입합니다.
                </Step>
                <Step n="2" title="승인 대기">
                  관리자가 가입을 승인하면 이메일로 안내드립니다.
                </Step>
                <Step n="3" title="다운로드 + 설치">
                  좌측 버튼으로 최신 버전을 받아 설치합니다.
                </Step>
                <Step n="4" title="로그인">
                  카카오톡 PC 를 띄운 채로 앱을 실행하고 가입한
                  이메일/비밀번호로 로그인합니다.
                </Step>
                <Step n="5" title="좌표 학습">
                  설정 페이지의 "위치 학습 시작" 으로 8단계 좌표를 학습합니다.
                </Step>
              </ol>
            </div>
          </div>

          <div className="mt-16 border-l-2 border-[color:var(--primary)] pl-6">
            <p className="t-uppercase mb-2 text-[color:var(--body)]">
              시스템 요구사항
            </p>
            <p className="t-body-sm">
              Windows 10 / 11 64-bit · 메모리 4GB 이상 ·
              카카오톡 PC 설치 · 인터넷 연결 (서버 동기화)
            </p>
          </div>
        </div>
      </section>
      <Footer />
    </>
  );
}

function Step({
  n, title, children,
}: { n: string; title: string; children: React.ReactNode }) {
  return (
    <li className="flex gap-4">
      <span
        className="flex h-6 w-6 flex-shrink-0 items-center justify-center text-[11px] font-bold"
        style={{ background: "var(--primary)", color: "#fff" }}
      >
        {n}
      </span>
      <div>
        <p className="font-medium">{title}</p>
        <p className="t-body-sm mt-1">{children}</p>
      </div>
    </li>
  );
}
