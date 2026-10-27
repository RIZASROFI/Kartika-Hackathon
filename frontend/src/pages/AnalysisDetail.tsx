import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowLeft,
  ArrowUpRight,
  Clock,
  ExternalLink,
  FileText,
  Link2,
  Network,
  ShieldAlert,
  ShieldCheck,
} from "lucide-react";
import { Link, useParams } from "react-router-dom";

import {
  Card,
  ConfidencePill,
  EmptyState,
  ErrorPanel,
  LevelBadge,
  ScoreBar,
  ScoreRing,
  SectionHeading,
  Spinner,
  VerdictBadge,
} from "../components/ui";
import { api } from "../lib/api";
import { CATEGORY_META, CLAIM_VERDICT_META, verdictMeta } from "../lib/labels";
import type { Evidence, FactCheckSummary, FactCheckVerdict } from "../lib/types";
import { cn, formatDate, formatPercent, hoursLabel } from "../lib/utils";

const EVIDENCE_KIND_LABEL: Record<string, string> = {
  sumber_utama: "Sumber utama",
  input_pengguna: "Input pengguna",
  tautan: "Tautan referensi",
  factcheck: "Pemeriksaan fakta",
};

const FACTCHECK_META: Record<FactCheckVerdict, { label: string; badge: string }> = {
  hoax: {
    label: "Hoax / tidak benar",
    badge: "border-rose-400/30 bg-rose-400/10 text-rose-300",
  },
  sebagian_benar: {
    label: "Sebagian benar",
    badge: "border-amber-400/30 bg-amber-400/10 text-amber-300",
  },
  fakta: {
    label: "Benar / fakta",
    badge: "border-emerald-400/30 bg-emerald-400/10 text-emerald-300",
  },
  tidak_jelas: {
    label: "Perlu ditelaah",
    badge: "border-slate-400/20 bg-slate-400/10 text-slate-300",
  },
};

function FactCheckCard({ factcheck }: { factcheck: Partial<FactCheckSummary> | undefined }) {
  const status = factcheck?.status;
  if (!status || status === "disabled") {
    return null;
  }

  const hits = factcheck?.hits ?? [];

  return (
    <Card>
      <SectionHeading
        title="Verifikasi fakta eksternal"
        subtitle="Google Fact Check Tools · klaim yang sudah diperiksa pihak lain"
      />
      {status === "matched" ? (
        <ul className="space-y-2.5">
          {hits.map((hit) => {
            const meta = FACTCHECK_META[hit.status] ?? FACTCHECK_META.tidak_jelas;
            return (
              <li
                key={`${hit.url}-${hit.rating}`}
                className="rounded-xl border border-white/5 bg-white/[0.015] p-3.5"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <span className={cn("chip", meta.badge)}>{meta.label}</span>
                  <span className="text-[11px] text-slate-500">{hit.rating}</span>
                </div>
                <p className="mt-2 line-clamp-3 text-xs leading-relaxed text-slate-300">
                  {hit.claim}
                </p>
                <p className="mt-2 text-[11px] text-slate-500">
                  {hit.publisher} · {formatDate(hit.review_date, false)}
                </p>
                {hit.url ? (
                  <a
                    href={hit.url}
                    target="_blank"
                    rel="noreferrer noopener"
                    className="mt-2 inline-flex items-center gap-1 text-[11px] font-medium text-cyan-400/80 hover:text-cyan-300"
                  >
                    Buka pemeriksaan <ExternalLink className="h-3 w-3" />
                  </a>
                ) : null}
              </li>
            );
          })}
        </ul>
      ) : status === "no_match" ? (
        <p className="text-xs leading-relaxed text-slate-500">
          Belum ada pemeriksaan fakta publik yang cocok dengan klaim pada konten ini.
          Ketiadaan catatan bukan bukti kebenaran.
        </p>
      ) : (
        <p className="text-xs leading-relaxed text-amber-200/70">
          {factcheck?.message ??
            "Layanan pemeriksaan fakta eksternal tidak dapat dihubungi saat analisis dibuat."}
        </p>
      )}
      <p className="mt-3 flex items-start gap-1.5 border-t border-white/5 pt-3 text-[11px] leading-relaxed text-slate-500">
        <ShieldCheck className="mt-0.5 h-3 w-3 shrink-0 text-cyan-400/70" />
        Hasil pemeriksaan pihak ketiga ditampilkan sebagai bukti pendukung, bukan pengganti
        penilaian analis.
      </p>
    </Card>
  );
}

