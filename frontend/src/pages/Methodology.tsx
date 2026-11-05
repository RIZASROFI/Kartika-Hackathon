import {
  AlertTriangle,
  ArrowRight,
  Database,
  Gauge,
  Globe,
  Link2,
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
    title: "Ingest & validasi",
    service: "Lokal",
    text: "URL diperiksa (http/https, tanpa host atau IP internal, batas 3 MB) atau teks manual minimal 8 kata diterima.",
  },
  {
    icon: ScanText,
    title: "Ekstraksi isi",
    service: "Trafilatura + BeautifulSoup",
    text: "Isi utama artikel diambil; metadata judul, penulis, penerbit, tanggal, dan sampai 5 tautan referensi dilengkapi.",
  },
  {
    icon: Gauge,
    title: "Analisis heuristik",
    service: "Lokal",
    text: "Sinyal hoaks & fakta dihitung dan kandidat klaim diekstrak dari kalimat yang memuat penanda klaim atau angka.",
  },
  {
    icon: ShieldCheck,
    title: "Pemeriksaan fakta",
    service: "MAFINDO + Google Fact Check",
    text: "Judul dan klaim dicari ke Yudistira/MAFINDO dan indeks ClaimReview; hasil disaring memakai kemiripan kata dan angka agar tetap relevan.",
  },
  {
    icon: Sparkles,
    title: "Verifikasi klaim",
    service: "Exa + Gemini",
    text: "Exa mengambil cuplikan sumber terbuka, lalu Gemini menilai tiap klaim hanya dari cuplikan tersebut dan wajib menyertakan sitasi.",
  },
  {
    icon: Scale,
    title: "Keputusan berbasis bukti",
    service: "EBDE (lokal)",
    text: "Temuan cek fakta dicocokkan dulu ke klaim konten; yang membahas klaim lain menjadi konteks. Setiap bukti dinilai dari relevansi, kredibilitas penerbit, kebaruan, dan independensi domain. Konflik dideteksi, duplikat tidak dihitung, dan verdict ditahan bila bukti belum cukup.",
  },
  {
    icon: Database,
    title: "Penyimpanan",
    service: "Basis data",
    text: "Temuan, klaim, sitasi, bukti, dan jejak keputusan EBDE disimpan untuk audit dan penelusuran lanjutan.",
  },
];

const SERVICES = [
  {
    icon: Gauge,
    name: "Mesin heuristik (lokal)",
    text: "Sinyal hoaks & fakta dan ekstraksi kandidat klaim berjalan di server tanpa memanggil API eksternal.",
  },
  {
    icon: ScanText,
    name: "Trafilatura + BeautifulSoup",
    text: "Mengambil isi utama halaman dan metadata judul, penulis, penerbit, tanggal, serta tautan referensi.",
  },
  {
    icon: ShieldCheck,
    name: "MAFINDO Yudistira + Google Fact Check",
    text: "Menanyakan apakah klaim sudah diperiksa lembaga pemeriksa fakta Indonesia maupun global. Hasil di-cache 7 hari dan menjadi bukti bagi EBDE.",
  },
  {
    icon: ScanText,
    name: "IndoBERT lokal (pembanding)",
    text: "Mengklasifikasi gaya narasi per jendela 512 token. Skornya ditampilkan sebagai pembanding dan tidak pernah dipakai sebagai bukti kebenaran.",
  },
  {
    icon: Globe,
    name: "Exa — pencarian sumber terbuka",
    text: "Mengambil cuplikan halaman publik untuk tiap klaim: maksimal 2 klaim × 3 hasil, cuplikan 600 karakter. Tanpa klaim, kueri memakai judul atau kalimat pertama.",
  },
  {
    icon: Sparkles,
    name: "Gemini — penilai klaim",
    text: "Menilai status klaim (didukung, dibantah, tidak cukup bukti) hanya dari cuplikan Exa, memberi alasan maksimal 40 kata, dan wajib menyertakan URL sitasi yang benar-benar ada di hasil pencarian.",
  },
  {
    icon: Scale,
    name: "Evidence-Based Decision Engine",
    text: "Mencocokkan klaim temuan cek fakta dengan konten, menimbang bukti (relevansi × kredibilitas × kebaruan), menghitung tiap domain independen sekali, mendeteksi konflik, lalu memilih satu dari lima verdict — atau menahan verdict.",
  },
  {
    icon: Database,
    name: "Basis data lokal",
    text: "Menyimpan analisis, sinyal, klaim, sitasi, bukti, jejak keputusan, dan cache pemeriksaan fakta.",
  },
];

