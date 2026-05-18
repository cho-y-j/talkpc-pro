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

          {/* 다운로드 + 가이드 */}
          <div className="mt-12 grid gap-8 lg:grid-cols-2">
            <div className="border border-[color:var(--hairline)] p-10">
              <p className="t-uppercase text-[color:var(--body)]">
                최신 버전 · v0.1.0
              </p>
              <h2 className="mt-4 text-2xl font-medium">
                Setup 인스톨러
                <span
                  className="ml-3 inline-block px-2 py-0.5 text-[10px] font-bold tracking-wider"
                  style={{ background: "var(--primary)", color: "#fff" }}
                >
                  추천
                </span>
              </h2>
              <ul className="mt-6 space-y-3 text-[14px] text-[color:var(--body)]">
                <li>· `C:\Program Files\TalkPC-Pro\` 자동 설치</li>
                <li>· 바탕화면 + 시작 메뉴 아이콘 자동</li>
                <li>· 제거 프로그램 등록 (간편 삭제)</li>
                <li>· 한글 사용자명 PC 도 정상 작동</li>
              </ul>
              <a
                href={GITHUB_RELEASES}
                target="_blank"
                rel="noopener noreferrer"
                className="btn-primary mt-10 w-full"
              >
                Setup.exe 다운로드
              </a>
              <p className="t-caption mt-4 text-center">
                GitHub Releases — `TalkPC-Pro-Setup-v0.1.0.exe`
              </p>
            </div>

            <div
              className="border border-[color:var(--hairline)] p-10"
              style={{ background: "var(--canvas-elevated)" }}
            >
              <p className="t-uppercase text-[color:var(--body)]">
                포터블 (압축 해제)
              </p>
              <h2 className="mt-4 text-2xl font-medium">ZIP 버전</h2>
              <ul className="mt-6 space-y-3 text-[14px] text-[color:var(--body)]">
                <li>· 설치 없이 압축만 해제</li>
                <li>
                  · <span className="text-[color:var(--warning)]">
                    ⚠ ASCII 경로 필수 (한글 X)
                  </span>
                </li>
                <li>· 권장: `D:\TalkPC-Pro\` 또는 `C:\TalkPC-Pro\`</li>
                <li>· 관리자 권한 불필요</li>
              </ul>
              <a
                href={GITHUB_RELEASES}
                target="_blank"
                rel="noopener noreferrer"
                className="btn-outline mt-10 w-full"
              >
                ZIP 다운로드
              </a>
              <p className="t-caption mt-4 text-center">
                `TalkPC-Pro-v0.1.0-windows-x64.zip`
              </p>
            </div>
          </div>

          {/* SmartScreen 차단 해제 안내 */}
          <div
            className="mt-16 border-l-2 border-[color:var(--primary)] p-8"
            style={{ background: "var(--canvas-elevated)" }}
          >
            <p className="t-uppercase mb-3 text-[color:var(--primary)]">
              중요 · Windows 차단 해제
            </p>
            <h3 className="t-title-md mb-4">
              처음 실행 시 파란 SmartScreen 경고가 뜹니다.
            </h3>
            <p className="t-body-sm mb-6">
              코드 사이닝 인증서 발급 전이라 Windows 가 "인식할 수 없는 앱"
              으로 표시합니다. 우리 제품이 맞으니 안전하게 우회하세요.
            </p>

            <div className="space-y-6">
              <div>
                <p className="t-uppercase mb-2">방법 ① 다운로드 후 즉시 차단 해제</p>
                <ol className="ml-4 space-y-1 text-[14px] text-[color:var(--body)]">
                  <li>1. 다운받은 파일 (exe/zip) <b>우클릭 → 속성</b></li>
                  <li>2. 일반 탭 맨 아래 <b>"차단 해제"</b> 체크박스 클릭</li>
                  <li>3. <b>확인</b> → 실행</li>
                </ol>
              </div>

              <div>
                <p className="t-uppercase mb-2">방법 ② 실행 시 경고 우회</p>
                <ol className="ml-4 space-y-1 text-[14px] text-[color:var(--body)]">
                  <li>1. 파란 창 좌측 작은 글씨 <b>"추가 정보"</b> 클릭</li>
                  <li>2. 나타나는 <b>"실행"</b> 버튼 클릭</li>
                  <li>3. 다음부터는 자동 실행</li>
                </ol>
              </div>
            </div>
          </div>

          {/* 설치 가이드 */}
          <div className="mt-16">
            <p className="t-uppercase text-[color:var(--body)]">설치 가이드</p>
            <h3 className="t-display-lg mt-3">처음 사용하시나요?</h3>
            <ol className="mt-8 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
              <Step n="1" title="회원가입">
                <Link href="/signup" className="underline">
                  가입 페이지
                </Link>
                에서 이메일/비번 등록.
              </Step>
              <Step n="2" title="승인 대기">
                관리자 승인 후 안내 메일 받기.
              </Step>
              <Step n="3" title="설치 파일 다운로드">
                위 Setup.exe 권장. 다운 후 차단 해제 (위 안내).
              </Step>
              <Step n="4" title="설치 실행">
                Setup.exe 더블 클릭 → 다음 → 완료. 바탕화면 아이콘 자동 생성.
              </Step>
              <Step n="5" title="로그인">
                카카오톡 PC 켜둔 채로 앱 실행 → 가입한 이메일/비번 로그인.
              </Step>
              <Step n="6" title="좌표 학습">
                설정 → "위치 학습 시작" → 8단계 좌표 클릭.
              </Step>
            </ol>
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
    <li
      className="border border-[color:var(--hairline)] p-6"
      style={{ background: "var(--canvas-elevated)" }}
    >
      <span
        className="inline-flex h-7 w-7 items-center justify-center text-[12px] font-bold"
        style={{ background: "var(--primary)", color: "#fff" }}
      >
        {n}
      </span>
      <p className="mt-4 font-medium">{title}</p>
      <p className="t-body-sm mt-2">{children}</p>
    </li>
  );
}
