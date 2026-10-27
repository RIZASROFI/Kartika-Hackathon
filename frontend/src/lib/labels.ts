import {
  Bot,
  Flame,
  Newspaper,
  Network,
  type LucideIcon,
} from "lucide-react";

import type { RiskLevel, SignalCategory, Verdict } from "./types";

export interface VerdictMeta {
  label: string;
  short: string;
  description: string;
  badge: string;
  dot: string;
  hex: string;
}

export const VERDICT_META: Record<Verdict, VerdictMeta> = {
  terkoordinasi: {
    label: "Indikasi aktivitas terkoordinasi",
    short: "Terkoordinasi",
    description: "Narasi serupa tersebar berdekatan waktu melalui beberapa kanal.",
    badge: "border-fuchsia-400/30 bg-fuchsia-400/10 text-fuchsia-300",
    dot: "bg-fuchsia-400",
    hex: "#e879f9",
  },
  terindikasi_menyesatkan: {
    label: "Terindikasi Hoax",
    short: "Terindikasi Hoax",
    description: "Kelemahan atribusi dan pola amplifikasi mengarah pada indikasi hoax.",
    badge: "border-rose-400/30 bg-rose-400/10 text-rose-300",
    dot: "bg-rose-400",
    hex: "#fb7185",
  },
  provokatif: {
    label: "Provokatif",
    short: "Provokatif",
    description: "Mengandung ajakan, ancaman, atau bahasa yang memicu eskalasi.",
    badge: "border-orange-400/30 bg-orange-400/10 text-orange-300",
    dot: "bg-orange-400",
    hex: "#fb923c",
  },
  perlu_verifikasi: {
    label: "Perlu verifikasi",
    short: "Perlu verifikasi",
    description: "Ada sinyal risiko yang belum cukup untuk menyimpulkan status klaim.",
    badge: "border-amber-400/30 bg-amber-400/10 text-amber-300",
    dot: "bg-amber-400",
    hex: "#fbbf24",
  },
  risiko_rendah: {
    label: "Terindikasi Fakta",
    short: "Terindikasi Fakta",
    description: "Tidak ditemukan indikasi hoax yang kuat; konten terindikasi mengarah pada fakta.",
    badge: "border-emerald-400/30 bg-emerald-400/10 text-emerald-300",
    dot: "bg-emerald-400",
    hex: "#34d399",
  },
};

export const LEVEL_META: Record<RiskLevel, { label: string; badge: string; bar: string }> = {
  rendah: {
    label: "Rendah",
    badge: "border-emerald-400/30 bg-emerald-400/10 text-emerald-300",
    bar: "bg-emerald-400",
  },
  sedang: {
    label: "Sedang",
    badge: "border-amber-400/30 bg-amber-400/10 text-amber-300",
    bar: "bg-amber-400",
  },
  tinggi: {
    label: "Tinggi",
    badge: "border-orange-400/30 bg-orange-400/10 text-orange-300",
    bar: "bg-orange-400",
  },
  kritis: {
    label: "Kritis",
    badge: "border-rose-400/30 bg-rose-400/10 text-rose-300",
    bar: "bg-rose-400",
  },
};

export interface CategoryMeta {
  label: string;
  description: string;
  icon: LucideIcon;
  hex: string;
}

export const CATEGORY_META: Record<SignalCategory, CategoryMeta> = {
  hoax: {
    label: "Hoax & Fakta",
    description: "Atribusi sumber, sensasionalisme, dan tekanan menyebarkan.",
    icon: Newspaper,
    hex: "#38bdf8",
  },
  provocation: {
    label: "Provokasi",
    description: "Leksikon kekerasan, polarisasi, dan ajakan eskalasi.",
    icon: Flame,
    hex: "#fb923c",
  },
  coordination: {
    label: "Koordinasi",
    description: "Kemiripan narasi dan kedekatan waktu publikasi.",
    icon: Network,
    hex: "#e879f9",
  },
  bot_ai: {
    label: "Bot & AI",
    description: "Pola templat, keseragaman kalimat, dan penanda konten generatif.",
    icon: Bot,
    hex: "#a78bfa",
  },
};

export const VERDICT_FILTERS: Array<{ value: Verdict | null; label: string }> = [
  { value: null, label: "Semua" },
  { value: "terkoordinasi", label: "Terkoordinasi" },
  { value: "terindikasi_menyesatkan", label: "Terindikasi Hoax" },
  { value: "provokatif", label: "Provokatif" },
  { value: "perlu_verifikasi", label: "Perlu verifikasi" },
  { value: "risiko_rendah", label: "Terindikasi Fakta" },
];

export const CLAIM_VERDICT_META: Record<string, { label: string; badge: string }> = {
  terindikasi_menyesatkan: {
    label: "Terindikasi Hoax",
    badge: "border-rose-400/30 bg-rose-400/10 text-rose-300",
  },
  perlu_verifikasi: {
    label: "Perlu verifikasi",
    badge: "border-amber-400/30 bg-amber-400/10 text-amber-300",
  },
  belum_diverifikasi: {
    label: "Belum diverifikasi",
    badge: "border-slate-400/20 bg-slate-400/10 text-slate-300",
  },
};

export function verdictMeta(verdict: Verdict): VerdictMeta {
  return VERDICT_META[verdict] ?? VERDICT_META.perlu_verifikasi;
}