const DIMENSIONS: Array<{ key: SignalCategory; weight: string }> = [
  { key: "hoax", weight: "penentu risiko" },
  { key: "indobert", weight: "pembanding" },
];

const LIMITATIONS = [
  "Pemeriksaan fakta eksternal bergantung pada cakupan MAFINDO dan Google Fact Check Tools; ketiadaan catatan bukan bukti kebenaran.",
  "Status klaim dinilai model bahasa (Gemini) dari cuplikan Exa; model dapat salah membaca sumber, sehingga setiap sitasi wajib dibuka analis.",
  "Kesetaraan klaim temuan cek fakta juga dinilai model bahasa; temuan yang membahas klaim lain dapat ditandai konteks secara keliru, dan sebaliknya. Analis tetap wajib membuka tautan cek fakta.",
  "Pencarian Exa hanya menjangkau halaman publik yang terindeks; konten berbayar, tertutup, atau belum terindeks tidak terjangkau.",
  "Kredibilitas penerbit memakai daftar tingkatan yang dapat berubah; domain yang tidak dikenal dinilai netral, bukan otomatis dipercaya.",
  "Independensi diukur per domain. Sindikasi yang memakai domain berbeda tetap dapat terhitung sebagai dua sumber.",
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
          organisasi. Layanan eksternal yang dipakai hanya Google Fact Check Tools, Exa, dan Gemini;
          sisanya berjalan lokal di server.
        </p>
      </div>

      <Card>
        <div className="mb-5 flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-cyan-300" />
          <h2 className="text-sm font-semibold text-white">Alur pemrosesan</h2>
        </div>
        <ol className="space-y-2.5">
          {PIPELINE.map((step, index) => {
            const Icon = step.icon;
            return (
              <li
                key={step.title}
                className="flex gap-3 rounded-xl border border-white/5 bg-white/[0.015] p-3.5"
              >
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-cyan-400/15 bg-cyan-400/10">
                  <Icon className="h-4 w-4 text-cyan-300" />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="text-xs font-semibold text-slate-200">{step.title}</p>
                    <div className="flex items-center gap-2">
                      <span className="rounded-md border border-white/5 bg-white/[0.03] px-1.5 py-0.5 font-mono text-[10px] text-slate-500">
                        {step.service}
                      </span>
                      <span className="font-mono text-[10px] text-slate-600">
                        {String(index + 1).padStart(2, "0")}
                      </span>
                    </div>
                  </div>
                  <p className="mt-1 text-[11px] leading-relaxed text-slate-500">{step.text}</p>
                </div>
              </li>
            );
          })}
        </ol>
      </Card>

      <Card>
        <div className="mb-5 flex items-center gap-2">
          <Globe className="h-4 w-4 text-cyan-300" />
          <h2 className="text-sm font-semibold text-white">Layanan & data yang digunakan</h2>
        </div>
        <div className="grid gap-3 md:grid-cols-2">
          {SERVICES.map((service) => {
            const Icon = service.icon;
            return (
              <div
                key={service.name}
                className="flex gap-3 rounded-xl border border-white/5 bg-white/[0.015] p-3.5"
              >
                <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-white/5 bg-white/[0.03]">
                  <Icon className="h-4 w-4 text-slate-300" />
                </span>
                <div className="min-w-0">
                  <p className="text-xs font-semibold text-slate-200">{service.name}</p>
                  <p className="mt-1 text-[11px] leading-relaxed text-slate-500">
                    {service.text}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
        <p className="mt-4 border-t border-white/5 pt-3 text-[11px] leading-relaxed text-slate-500">
          Tanpa kunci API, langkah Google Fact Check, Exa, dan Gemini dilewati secara otomatis dan
          laporan mencantumkan batasannya. Endpoint serta model bahasa diatur lewat
          <span className="font-mono text-slate-400"> LLM_BASE_URL</span> dan
          <span className="font-mono text-slate-400"> LLM_MODEL</span> (API kompatibel OpenAI).
        </p>
      </Card>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)]">
        <Card>
          <h2 className="text-sm font-semibold text-white">Sinyal hoaks &amp; fakta</h2>
          <p className="mt-1 text-xs text-slate-500">
            Skala 0–100 dengan label tingkat risiko.
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
            <span className="font-semibold text-cyan-200">Dua angka yang berbeda:</span> skor
            risiko (0–100) mengukur pola penyebaran dari sinyal narasi. Verdict faktual
            (Terindikasi Fakta/Hoaks, Campuran, Perlu Verifikasi, Belum Dapat Dinilai) dihitung
            EBDE dari bukti eksternal saja, sehingga arah keduanya bisa berbeda.
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
            <p className="mt-1 text-[11px] leading-relaxed text-slate-500">
              Ditetapkan EBDE. Ambang: bobot sisi dominan ≥ 0,60 dan dominasi ≥ 70%; bila tidak
              ada pembanding, dua domain independen dengan bobot ≥ 0,40 sudah memutuskan; konflik
              bila sisi lemah ≥ 50% sisi kuat; minimal dua domain independen (kecuali satu temuan
              lembaga cek fakta dengan kredibilitas ≥ 0,90 dan relevansi ≥ 0,60).
            </p>
            <ul className="mt-3 space-y-2.5">
              {(Object.keys(VERDICT_META) as Array<keyof typeof VERDICT_META>)
                .filter(
                  (verdict) =>
                    verdict !== "terindikasi_menyesatkan" && verdict !== "risiko_rendah",
                )
                .map((verdict) => (
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
              Tidak ada label “pasti salah” atau tuduhan terhadap individu.
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
            <Sparkles className="h-4 w-4 text-violet-300" />
            <h2 className="text-sm font-semibold text-white">Verifikasi klaim berbasis AI</h2>
          </div>
          <p className="mt-2 text-xs leading-relaxed text-slate-400">
            Penilaian sinyal tetap berjalan lokal. Hanya pemeriksaan fakta Google dan verifikasi
            klaim Exa + Gemini yang memanggil layanan eksternal:
          </p>
          <ol className="mt-4 space-y-2.5 text-xs leading-relaxed text-slate-400">
            <li className="flex gap-2">
              <span className="font-mono text-[10px] text-slate-600">01</span>
              <span>
                <span className="font-medium text-slate-200">Retrieval.</span> Exa mencari sumber
                terbuka untuk tiap klaim (maksimal 2 klaim, 3 hasil per klaim); bila tidak ada
                klaim, judul atau kalimat pertama dipakai sebagai kueri.
              </span>
            </li>
            <li className="flex gap-2">
              <span className="font-mono text-[10px] text-slate-600">02</span>
              <span>
                <span className="font-medium text-slate-200">Penilaian.</span> Gemini menilai klaim
                hanya dari cuplikan yang diberikan dan mengembalikan JSON berisi status, alasan,
                dan daftar sitasi.
              </span>
            </li>
            <li className="flex gap-2">
              <span className="font-mono text-[10px] text-slate-600">03</span>
              <span>
                <span className="font-medium text-slate-200">Validasi sitasi.</span> URL harus
                cocok dengan hasil pencarian; status tanpa sitasi valid otomatis diturunkan menjadi
                “tidak cukup bukti”. Hanya sumber yang dikutip disimpan sebagai bukti.
              </span>
            </li>
            <li className="flex gap-2">
              <span className="font-mono text-[10px] text-slate-600">04</span>
              <span>
                <span className="font-medium text-slate-200">Ketahanan.</span> Kegagalan jaringan
                atau kuota dicatat sebagai status di laporan, dan analisis heuristik tetap selesai.
              </span>
            </li>
          </ol>
          <p className="mt-4 border-t border-white/5 pt-3 text-[11px] leading-relaxed text-slate-500">
            Basis data cek fakta MAFINDO (Yudistira) dicari berdampingan dengan Google Fact Check,
            sehingga temuan dari pemeriksa fakta Indonesia ikut tampil sebagai bukti pendukung.
            Rencana berikutnya: penjelasan multibahasa, laporan siap unduh, dan klasifikasi sinyal
            akun.
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            <span className="chip border-white/10 bg-white/5 text-slate-400">
              <Newspaper className="h-3 w-3" /> Hoax
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
