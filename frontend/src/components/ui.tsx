import type { ReactNode } from "react";
import { AlertTriangle, Inbox, Loader2, ShieldCheck } from "lucide-react";

import { LEVEL_META, verdictMeta } from "../lib/labels";
import type { RiskLevel, Verdict } from "../lib/types";
import { cn } from "../lib/utils";

export function Card({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return <section className={cn("card p-5 sm:p-6", className)}>{children}</section>;
}

export function SectionHeading({
  title,
  subtitle,
  action,
}: {
  title: string;
  subtitle?: string;
  action?: ReactNode;
}) {
  return (
    <div className="mb-5 flex items-start justify-between gap-4">
      <div>
        <h2 className="text-base font-semibold text-white">{title}</h2>
        {subtitle ? <p className="mt-1 text-sm text-slate-400">{subtitle}</p> : null}
      </div>
      {action ? <div className="shrink-0">{action}</div> : null}
    </div>
  );
}

export function VerdictBadge({ verdict, short = false }: { verdict: Verdict; short?: boolean }) {
  const meta = verdictMeta(verdict);
  return (
    <span className={cn("chip", meta.badge)}>
      <span className={cn("h-1.5 w-1.5 rounded-full", meta.dot)} />
      {short ? meta.short : meta.label}
    </span>
  );
}

export function LevelBadge({ level }: { level: RiskLevel }) {
  const meta = LEVEL_META[level] ?? LEVEL_META.rendah;
  return <span className={cn("chip", meta.badge)}>{meta.label}</span>;
}

export function ScoreBar({
  score,
  level,
  className,
}: {
  score: number;
  level: RiskLevel;
  className?: string;
}) {
  const meta = LEVEL_META[level] ?? LEVEL_META.rendah;
  return (
    <div className={cn("h-1.5 w-full overflow-hidden rounded-full bg-white/5", className)}>
      <div
        className={cn("h-full rounded-full transition-all duration-700", meta.bar)}
        style={{ width: `${Math.max(2, Math.min(100, score))}%` }}
      />
    </div>
  );
}

export function ScoreRing({
  score,
  level,
  size = 132,
  label = "Risiko",
}: {
  score: number;
  level: RiskLevel;
  size?: number;
  label?: string;
}) {
  const meta = LEVEL_META[level] ?? LEVEL_META.rendah;
  const radius = (size - 14) / 2;
  const circumference = 2 * Math.PI * radius;
  const progress = circumference * (Math.max(0, Math.min(100, score)) / 100);
  const strokeColor = { rendah: "#34d399", sedang: "#fbbf24", tinggi: "#fb923c", kritis: "#fb7185" }[
    level
  ];

  return (
    <div className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="rgba(148,163,184,0.12)"
          strokeWidth={8}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={strokeColor}
          strokeWidth={8}
          strokeLinecap="round"
          strokeDasharray={`${progress} ${circumference - progress}`}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-3xl font-semibold text-white">{score}</span>
        <span className={cn("text-[11px] font-medium uppercase tracking-wider", meta.badge.split(" ").pop())}>
          {label} · {meta.label}
        </span>
      </div>
    </div>
  );
}

export function ConfidencePill({ value }: { value: number }) {
  const percent = Math.round(value * 100);
  const tone = percent >= 65 ? "text-emerald-300" : percent >= 45 ? "text-amber-300" : "text-slate-400";
  return (
    <span className={cn("inline-flex items-center gap-1.5 text-xs", tone)}>
      <ShieldCheck className="h-3.5 w-3.5" />
      Keyakinan {percent}%
    </span>
  );
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-white/10 bg-white/[0.015] px-6 py-12 text-center">
      <div className="mb-3 flex h-11 w-11 items-center justify-center rounded-full border border-white/10 bg-white/5">
        <Inbox className="h-5 w-5 text-slate-400" />
      </div>
      <p className="text-sm font-medium text-slate-200">{title}</p>
      <p className="mt-1 max-w-md text-sm text-slate-500">{description}</p>
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  );
}

export function Spinner({ label = "Memuat data" }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-2 py-16 text-sm text-slate-400">
      <Loader2 className="h-4 w-4 animate-spin text-cyan-300" />
      {label}…
    </div>
  );
}

export function ErrorPanel({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex items-start gap-3 rounded-2xl border border-rose-400/20 bg-rose-400/5 p-5">
      <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-rose-300" />
      <div className="text-sm">
        <p className="font-medium text-rose-200">Gagal memuat data</p>
        <p className="mt-1 text-rose-200/70">{message}</p>
        {onRetry ? (
          <button type="button" onClick={onRetry} className="mt-3 btn-ghost">
            Coba lagi
          </button>
        ) : null}
      </div>
    </div>
  );
}
