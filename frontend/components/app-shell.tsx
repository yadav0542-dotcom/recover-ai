"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { BackendStatus } from "@/components/backend-status";

const navigation = [
  { href: "/", label: "Dashboard", icon: "⌂" },
  { href: "/payment-simulator", label: "Payment Simulator", icon: "＋" },
  { href: "/recovery-cases", label: "Recovery Cases", icon: "↗" },
  { href: "/audit-logs", label: "Audit Logs", icon: "≡" },
];

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="min-h-screen bg-[#f5f7fa] text-[#172033]">
      <aside className="fixed inset-y-0 left-0 z-20 hidden w-64 border-r border-[#2b3850] bg-[#172033] px-4 py-5 lg:block">
        <Link href="/" className="flex items-center gap-3 px-2">
          <span className="brand-mark">R</span>

          <span>
            <span className="block text-[15px] font-bold tracking-tight text-white">
              RecoverAI
            </span>
            <span className="block text-xs font-medium text-[#9eabc0]">
              Revenue recovery
            </span>
          </span>
        </Link>

        <div className="mt-10 px-2 text-[11px] font-semibold uppercase tracking-wide text-[#718099]">
          Workspace
        </div>

        <nav className="mt-3 space-y-1">
          {navigation.map((item) => {
            const active =
              item.href === "/"
                ? pathname === "/"
                : pathname.startsWith(item.href);

            return (
              <Link
                key={item.href}
                href={item.href}
                className={`nav-link ${active ? "nav-link-active" : ""}`}
              >
                <span className="nav-icon" aria-hidden="true">
                  {item.icon}
                </span>

                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>

        <div className="absolute bottom-5 left-4 right-4 rounded-lg border border-[#34425b] bg-[#202b40] p-4">
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-emerald-400" />
            <p className="text-xs font-semibold text-white">
              Safe by design
            </p>
          </div>

          <p className="mt-2 text-xs leading-5 text-[#9eabc0]">
            Recommendations remain simulated until deterministic policy
            approves execution.
          </p>
        </div>
      </aside>

      <div className="lg:pl-64">
        <header className="sticky top-0 z-10 flex min-h-[64px] items-center justify-between border-b border-[#e2e7ee] bg-white px-5 sm:px-8 lg:px-10">
          <div className="flex items-center gap-3 lg:hidden">
            <span className="brand-mark">R</span>
            <span className="text-sm font-bold text-[#172033]">
              RecoverAI
            </span>
          </div>

          <div className="hidden text-sm font-medium text-[#526071] lg:block">
            Revenue recovery workspace
          </div>

          <BackendStatus />
        </header>

        <main className="page-grid min-h-[calc(100vh-64px)] px-5 py-7 sm:px-8 lg:px-10">
          {children}
        </main>
      </div>
    </div>
  );
}