import Link from "next/link";
import { Nav } from "@/components/Nav";
import { Footer } from "@/components/Footer";

export default function Home() {
  return (
    <>
      <Nav />

      {/* ── Cinematic Hero ── */}
      <section
        className="relative flex min-h-[88vh] w-full items-end"
        style={{
          background:
            "linear-gradient(180deg, #181818 0%, #0e0e0e 60%, #181818 100%)",
        }}
      >
        <div
          aria-hidden
          className="absolute inset-0 opacity-60"
          style={{
            background:
              "radial-gradient(ellipse 80% 60% at 50% 40%, #2a2a2a 0%, transparent 70%)",
          }}
        />
        <div
          aria-hidden
          className="absolute left-1/2 top-1/2 h-[40vh] w-[60vw] -translate-x-1/2 -translate-y-1/2 opacity-20"
          style={{
            background:
              "linear-gradient(135deg, #da291c 0%, transparent 60%)",
            filter: "blur(80px)",
          }}
        />
        <div className="relative mx-auto w-full max-w-[1280px] px-6 pb-24 pt-32">
          <p className="t-uppercase mb-6 text-[color:var(--body)]">
            카카오톡 자동 발송 · 클라우드 백업 · 알림톡
          </p>
          <h1 className="t-display-mega max-w-4xl">
            대량 메시지,
            <br />
            한 명씩 보낸 듯이.
          </h1>
          <p className="t-body-md mt-6 max-w-2xl text-[color:var(--body)]">
            연락처와 템플릿을 클라우드에 안전하게 보관하고,
            카카오톡 PC 자동 발송으로 봇 탐지를 피해 자연스럽게 전달합니다.
            생일 자동 발송, 알림톡, 사용량 통계까지 한 곳에서.
          </p>
          <div className="mt-10 flex flex-wrap gap-4">
            <Link href="/download" className="btn-primary">
              지금 시작
            </Link>
            <Link href="/signup" className="btn-outline">
              회원가입
            </Link>
          </div>
        </div>
      </section>

      {/* ── Features ── */}
      <section
        id="features"
        className="border-y border-[color:var(--hairline)] py-24"
      >
        <div className="mx-auto max-w-[1280px] px-6">
          <p className="t-uppercase text-[color:var(--body)]">Features</p>
          <h2 className="t-display-xl mt-3 max-w-2xl">
            상용 수준의 자동 발송 솔루션.
          </h2>
          <div className="mt-16 grid gap-px bg-[color:var(--hairline)] sm:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map((f) => (
              <div key={f.title} className="bg-[color:var(--canvas)] p-8">
                <div
                  className="mb-6 flex h-10 w-10 items-center justify-center"
                  style={{ background: "var(--primary)" }}
                >
                  <span className="text-lg font-bold">{f.no}</span>
                </div>
                <h3 className="t-title-md">{f.title}</h3>
                <p className="t-body-sm mt-3">{f.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Numbers ── */}
      <section className="bg-[color:var(--canvas-elevated)] py-24">
        <div className="mx-auto grid max-w-[1280px] grid-cols-2 gap-12 px-6 md:grid-cols-4">
          {STATS.map((s) => (
            <div key={s.label}>
              <div
                className="t-number"
                style={{ color: s.accent ? "var(--primary)" : "var(--ink)" }}
              >
                {s.value}
              </div>
              <p className="t-uppercase mt-3 text-[color:var(--body)]">
                {s.label}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* ── Plans (light editorial band) ── */}
      <section
        id="plans"
        className="py-24"
        style={{
          background: "var(--canvas-light)",
          color: "var(--body-on-light)",
        }}
      >
        <div className="mx-auto max-w-[1280px] px-6">
          <p className="t-uppercase" style={{ opacity: 0.6 }}>
            Plans
          </p>
          <h2 className="t-display-xl mt-3 max-w-2xl">
            합리적인 가격, 명확한 정책.
          </h2>
          <div className="mt-16 grid gap-px border border-[color:var(--hairline-on-light)] bg-[color:var(--hairline-on-light)] md:grid-cols-2">
            <PlanCard
              label="월간 구독"
              price="₩19,900"
              period="/ 월"
              features={[
                "카카오톡 PC 자동 발송",
                "연락처/템플릿 클라우드 백업",
                "생일 자동 발송",
                "알림톡 발송 (세종텔레콤)",
                "1대 디바이스",
                "이메일 지원",
              ]}
            />
            <PlanCard
              label="연간 구독"
              price="₩199,000"
              period="/ 년"
              badge="2개월 무료"
              features={[
                "월간 플랜의 모든 기능",
                "우선 지원",
                "신규 기능 베타 액세스",
                "사용량 무제한",
                "전화 지원",
                "맞춤 설정 컨설팅",
              ]}
            />
          </div>
          <p className="t-body-sm mt-8" style={{ color: "var(--muted)" }}>
            * 7일 이내 미사용 시 전액 환불. 카카오페이/토스/카드 결제 지원
            (포트원).
          </p>
        </div>
      </section>

      {/* ── CTA Band ── */}
      <section className="bg-[color:var(--canvas)] py-24">
        <div className="mx-auto max-w-[1280px] px-6 text-center">
          <h2 className="t-display-xl">지금 시작하세요.</h2>
          <p className="t-body-md mt-6 text-[color:var(--body)]">
            가입 후 관리자 승인을 받으면 바로 사용 가능합니다.
          </p>
          <div className="mt-10 flex justify-center gap-4">
            <Link href="/signup" className="btn-primary">
              회원가입
            </Link>
            <Link href="/download" className="btn-outline">
              다운로드
            </Link>
          </div>
        </div>
      </section>

      <Footer />
    </>
  );
}

const FEATURES = [
  { no: "01", title: "카카오톡 PC 자동 발송", body: "Win32 API 기반 PostMessage 클릭 — 마우스 커서 이동 없이 대량 발송. 자연스러운 딜레이로 봇 탐지 회피." },
  { no: "02", title: "95% 정확도 한글 OCR", body: "PaddleOCR 한국어 모델 + 5x Lanczos 전처리. 카카오톡 친구탭의 이름/생일 OCR 검증." },
  { no: "03", title: "클라우드 동기화", body: "연락처/템플릿/발송 이력 실시간 백업. PC 재설치/포맷 후에도 데이터 100% 복구." },
  { no: "04", title: "생일 자동 발송", body: "카톡 친구탭에서 ±1일 생일자 자동 인식 → 템플릿 자동 발송 + DB 빈 생일 자동 채움." },
  { no: "05", title: "알림톡 (세종텔레콤)", body: "공식 알림톡/SMS 발송. 발신프로필 키 등록 후 정식 채널로 합법 발송." },
  { no: "06", title: "라이선스 / 사용량 관리", body: "디바이스 묶기, 일일 한도, 부정 사용 자동 감지. 어드민 패널에서 한 눈에 관리." },
];

const STATS = [
  { value: "95%+", label: "OCR 정확도", accent: false },
  { value: "300", label: "일일 발송 한도", accent: false },
  { value: "100%", label: "클라우드 복구", accent: true },
  { value: "0", label: "데이터 손실", accent: false },
];

function PlanCard({
  label, price, period, features, badge,
}: { label: string; price: string; period: string; features: string[]; badge?: string }) {
  return (
    <div className="bg-[color:var(--canvas-light)] p-10">
      <div className="flex items-baseline justify-between">
        <p className="t-uppercase">{label}</p>
        {badge && (
          <span
            className="t-uppercase rounded-full px-3 py-1 text-[10px]"
            style={{ background: "var(--primary)", color: "#fff" }}
          >
            {badge}
          </span>
        )}
      </div>
      <div className="mt-6 flex items-baseline gap-2">
        <span className="text-[40px] font-medium">{price}</span>
        <span className="t-body-sm" style={{ color: "#666" }}>
          {period}
        </span>
      </div>
      <ul className="mt-8 space-y-3">
        {features.map((f) => (
          <li key={f} className="flex items-start gap-3 text-[14px]">
            <span
              className="mt-2 inline-block h-px w-3 flex-shrink-0"
              style={{ background: "var(--primary)" }}
            />
            {f}
          </li>
        ))}
      </ul>
      <Link href="/signup" className="btn-outline-light mt-8 w-full">
        선택하기
      </Link>
    </div>
  );
}
