import type { ReactNode } from "react";
import { AlertTriangle, Inbox, Loader2, ShieldCheck, Trash2 } from "lucide-react";

import { verdictMeta } from "../lib/labels";
import type { Verdict } from "../lib/types";
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

export function ScoreBar({ score, className }: { score: number; className?: string }) {
  return (
    <div className={cn("h-1.5 w-full overflow-hidden rounded-full bg-white/5", className)}>
      <div
        className="h-full rounded-full bg-cyan-400 transition-all duration-700"
        style={{ width: `${Math.max(2, Math.min(100, score))}%` }}
      />
    </div>
  );
}

export function ScoreRing({
  score,
  size = 132,
  label = "Indeks narasi",
}: {
  score: number;
  size?: number;
  label?: string;
}) {
  const radius = (size - 14) / 2;
  const circumference = 2 * Math.PI * radius;
  const progress = circumference * (Math.max(0, Math.min(100, score)) / 100);

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
          stroke="#38bdf8"
          strokeWidth={8}
          strokeLinecap="round"
          strokeDasharray={`${progress} ${circumference - progress}`}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-3xl font-semibold text-white">{score}</span>
        <span className="text-[11px] font-medium uppercase tracking-wider text-cyan-300">
          {label}
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

export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel = "Hapus",
  busy = false,
  error,
  onConfirm,
  onCancel,
}: {
  open: boolean;
  title: string;
  description: string;
  confirmLabel?: string;
  busy?: boolean;
  error?: string | null;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  if (!open) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink-950/80 p-4 backdrop-blur-sm">
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className="w-full max-w-md rounded-2xl border border-white/10 bg-ink-900 p-6 shadow-panel"
      >
        <div className="flex items-start gap-3">
          <span className="mt-0.5 inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-rose-400/20 bg-rose-400/10 text-rose-300">
            <Trash2 className="h-4 w-4" />
          </span>
          <div>
            <h2 className="text-base font-semibold text-white">{title}</h2>
            <p className="mt-1.5 text-sm leading-relaxed text-slate-400">{description}</p>
          </div>
        </div>
        {error ? <p className="mt-4 text-xs text-rose-300">{error}</p> : null}
        <div className="mt-6 flex justify-end gap-2">
          <button type="button" className="btn-ghost" onClick={onCancel} disabled={busy}>
            Batal
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={busy}
            className="inline-flex items-center justify-center gap-2 rounded-xl bg-rose-500 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-rose-400 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
