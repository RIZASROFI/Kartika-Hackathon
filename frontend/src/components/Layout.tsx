import { useState } from "react";
import {
  BookOpen,
  History,
  LayoutDashboard,
  Menu,
  ScanLine,
  ShieldCheck,
  X,
} from "lucide-react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";

import { cn } from "../lib/utils";

const NAV_ITEMS = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, exact: true },
  { to: "/analisis/baru", label: "Analisis Baru", icon: ScanLine, exact: true },
  { to: "/analisis", label: "Riwayat Analisis", icon: History, exact: false },
  { to: "/metodologi", label: "Metodologi", icon: BookOpen, exact: true },
];

function navActive(pathname: string, to: string, exact: boolean): boolean {
  if (to === "/") {
    return pathname === "/";
  }
  if (to === "/analisis") {
    return pathname.startsWith("/analisis") && pathname !== "/analisis/baru";
  }
  return exact ? pathname === to : pathname.startsWith(to);
}

function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  const { pathname } = useLocation();

  return (
    <div className="flex h-full flex-col">
      <Link to="/" onClick={onNavigate} className="flex items-center gap-3 px-2">
        <span className="flex h-10 w-10 items-center justify-center rounded-xl border border-cyan-400/30 bg-cyan-400/10">
          <ShieldCheck className="h-5 w-5 text-cyan-300" />
        </span>
        <span>
          <span className="block text-sm font-semibold tracking-[0.22em] text-white">KARTIKA</span>
          <span className="block text-[10px] font-medium uppercase tracking-[0.3em] text-cyan-400/80">
            Intel
          </span>
        </span>
      </Link>

      <p className="mt-9 px-3 text-[10px] font-semibold uppercase tracking-[0.2em] text-slate-600">
        Workspace
      </p>
      <nav className="mt-3 space-y-1">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const active = navActive(pathname, item.to, item.exact);
          return (
            <NavLink
              key={item.to}
              to={item.to}
              onClick={onNavigate}
              className={cn(
                "flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition",
                active
                  ? "bg-cyan-400/10 font-medium text-cyan-200 shadow-[inset_0_0_0_1px_rgba(34,211,238,0.18)]"
                  : "text-slate-400 hover:bg-white/5 hover:text-slate-100",
              )}
            >
              <Icon className={cn("h-4 w-4", active ? "text-cyan-300" : "text-slate-500")} />
              {item.label}
            </NavLink>
          );
        })}
      </nav>

      <div className="mt-auto space-y-3">
        <div className="rounded-xl border border-white/5 bg-white/[0.02] p-3.5">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">
              Mesin
            </span>
            <span className="rounded-full border border-cyan-400/20 bg-cyan-400/10 px-2 py-0.5 text-[10px] font-medium text-cyan-300">
              heuristic-1.0
            </span>
          </div>
          <p className="mt-2 text-xs leading-relaxed text-slate-500">
            Skor bersifat indikatif. Verifikasi analis tetap diperlukan sebelum tindakan.
          </p>
        </div>
        <p className="px-1 text-[10px] uppercase tracking-[0.2em] text-slate-600">
          Kartika Cyber Hackathon 2026
        </p>
      </div>
    </div>
  );
}

export default function Layout() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const today = new Intl.DateTimeFormat("id-ID", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  }).format(new Date());

  return (
    <div className="min-h-screen">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-[264px] border-r border-white/5 bg-ink-950/80 px-5 py-6 backdrop-blur lg:block">
        <SidebarContent />
      </aside>

      <header className="sticky top-0 z-20 flex items-center justify-between gap-3 border-b border-white/5 bg-ink-950/85 px-4 py-3 backdrop-blur lg:hidden">
        <button
          type="button"
          onClick={() => setMobileOpen(true)}
          className="rounded-lg border border-white/10 p-2 text-slate-300"
          aria-label="Buka menu"
        >
          <Menu className="h-4 w-4" />
        </button>
        <div className="flex items-center gap-2">
          <ShieldCheck className="h-4 w-4 text-cyan-300" />
          <span className="text-sm font-semibold tracking-[0.2em] text-white">KARTIKA INTEL</span>
        </div>
        <div className="w-8" />
      </header>

      {mobileOpen ? (
        <div className="fixed inset-0 z-40 lg:hidden">
          <button
            type="button"
            aria-label="Tutup menu"
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            onClick={() => setMobileOpen(false)}
          />
          <div className="absolute inset-y-0 left-0 w-[280px] border-r border-white/10 bg-ink-950 px-5 py-6">
            <button
              type="button"
              onClick={() => setMobileOpen(false)}
              className="absolute right-4 top-5 rounded-lg border border-white/10 p-1.5 text-slate-400"
              aria-label="Tutup menu"
            >
              <X className="h-4 w-4" />
            </button>
            <SidebarContent onNavigate={() => setMobileOpen(false)} />
          </div>
        </div>
      ) : null}

      <div className="lg:pl-[264px]">
        <div className="hidden items-center justify-between border-b border-white/5 px-8 py-3.5 lg:flex">
          <p className="text-xs text-slate-500">
            Digital Information Threat Intelligence ·{" "}
            <span className="text-slate-400">{today}</span>
          </p>
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1.5 rounded-full border border-amber-400/20 bg-amber-400/5 px-2.5 py-1 text-[11px] font-medium text-amber-300/90">
              <span className="h-1.5 w-1.5 rounded-full bg-amber-400" />
              Data demo sintetis
            </span>
          </div>
        </div>
        <main className="mx-auto w-full max-w-7xl px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
