"use client";

import Link from "next/link";
import { useRouter, usePathname } from "next/navigation";
import { useEffect } from "react";
import { Button } from "@/components/ui/button";
import { clearToken, getToken } from "@/lib/api";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!getToken()) router.replace("/");
  }, [router]);

  function logout() {
    clearToken();
    router.replace("/");
  }

  const nav = [
    { href: "/dashboard", label: "통계" },
    { href: "/dashboard/users", label: "사용자 관리" },
    { href: "/dashboard/abuse", label: "부정 사용 감지" },
  ];

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b bg-white">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-8">
            <Link href="/dashboard" className="text-lg font-bold">
              TalkPC Pro Admin
            </Link>
            <nav className="flex gap-4">
              {nav.map((n) => (
                <Link
                  key={n.href}
                  href={n.href}
                  className={
                    "text-sm " +
                    (pathname === n.href
                      ? "font-semibold text-slate-900"
                      : "text-slate-500 hover:text-slate-900")
                  }
                >
                  {n.label}
                </Link>
              ))}
            </nav>
          </div>
          <Button variant="outline" size="sm" onClick={logout}>
            로그아웃
          </Button>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-6 py-8">{children}</main>
    </div>
  );
}
