import Link from "next/link";

export function Nav() {
  return (
    <nav className="border-b border-[color:var(--hairline)] bg-[color:var(--canvas)]">
      <div className="mx-auto flex h-16 max-w-[1280px] items-center justify-between px-6">
        <Link href="/" className="flex items-center gap-3">
          <span
            className="inline-block h-3 w-6"
            style={{ background: "var(--primary)" }}
          />
          <span className="text-[15px] font-medium tracking-wide">
            TALKPC <span className="font-bold">PRO</span>
          </span>
        </Link>

        <div className="hidden gap-8 md:flex">
          <Link href="/#features" className="nav-link">Features</Link>
          <Link href="/#plans" className="nav-link">Plans</Link>
          <Link href="/download" className="nav-link">Download</Link>
        </div>

        <div className="flex items-center gap-3">
          <Link href="/signup" className="nav-link hidden sm:inline">
            Sign up
          </Link>
          <Link
            href="/download"
            className="btn-primary h-10 px-5 text-[12px]"
            style={{ height: 40 }}
          >
            Get Started
          </Link>
        </div>
      </div>
    </nav>
  );
}
