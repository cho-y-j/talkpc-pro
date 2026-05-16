import Link from "next/link";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE || "https://talkpc-pro.vercel.app";

export function Footer() {
  return (
    <footer className="border-t border-[color:var(--hairline)] bg-[color:var(--canvas)] py-16">
      <div className="mx-auto grid max-w-[1280px] grid-cols-2 gap-8 px-6 md:grid-cols-5">
        <div className="col-span-2">
          <div className="flex items-center gap-3">
            <span
              className="inline-block h-3 w-6"
              style={{ background: "var(--primary)" }}
            />
            <span className="text-[15px] font-medium">
              TALKPC <span className="font-bold">PRO</span>
            </span>
          </div>
          <p className="t-body-sm mt-4 max-w-sm">
            카카오톡 PC 자동 발송 솔루션. 연락처, 템플릿, 알림톡을 한 곳에서
            관리하고 클라우드 백업으로 데이터 손실 없이.
          </p>
        </div>
        <div>
          <h4 className="t-uppercase mb-4 text-white">Product</h4>
          <ul className="space-y-3">
            <li><Link href="/#features" className="t-body-sm hover:text-white">Features</Link></li>
            <li><Link href="/#plans" className="t-body-sm hover:text-white">Pricing</Link></li>
            <li><Link href="/download" className="t-body-sm hover:text-white">Download</Link></li>
          </ul>
        </div>
        <div>
          <h4 className="t-uppercase mb-4 text-white">Account</h4>
          <ul className="space-y-3">
            <li><Link href="/signup" className="t-body-sm hover:text-white">Sign up</Link></li>
            <li><a href={`${API_BASE}/docs`} className="t-body-sm hover:text-white">API Docs</a></li>
          </ul>
        </div>
        <div>
          <h4 className="t-uppercase mb-4 text-white">Legal</h4>
          <ul className="space-y-3">
            <li><a href={`${API_BASE}/terms`} className="t-body-sm hover:text-white">이용약관</a></li>
            <li><a href={`${API_BASE}/privacy`} className="t-body-sm hover:text-white">개인정보처리방침</a></li>
            <li><a href="mailto:support@talkpc-pro.com" className="t-body-sm hover:text-white">Contact</a></li>
          </ul>
        </div>
      </div>
      <div className="mx-auto mt-12 max-w-[1280px] border-t border-[color:var(--hairline)] px-6 pt-6">
        <p className="t-caption">© 2026 TalkPC Pro. All rights reserved.</p>
      </div>
    </footer>
  );
}