function EvidenceRow({ item }: { item: Evidence }) {
  return (
    <li className="rounded-xl border border-white/5 bg-white/[0.015] p-3.5">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-medium text-slate-200">
            {item.url ? (
              <a
                href={item.url}
                target="_blank"
                rel="noreferrer noopener"
                className="inline-flex items-center gap-1.5 hover:text-cyan-300"
              >
                {item.title}
                <ExternalLink className="h-3 w-3 shrink-0" />
              </a>
            ) : (
              item.title
            )}
          </p>
          <p className="mt-1 text-[11px] text-slate-500">
            {EVIDENCE_KIND_LABEL[item.kind] ?? item.kind}
            {item.publisher ? ` · ${item.publisher}` : ""} · diambil {formatDate(item.retrieved_at, false)}
          </p>
          {item.snippet ? (
            <p className="mt-2 line-clamp-3 text-xs leading-relaxed text-slate-500">{item.snippet}</p>
          ) : null}
        </div>
      </div>
    </li>
  );
}

export default function AnalysisDetail() {
  const { id } = useParams<{ id: string }>();
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["analysis", id],
    queryFn: () => api.getAnalysis(id as string),
    enabled: Boolean(id),
  });

  if (isLoading) {
    return <Spinner label="Memuat laporan analisis" />;
  }

  if (isError || !data) {
    return (
      <div className="space-y-4">
        <Link to="/analisis" className="btn-ghost w-fit">
          <ArrowLeft className="h-4 w-4" /> Kembali
        </Link>
        <ErrorPanel
          message={error instanceof Error ? error.message : "Analisis tidak ditemukan."}
          onRetry={() => void refetch()}
        />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <Link to="/analisis" className="btn-ghost w-fit">
        <ArrowLeft className="h-4 w-4" /> Riwayat analisis
      </Link>

      <Card className="relative overflow-hidden">
        <div
          className="pointer-events-none absolute -right-24 -top-28 h-64 w-64 rounded-full opacity-20 blur-3xl"
          style={{ background: verdictMeta(data.verdict).hex }}
        />
        <div className="relative grid gap-6 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <VerdictBadge verdict={data.verdict} />
              <LevelBadge level={data.risk_level} />
              <span className="chip border-white/10 bg-white/5 text-slate-400">
                <Clock className="h-3 w-3" />
                {formatDate(data.created_at)}
              </span>
            </div>
            <h1 className="mt-3 text-xl font-semibold leading-snug tracking-tight text-white sm:text-2xl">
              {data.title}
            </h1>
            <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-slate-500">
              <span className="inline-flex items-center gap-1.5">
                {data.source_type === "url" ? (
                  <Link2 className="h-3.5 w-3.5" />
                ) : (
                  <FileText className="h-3.5 w-3.5" />
                )}
                {data.publisher ?? "Input manual"}
              </span>
              {data.content.url ? (
                <a
                  href={data.content.url}
                  target="_blank"
                  rel="noreferrer noopener"
                  className="inline-flex items-center gap-1 text-cyan-400/80 hover:text-cyan-300"
                >
                  Buka sumber <ExternalLink className="h-3 w-3" />
                </a>
              ) : null}
              <span>{data.content.word_count} kata</span>
              <span>Mesin {data.engine_version}</span>
              <span>{data.processing_ms} ms</span>
            </div>
            <p className="mt-4 max-w-3xl text-sm leading-relaxed text-slate-300">{data.summary}</p>
            <div className="mt-4 flex flex-wrap items-center gap-3">
              <ConfidencePill value={data.confidence} />
              {data.related.length ? (
                <span className="inline-flex items-center gap-1.5 text-xs text-fuchsia-300">
                  <Network className="h-3.5 w-3.5" />
                  {data.related.length} konten terkait terdeteksi
                </span>
              ) : null}
            </div>
          </div>
          <div className="flex justify-center lg:justify-end">
            <ScoreRing score={data.risk_score} level={data.risk_level} />
          </div>
        </div>
      </Card>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <div className="space-y-6">
          <div>
            <SectionHeading
              title="Analisis sinyal"
              subtitle="Empat dimensi independen dengan skor 0–100"
            />
            <div className="grid gap-4 md:grid-cols-2">
              {data.signals.map((signal) => {
                const meta = CATEGORY_META[signal.category];
                const Icon = meta?.icon ?? ShieldAlert;
                return (
                  <Card key={signal.id} className="flex flex-col">
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex items-center gap-2.5">
                        <span className="flex h-8 w-8 items-center justify-center rounded-lg border border-white/5 bg-white/[0.03]">
                          <Icon className="h-4 w-4" style={{ color: meta?.hex }} />
                        </span>
                        <div>
                          <p className="text-sm font-semibold text-white">{signal.title}</p>
                          <p className="text-[11px] text-slate-500">{meta?.label ?? signal.category}</p>
                        </div>
                      </div>
                      <LevelBadge level={signal.level} />
                    </div>

                    <div className="mt-4 flex items-end justify-between">
                      <div className="flex items-baseline gap-1">
                        <span className="text-2xl font-semibold tabular-nums text-white">
                          {signal.score}
                        </span>
                        <span className="text-xs text-slate-500">/100</span>
                      </div>
                      <span className="text-[11px] text-slate-500">
                        keyakinan {formatPercent(signal.confidence)}
                      </span>
                    </div>
                    <ScoreBar score={signal.score} level={signal.level} className="mt-2" />

                    <p className="mt-3 text-xs leading-relaxed text-slate-400">{signal.explanation}</p>

                    {signal.details.length ? (
                      <ul className="mt-3 space-y-1.5 border-t border-white/5 pt-3">
                        {signal.details.slice(0, 5).map((detail) => (
                          <li key={detail} className="flex gap-2 text-[11px] leading-relaxed text-slate-500">
                            <span
                              className="mt-1 h-1 w-1 shrink-0 rounded-full"
                              style={{ background: meta?.hex ?? "#64748b" }}
                            />
                            {detail}
                          </li>
                        ))}
                      </ul>
                    ) : null}
                  </Card>
                );
              })}
            </div>
          </div>

          <Card>
            <SectionHeading
              title="Klaim yang diekstrak"
              subtitle="Kandidat klaim untuk diverifikasi analis manusia"
            />
            {data.claims.length ? (
              <ol className="space-y-3">
                {data.claims.map((claim, index) => {
                  const meta = CLAIM_VERDICT_META[claim.verdict] ?? CLAIM_VERDICT_META.belum_diverifikasi;
                  return (
                    <li
                      key={claim.id}
                      className="rounded-xl border border-white/5 bg-white/[0.015] p-4"
                    >
                      <div className="flex items-start gap-3">
                        <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-md border border-white/10 bg-white/5 text-[11px] font-semibold text-slate-400">
                          {String(index + 1).padStart(2, "0")}
                        </span>
                        <div>
                          <p className="text-sm leading-relaxed text-slate-200">{claim.text}</p>
                          <div className="mt-2.5 flex flex-wrap items-center gap-2">
                            <span className={cn("chip", meta.badge)}>{meta.label}</span>
                          </div>
                          <p className="mt-2 text-xs leading-relaxed text-slate-500">
                            {claim.rationale}
                          </p>
                        </div>
                      </div>
                    </li>
                  );
                })}
              </ol>
            ) : (
              <p className="text-sm text-slate-500">
                Tidak ada kalimat yang memenuhi pola klaim untuk diekstrak.
              </p>
            )}
          </Card>
        </div>

        <div className="space-y-6">
          <FactCheckCard factcheck={data.factcheck} />

          <Card>
            <SectionHeading
              title="Konten terkait"
              subtitle="Indikasi amplifikasi narasi dalam jendela waktu"
            />
            {data.related.length ? (
              <ul className="space-y-3">
                {data.related.map((related) => (
                  <li key={related.id}>
                    <Link
                      to={`/analisis/${related.id}`}
                      className="group block rounded-xl border border-white/5 bg-white/[0.015] p-3.5 transition hover:border-fuchsia-400/25 hover:bg-fuchsia-400/[0.04]"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-[11px] font-semibold text-fuchsia-300">
                          {formatPercent(related.similarity)} mirip
                        </span>
                        <VerdictBadge verdict={related.verdict} short />
                      </div>
                      <p className="mt-2 line-clamp-2 text-xs font-medium text-slate-200 group-hover:text-white">
                        {related.title}
                      </p>
                      <p className="mt-1.5 text-[11px] text-slate-500">
                        {related.hours_apart !== null
                          ? `selisih ${hoursLabel(related.hours_apart)}`
                          : "waktu tidak diketahui"}
                      </p>
                      {related.shared_phrases.length ? (
                        <div className="mt-2 flex flex-wrap gap-1.5">
                          {related.shared_phrases.slice(0, 3).map((phrase) => (
                            <span
                              key={phrase}
                              className="rounded-md border border-white/5 bg-white/[0.03] px-1.5 py-0.5 text-[10px] text-slate-500"
                            >
                              “{phrase}”
                            </span>
                          ))}
                        </div>
                      ) : null}
                    </Link>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-xs leading-relaxed text-slate-500">
                Tidak ada konten dengan kemiripan narasi di atas ambang pada jendela waktu ini.
              </p>
            )}
          </Card>

          <Card>
            <SectionHeading title="Sumber & bukti" subtitle="Jejak sumber yang dapat diaudit" />
            {data.evidence.length ? (
              <ul className="space-y-2.5">
                {data.evidence.map((item) => (
                  <EvidenceRow key={item.id} item={item} />
                ))}
              </ul>
            ) : (
              <EmptyState
                title="Belum ada bukti terlampir"
                description="Sumber utama tidak dapat diekstrak dari input ini."
              />
            )}
          </Card>

          <div className="rounded-2xl border border-amber-400/15 bg-amber-400/[0.04] p-4">
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-amber-300" />
              <p className="text-xs font-semibold text-amber-200">Batasan analisis</p>
            </div>
            <ul className="mt-3 space-y-2">
              {data.limitations.map((limitation) => (
                <li
                  key={limitation}
                  className="flex gap-2 text-[11px] leading-relaxed text-amber-100/60"
                >
                  <span className="mt-1 h-1 w-1 shrink-0 rounded-full bg-amber-300/60" />
                  {limitation}
                </li>
              ))}
            </ul>
            <p className="mt-3 border-t border-amber-400/10 pt-3 text-[11px] text-amber-100/50">
              Skor ini bukan bukti hukum. Gunakan sebagai prioritas tinjauan.
            </p>
          </div>
        </div>
      </div>

      <div className="flex items-center justify-between gap-3 rounded-xl border border-white/5 bg-white/[0.02] px-4 py-3">
        <p className="text-xs text-slate-500">
          Ingin membandingkan dengan laporan lain?
        </p>
        <Link
          to="/analisis"
          className="inline-flex items-center gap-1.5 text-xs font-medium text-cyan-300 hover:text-cyan-200"
        >
          Buka riwayat <ArrowUpRight className="h-3.5 w-3.5" />
        </Link>
      </div>
    </div>
  );
}
