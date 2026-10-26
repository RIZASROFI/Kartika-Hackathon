import {
  AlertTriangle,
  ArrowRight,
  Bot,
  Database,
  Flame,
  Gauge,
  Globe,
  Link2,
  Network,
  Newspaper,
  ScanText,
  Scale,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { Link } from "react-router-dom";

import { Card, VerdictBadge } from "../components/ui";
import { CATEGORY_META, LEVEL_META, VERDICT_META } from "../lib/labels";
import type { RiskLevel, SignalCategory } from "../lib/types";

const PIPELINE = [
  {
    icon: Link2,
    title: "Ingest",
    text: "Menerima URL artikel atau teks manual. URL divalidasi dan diperiksa terhadap alamat internal (proteksi SSRF).",
  },
  {
    icon: ScanText,
    title: "Ekstraksi",
    text: "Trafilatura mengambil isi utama; BeautifulSoup melengkapi metadata judul, penulis, penerbit, tanggal, dan tautan.",
  },
  {
    icon: Gauge,
    title: "Penilaian",
    text: "Empat modul heuristik menghitung skor independen. Sinyal terkuat mendominasi skor risiko akhir.",
  },
  {
    icon: Network,
    title: "Korelasi",
    text: "Isi dibandingkan dengan korpus tersimpan dalam jendela waktu untuk menemukan reproduksi narasi.",
  },
  {
    icon: Database,
    title: "Penyimpanan",
    text: "Temuan, klaim, tautan bukti, dan relasi koordinasi disimpan untuk audit dan penelusuran lanjutan.",
  },
];

const DIMENSIONS: Array<{ key: SignalCategory; weight: string }> = [
  { key: "hoax", weight: "35%" },
  { key: "provocation", weight: "30%" },
  { key: "coordination", weight: "20%" },
  { key: "bot_ai", weight: "15%" },
];

const LIMITATIONS = [
  "Tidak ada pencocokan otomatis ke basis data fakta eksternal. Status klaim selalu indikatif.",
  "Sinyal bot/AI hanya membaca pola teks; metadata akun, waktu unggah, dan jaringan interaksi belum tersedia.",
  "Leksikon provokasi dapat melewatkan sarkasme, ironi, kutipan berita, atau konteks budaya lokal.",
  "Kemiripan teks yang tinggi tidak membuktikan aktor yang sama; bisa terjadi karena sindikasi berita.",
  "Korpus kecil membuat analisis koordinasi belum reliabel dan keyakinan skor diturunkan.",
];

export default function Methodology() {
  return (
    <div className="space-y-6">
      <div>
        <p className="label">How it works</p>
        <h1 className="mt-1.5 text-2xl font-semibold tracking-tight text-white">
          Metodologi & Batasan
        </h1>
        <p className="mt-1.5 max-w-3xl text-sm leading-relaxed text-slate-400">
          KARTIKA Intel membantu analis memprioritaskan konten yang perlu ditinjau. Platform ini
          tidak menetapkan benar atau salah secara otomatis, dan tidak menuduh individu atau
          organisasi.
        </p>
      </div>

      <Card>
        <div className="mb-5 flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-cyan-300" />
          <h2 className="text-sm font-semibold text-white">Alur pemrosesan</h2>
        </div>
        <ol className="grid gap-4 md:grid-cols-5">
          {PIPELINE.map((step, index) => {
            const Icon = step.icon;
            return (
              <li key={step.title} className="rounded-xl border border-white/5 bg-white/[0.015] p-3.5">
                <div className="flex items-center justify-between">
                  <span className="flex h-7 w-7 items-center justify-center rounded-lg border border-cyan-400/15 bg-cyan-400/10">
                    <Icon className="h-3.5 w-3.5 text-cyan-300" />
                  </span>
                  <span className="font-mono text-[10px] text-slate-600">
                    {String(index + 1).padStart(2, "0")}
                  </span>
                </div>
                <p className="mt-2.5 text-xs font-semibold text-slate-200">{step.title}</p>
                <p className="mt-1 text-[11px] leading-relaxed text-slate-500">{step.text}</p>
              </li>
            );
          })}
        </ol>
      </Card>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)]">
        <Card>
          <h2 className="text-sm font-semibold text-white">Empat dimensi sinyal</h2>
          <p className="mt-1 text-xs text-slate-500">
            Setiap dimensi diskalakan 0–100 dan diberi label tingkat risiko.
          </p>
          <div className="mt-4 space-y-3">
            {DIMENSIONS.map((dimension) => {
              const meta = CATEGORY_META[dimension.key];
              const Icon = meta.icon;
              return (
                <div
                  key={dimension.key}
                  className="flex items-start gap-3 rounded-xl border border-white/5 bg-white/[0.015] p-3.5"
                >
                  <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-white/5 bg-white/[0.03]">
                    <Icon className="h-4 w-4" style={{ color: meta.hex }} />
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="text-xs font-semibold text-slate-200">{meta.label}</p>
                      <span className="rounded-md border border-white/5 bg-white/[0.03] px-1.5 py-0.5 font-mono text-[10px] text-slate-500">
                        bobot {dimension.weight}
                      </span>
                    </div>
                    <p className="mt-1 text-[11px] leading-relaxed text-slate-500">
                      {meta.description}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
          <div className="mt-4 rounded-xl border border-cyan-400/10 bg-cyan-400/[0.03] p-3.5 text-[11px] leading-relaxed text-cyan-100/60">
            <span className="font-semibold text-cyan-200">Rumus skor risiko:</span> 65% sinyal
            terkuat + 35% rata-rata berbobot empat dimensi. Pendekatan ini mencegah satu sinyal
            kritis tenggelam oleh dimensi lain yang tenang.
          </div>
        </Card>

        <div className="space-y-6">
          <Card>
            <h2 className="text-sm font-semibold text-white">Ambang tingkat risiko</h2>
            <ul className="mt-4 space-y-2">
              {(Object.keys(LEVEL_META) as RiskLevel[]).map((level) => {
                const ranges: Record<RiskLevel, string> = {
                  rendah: "0–24",
                  sedang: "25–49",
                  tinggi: "50–74",
                  kritis: "75–100",
                };
                return (
                  <li
                    key={level}
                    className="flex items-center justify-between rounded-lg border border-white/5 bg-white/[0.015] px-3 py-2"
                  >
                    <span className={`chip ${LEVEL_META[level].badge}`}>
                      {LEVEL_META[level].label}
                    </span>
                    <span className="font-mono text-[11px] text-slate-500">
                      {ranges[level]}
                    </span>
                  </li>
                );
              })}
            </ul>
          </Card>

          <Card>
            <h2 className="text-sm font-semibold text-white">Status analisis</h2>
            <ul className="mt-3 space-y-2.5">
              {(Object.keys(VERDICT_META) as Array<keyof typeof VERDICT_META>).map((verdict) => (
                <li key={verdict} className="space-y-1">
                  <VerdictBadge verdict={verdict} short />
                  <p className="text-[11px] leading-relaxed text-slate-500">
                    {VERDICT_META[verdict].description}
                  </p>
                </li>
              ))}
            </ul>
          </Card>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <div className="flex items-center gap-2">
            <Network className="h-4 w-4 text-fuchsia-300" />
            <h2 className="text-sm font-semibold text-white">Cara kerja analisis koordinasi</h2>
          </div>
          <ul className="mt-4 space-y-3 text-xs leading-relaxed text-slate-400">
            <li>
              <span className="font-medium text-slate-200">Representasi teks.</span> Setiap konten
              diubah menjadi shingle 4-kata setelah normalisasi huruf dan tanda baca.
            </li>
            <li>
              <span className="font-medium text-slate-200">Kemiripan.</span> Skor Jaccard mengukur
              irisan shingle antar dua konten. Ambang awal 28%; pasangan di atas ambang disimpan
              sebagai relasi.
            </li>
            <li>
              <span className="font-medium text-slate-200">Jendela waktu.</span> Perbandingan
              dibatasi ±72 jam dari waktu publikasi untuk mengurangi kecocokan acak.
            </li>
            <li>
              <span className="font-medium text-slate-200">Pembaruan dua arah.</span> Saat konten
              baru cocok dengan konten lama, skor koordinasi konten lama ikut dihitung ulang.
            </li>
            <li>
              <span className="font-medium text-slate-200">Interpretasi.</span> Temuan berarti
              narasi direproduksi, bukan bukti aktor yang sama atau operasi terkoordinasi
              terorganisir.
            </li>
          </ul>
        </Card>

        <div className="rounded-2xl border border-amber-400/15 bg-amber-400/[0.04] p-5">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-amber-300" />
            <h2 className="text-sm font-semibold text-amber-200">Batasan yang harus dibaca</h2>
          </div>
          <ul className="mt-4 space-y-2.5">
            {LIMITATIONS.map((limitation) => (
              <li
                key={limitation}
                className="flex gap-2 text-[11px] leading-relaxed text-amber-100/65"
              >
                <span className="mt-1 h-1 w-1 shrink-0 rounded-full bg-amber-300/60" />
                {limitation}
              </li>
            ))}
          </ul>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <div className="flex items-center gap-2">
            <Scale className="h-4 w-4 text-emerald-300" />
            <h2 className="text-sm font-semibold text-white">Etika & tata kelola</h2>
          </div>
          <ul className="mt-4 space-y-2.5 text-xs leading-relaxed text-slate-400">
            <li className="flex gap-2">
              <ShieldCheck className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-300/70" />
              Hasil selalu disertai tingkat keyakinan, daftar bukti, dan daftar batasan.
            </li>
            <li className="flex gap-2">
              <ShieldCheck className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-300/70" />
              Tidak ada label “pasti salah”, “pasti bot”, atau tuduhan terhadap individu.
            </li>
            <li className="flex gap-2">
              <ShieldCheck className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-300/70" />
              Analis manusia memutuskan eskalasi, takedown, atau klarifikasi publik.
            </li>
            <li className="flex gap-2">
              <ShieldCheck className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-300/70" />
              Hanya konten publik yang diberikan pengguna; tidak ada pengambilan data kredensial.
            </li>
          </ul>
        </Card>

        <Card>
          <div className="flex items-center gap-2">
            <Bot className="h-4 w-4 text-violet-300" />
            <h2 className="text-sm font-semibold text-white">Roadmap integrasi LLM</h2>
          </div>
          <p className="mt-2 text-xs leading-relaxed text-slate-400">
            Mesin MVP berjalan sepenuhnya lokal. Lapisan bahasa akan ditambahkan tanpa mengubah
            kontrak API:
          </p>
          <ol className="mt-4 space-y-2.5 text-xs leading-relaxed text-slate-400">
            <li className="flex gap-2">
              <span className="font-mono text-[10px] text-slate-600">01</span>
              Ringkasan klaim dan penalaran verdict dengan kutipan sumber.
            </li>
            <li className="flex gap-2">
              <span className="font-mono text-[10px] text-slate-600">02</span>
              Retrieval bukti dari basis data fakta dan situs resmi.
            </li>
            <li className="flex gap-2">
              <span className="font-mono text-[10px] text-slate-600">03</span>
              Penjelasan multibahasa dan laporan investigasi siap unduh.
            </li>
            <li className="flex gap-2">
              <span className="font-mono text-[10px] text-slate-600">04</span>
              Klasifikasi sinyal akun dengan data aktivitas yang tersedia secara sah.
            </li>
          </ol>
          <div className="mt-4 flex flex-wrap gap-2">
            <span className="chip border-white/10 bg-white/5 text-slate-400">
              <Newspaper className="h-3 w-3" /> Hoax
            </span>
            <span className="chip border-white/10 bg-white/5 text-slate-400">
              <Flame className="h-3 w-3" /> Provokasi
            </span>
            <span className="chip border-white/10 bg-white/5 text-slate-400">
              <Globe className="h-3 w-3" /> Multibahasa
            </span>
          </div>
        </Card>
      </div>

      <div className="flex flex-col items-start justify-between gap-3 rounded-xl border border-white/5 bg-white/[0.02] px-4 py-3.5 sm:flex-row sm:items-center">
        <p className="text-xs text-slate-500">
          Siap mencoba alurnya pada konten Anda sendiri?
        </p>
        <Link
          to="/analisis/baru"
          className="inline-flex items-center gap-1.5 text-xs font-medium text-cyan-300 hover:text-cyan-200"
        >
          Jalankan analisis <ArrowRight className="h-3.5 w-3.5" />
        </Link>
      </div>
    </div>
  );
}
