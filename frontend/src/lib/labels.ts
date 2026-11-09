import { BrainCircuit, Newspaper, type LucideIcon } from "lucide-react";

import type { SignalCategory, Verdict } from "./types";

export interface VerdictMeta {
  label: string;
  short: string;
  description: string;
  badge: string;
  dot: string;
  hex: string;
}

export const VERDICT_META: Record<Verdict, VerdictMeta> = {
  terindikasi_fakta: {
    label: "Terindikasi Fakta",
    short: "Terindikasi fakta",
    description:
      "Bukti independen secara dominan mendukung klaim, dengan bobot di atas ambang keputusan.",
    badge: "border-emerald-400/30 bg-emerald-400/10 text-emerald-300",
    dot: "bg-emerald-400",
    hex: "#34d399",
  },
  terindikasi_hoaks: {
    label: "Terindikasi Hoaks",
    short: "Terindikasi hoaks",
    description:
      "Bukti independen secara dominan membantah klaim. Tetap indikasi berbasis bukti, bukan putusan hukum.",
    badge: "border-rose-400/30 bg-rose-400/10 text-rose-300",
    dot: "bg-rose-400",
    hex: "#fb7185",
  },
  campuran: {
    label: "Campuran",
    short: "Campuran",
    description:
      "Sebagian klaim didukung dan sebagian dibantah, atau pemeriksa fakta menilai klaim hanya sebagian benar.",
    badge: "border-orange-400/30 bg-orange-400/10 text-orange-300",
    dot: "bg-orange-400",
    hex: "#fb923c",
  },
  perlu_verifikasi: {
    label: "Perlu Verifikasi",
    short: "Perlu verifikasi",
    description:
      "Bukti yang ada belum cukup atau belum konvergen; status klaim belum dapat ditetapkan.",
    badge: "border-amber-400/30 bg-amber-400/10 text-amber-300",
    dot: "bg-amber-400",
    hex: "#fbbf24",
  },
  belum_dapat_dinilai: {
    label: "Belum Dapat Dinilai",
    short: "Belum dinilai",
    description:
      "Belum ada bukti eksternal yang dapat dinilai (layanan tidak aktif, gagal dihubungi, atau tanpa catatan). Mesin tidak menebak.",
    badge: "border-slate-400/20 bg-slate-400/10 text-slate-300",
    dot: "bg-slate-400",
    hex: "#94a3b8",
  },
  // Format lama: hanya muncul pada analisis yang dibuat sebelum engine EBDE.
  terindikasi_menyesatkan: {
    label: "Terindikasi Hoax (format lama)",
    short: "Hoax (lama)",
    description:
      "Verdict heuristik sebelum EBDE. Analisis lama tidak memiliki jejak bukti terstruktur.",
    badge: "border-rose-400/20 bg-rose-400/[0.06] text-rose-300/80",
    dot: "bg-rose-400/60",
    hex: "#fb7185",
  },
  risiko_rendah: {
    label: "Tanpa indikasi hoax (format lama)",
    short: "Risiko rendah (lama)",
    description:
      "Verdict heuristik sebelum EBDE; bukan berarti isi sudah terverifikasi sebagai fakta.",
    badge: "border-emerald-400/20 bg-emerald-400/[0.06] text-emerald-300/80",
    dot: "bg-emerald-400/60",
    hex: "#34d399",
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
  indobert: {
    label: "Model IndoBERT",
    description: "Klasifikasi probabilistik model IndoBERT lokal; ikut menimbang indeks pola narasi (bobot 30%).",
    icon: BrainCircuit,
    hex: "#a78bfa",
  },
};

export const VERDICT_FILTERS: Array<{ value: Verdict | null; label: string }> = [
  { value: null, label: "Semua" },
  { value: "terindikasi_hoaks", label: "Terindikasi Hoaks" },
  { value: "terindikasi_fakta", label: "Terindikasi Fakta" },
  { value: "perlu_verifikasi", label: "Perlu Verifikasi" },
];

export const DECISION_STANCE_META: Record<string, { label: string; badge: string }> = {
  mendukung: {
    label: "Mendukung",
    badge: "border-emerald-400/30 bg-emerald-400/10 text-emerald-300",
  },
  membantah: {
    label: "Membantah",
    badge: "border-rose-400/30 bg-rose-400/10 text-rose-300",
  },
  sebagian: {
    label: "Sebagian benar",
    badge: "border-amber-400/30 bg-amber-400/10 text-amber-300",
  },
  netral: {
    label: "Konteks",
    badge: "border-slate-400/20 bg-slate-400/10 text-slate-300",
  },
};

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

export const CLAIM_EVIDENCE_META: Record<string, { label: string; badge: string }> = {
  didukung: {
    label: "Didukung bukti",
    badge: "border-emerald-400/30 bg-emerald-400/10 text-emerald-300",
  },
  dibantah: {
    label: "Dibantah bukti",
    badge: "border-rose-400/30 bg-rose-400/10 text-rose-300",
  },
  tidak_cukup_bukti: {
    label: "Tidak cukup bukti",
    badge: "border-slate-400/20 bg-slate-400/10 text-slate-300",
  },
};

export function verdictMeta(verdict: Verdict): VerdictMeta {
  return VERDICT_META[verdict] ?? VERDICT_META.perlu_verifikasi;
}
