import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowLeft,
  ArrowUpRight,
  Clock,
  ExternalLink,
  FileText,
  Link2,
  Scale,
  ShieldAlert,
  ShieldCheck,
} from "lucide-react";
import { Link, useParams } from "react-router-dom";

import {
  Card,
  ConfidencePill,
  EmptyState,
  ErrorPanel,
  ScoreBar,
  ScoreRing,
  SectionHeading,
  Spinner,
  VerdictBadge,
} from "../components/ui";
import { api } from "../lib/api";
import {
  CATEGORY_META,
  CLAIM_EVIDENCE_META,
  CLAIM_VERDICT_META,
  DECISION_STANCE_META,
  verdictMeta,
} from "../lib/labels";
import type {
  Evidence,
  EvidenceDecision,
  FactCheckSummary,
  FactCheckVerdict,
} from "../lib/types";
import { cn, formatDate, formatPercent } from "../lib/utils";

const EVIDENCE_KIND_LABEL: Record<string, string> = {
  sumber_utama: "Sumber utama",
  input_pengguna: "Input pengguna",
  tautan: "Tautan referensi",
  factcheck: "Pemeriksaan fakta",
  pencarian_web: "Pencarian web terbuka",
  konteks: "Konteks",
};

// Dipakai untuk rekaman lama yang belum menyimpan `scales` dari EBDE; nilainya
// sama dengan tier tertinggi di mesin (kredibilitas lembaga cek fakta = 0.95).
const SCORE_SCALE_FALLBACK = { relevance: 1, credibility: 0.95, recency: 1, weight: 0.95 };

const FACTCHECK_PROVIDER_LABEL: Record<string, string> = {
  google: "Google Fact Check Tools",
  mafindo: "MAFINDO Yudistira",
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

function DecisionCard({ decision }: { decision: Partial<EvidenceDecision> | undefined }) {
  if (!decision?.verdict) {
    return null;
  }

  const items = decision.items ?? [];
  const scale = { ...SCORE_SCALE_FALLBACK, ...(decision.scales ?? {}) };
  const sides = [
    {
      key: "support",
      label: "Mendukung",
      weight: decision.support_weight ?? 0,
      groups: decision.support_groups ?? 0,
      bar: "bg-emerald-400",
    },
    {
      key: "refute",
      label: "Membantah",
      weight: decision.refute_weight ?? 0,
      groups: decision.refute_groups ?? 0,
      bar: "bg-rose-400",
    },
    {
      key: "partial",
      label: "Sebagian benar",
      weight: decision.partial_weight ?? 0,
      groups: decision.partial_groups ?? 0,
      bar: "bg-amber-400",
    },
  ];
  const total = sides.reduce((sum, side) => sum + side.weight, 0);

  return (
    <Card>
      <SectionHeading
        title="Keputusan berbasis bukti"
        subtitle={
          decision.engine
            ? `Evidence-Based Decision Engine ${decision.engine} · bobot = relevansi × kredibilitas × kebaruan, dihitung per domain independen`
            : "Evidence-Based Decision Engine"
        }
      />
      <div className="flex flex-wrap items-center gap-2">
        <VerdictBadge verdict={decision.verdict} />
        <span className="chip border-white/10 bg-white/5 text-slate-400">
          keyakinan bukti {Math.round((decision.confidence ?? 0) * 100)}%
        </span>
        <span className="chip border-white/10 bg-white/5 text-slate-400">
          {decision.independent_groups ?? 0} domain independen
        </span>
        {decision.conflict ? (
          <span className="chip border-orange-400/30 bg-orange-400/10 text-orange-300">
            Bukti bertentangan
          </span>
        ) : null}
        {decision.sufficient === false ? (
          <span className="chip border-amber-400/30 bg-amber-400/10 text-amber-300">
            Bukti belum cukup
          </span>
        ) : null}
      </div>

      <p className="mt-3 text-xs leading-relaxed text-slate-400">{decision.rationale}</p>

      <div className="mt-4 space-y-2.5">
        {sides.map((side) => (
          <div key={side.key}>
            <div className="flex items-center justify-between text-[11px]">
              <span className="text-slate-400">
                {side.label}
                <span className="ml-1 text-slate-600">· {side.groups} domain</span>
              </span>
              <span
                className="font-mono text-[10px] text-slate-500"
                title={
                  side.groups > 0
                    ? `Maksimum ${scale.weight.toFixed(2)} per domain independen × ${side.groups} domain`
                    : undefined
                }
              >
                bobot {side.weight.toFixed(2)}
                {side.groups > 0
                  ? ` / maks ${(scale.weight * side.groups).toFixed(2)}`
                  : ""}
              </span>
            </div>
            <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-white/5">
              <div
                className={cn("h-full rounded-full", side.bar)}
                style={{ width: total ? `${Math.max(2, (side.weight / total) * 100)}%` : "0%" }}
              />
            </div>
          </div>
        ))}
      </div>

      {!decision.sufficient && decision.insufficient_reason ? (
        <p className="mt-3 flex items-start gap-1.5 rounded-lg border border-amber-400/15 bg-amber-400/[0.04] p-2.5 text-[11px] leading-relaxed text-amber-100/70">
          <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0 text-amber-300" />
          {decision.insufficient_reason}
        </p>
      ) : null}

      {items.length ? (
        <details className="mt-4 border-t border-white/5 pt-3">
          <summary className="cursor-pointer text-[11px] font-medium text-slate-400">
            Jejak penilaian {items.length} bukti
          </summary>
          <ul className="mt-2.5 space-y-2">
            {items.map((item) => {
              const stance = DECISION_STANCE_META[item.stance] ?? DECISION_STANCE_META.netral;
              return (
                <li
                  key={`${item.url}-${item.title}`}
                  className="rounded-lg border border-white/5 bg-white/[0.015] p-2.5"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <span className={cn("chip", stance.badge)}>{stance.label}</span>
                    <span className="font-mono text-[10px] text-slate-500">
                      bobot {item.weight.toFixed(2)}/{scale.weight.toFixed(2)}
                    </span>
                    <span
                      className="font-mono text-[10px] text-slate-600"
                      title="Tiap dimensi berskala 0–1. Kredibilitas maksimum 0.95, yaitu tier lembaga cek fakta; bobot maksimum = 1.00 × 0.95 × 1.00."
                    >
                      rel {item.relevance.toFixed(2)}/{scale.relevance.toFixed(2)} · kred{" "}
                      {item.credibility.toFixed(2)}/{scale.credibility.toFixed(2)} · baru{" "}
                      {item.recency.toFixed(2)}/{scale.recency.toFixed(2)}
                    </span>
                  </div>
                  <p className="mt-1.5 truncate text-[11px] text-slate-300">
                    {item.url ? (
                      <a
                        href={item.url}
                        target="_blank"
                        rel="noreferrer noopener"
                        className="hover:text-cyan-300 hover:underline"
                      >
                        {item.title}
                      </a>
                    ) : (
                      item.title
                    )}
                  </p>
                  <p className="text-[10px] text-slate-600">
                    {item.publisher || item.group} ·{" "}
                    {item.kind === "factcheck" ? "pemeriksaan fakta" : "pencarian web"}
                  </p>
                  {item.note ? (
                    <p className="mt-1 flex items-start gap-1.5 text-[10px] leading-relaxed text-amber-200/70">
                      <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0 text-amber-300/80" />
                      {item.note}
                    </p>
                  ) : null}
                </li>
              );
            })}
          </ul>
        </details>
      ) : null}

      <p className="mt-3 flex items-start gap-1.5 border-t border-white/5 pt-3 text-[11px] leading-relaxed text-slate-500">
        <Scale className="mt-0.5 h-3 w-3 shrink-0 text-cyan-400/70" />
        Indeks pola narasi ({decision.narrative_risk ?? 0}/100) hanya konteks: tidak dipakai
        sebagai bukti dan tidak dapat menggeser status ini.
      </p>
    </Card>
  );
}

function FactCheckCard({
  factcheck,
  notes,
}: {
  factcheck: Partial<FactCheckSummary> | undefined;
  notes: Map<string, string>;
}) {
  const status = factcheck?.status;
  if (!status || status === "disabled") {
    return null;
  }

  const hits = factcheck?.hits ?? [];
  const providers = factcheck?.providers?.length
    ? factcheck.providers
    : factcheck?.provider
      ? factcheck.provider.split("+")
      : [];
  const providerLabel = providers
    .map((provider) => FACTCHECK_PROVIDER_LABEL[provider] ?? provider)
    .join(" · ");

  return (
    <Card>
      <SectionHeading
        title="Verifikasi fakta eksternal"
        subtitle={
          providerLabel
            ? `${providerLabel} · klaim yang sudah diperiksa pihak lain`
            : "Klaim yang sudah diperiksa pihak lain"
        }
      />
      {status === "matched" ? (
        <ul className="space-y-2.5">
          {hits.map((hit) => {
            const meta = FACTCHECK_META[hit.status] ?? FACTCHECK_META.tidak_jelas;
            const note = notes.get(hit.url);
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
                  {hit.publisher}
                  {hit.provider ? ` · ${FACTCHECK_PROVIDER_LABEL[hit.provider] ?? hit.provider}` : ""}
                  {" · "}
                  {formatDate(hit.review_date, false)}
                </p>
                {note ? (
                  <p className="mt-2 flex items-start gap-1.5 text-[11px] leading-relaxed text-amber-200/70">
                    <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0 text-amber-300/80" />
                    {note}
                  </p>
                ) : null}
                {hit.url ? (
                  <a
                    href={hit.url}
                    target="_blank"
                    rel="noreferrer noopener"
                    className="mt-2 inline-flex items-center gap-1 text-[11px] font-medium text-cyan-400/80 hover:text-cyan-300"
                  >
                    {hit.reference_only ? "Buka rujukan" : "Buka pemeriksaan"}{" "}
                    <ExternalLink className="h-3 w-3" />
                  </a>
                ) : null}
                {hit.reference_only ? (
                  <p className="mt-1 text-[10px] leading-relaxed text-slate-600">
                    Tautan ini rujukan yang dikutip pemeriksaan, bukan halaman artikel pemeriksa
                    fakta.
                  </p>
                ) : null}
              </li>
            );
          })}
        </ul>
      ) : status === "no_match" ? (
        <div className="space-y-2">
          <p className="text-xs leading-relaxed text-slate-500">
            {providerLabel || "Sumber pemeriksa fakta"} sudah dicari, tetapi belum ada
            pemeriksaan fakta publik yang cocok dengan klaim pada konten ini. Ketiadaan
            catatan bukan bukti kebenaran.
          </p>
          {factcheck?.keywords?.length ? (
            <p className="text-[11px] leading-relaxed text-slate-600">
              Kata kunci yang dicari: {factcheck.keywords.join(", ")}
            </p>
          ) : null}
        </div>
      ) : (
        <p className="text-xs leading-relaxed text-amber-200/70">
          {factcheck?.message ??
            "Layanan pemeriksaan fakta eksternal tidak dapat dihubungi saat analisis dibuat."}
        </p>
      )}
      <p className="mt-3 flex items-start gap-1.5 border-t border-white/5 pt-3 text-[11px] leading-relaxed text-slate-500">
        <ShieldCheck className="mt-0.5 h-3 w-3 shrink-0 text-cyan-400/70" />
        Hasil pemeriksaan pihak ketiga menjadi bahan pertimbangan EBDE, bukan pengganti penilaian
        analis: temuan untuk klaim lain ditandai sebagai konteks dan tidak menimbang verdict.
      </p>
    </Card>
  );
}

function EvidenceRow({ item }: { item: Evidence }) {
  return (
    <li className="rounded-xl border border-white/5 bg-white/[0.015] p-3.5">
      <div className="min-w-0">
        <p className="text-xs font-medium text-slate-200">
          {item.url ? (
            <a
              href={item.url}
              target="_blank"
              rel="noreferrer noopener"
              className="inline-flex items-start gap-1.5 hover:text-cyan-300 hover:underline"
            >
              {item.title}
              <ExternalLink className="mt-0.5 h-3 w-3 shrink-0" />
            </a>
          ) : (
            item.title
          )}
        </p>
        <p className="mt-1 text-[11px] text-slate-500">
          {EVIDENCE_KIND_LABEL[item.kind] ?? item.kind}
          {item.publisher ? ` · ${item.publisher}` : ""} · diambil {formatDate(item.retrieved_at, false)}
        </p>
        {item.url ? (
          <a
            href={item.url}
            target="_blank"
            rel="noreferrer noopener"
            title={item.url}
            className="mt-2 flex items-center gap-1.5 rounded-lg border border-white/5 bg-white/[0.02] px-2 py-1.5 text-[11px] text-cyan-300/90 transition hover:border-cyan-400/30 hover:bg-cyan-400/[0.06] hover:text-cyan-200"
          >
            <Link2 className="h-3 w-3 shrink-0" />
            <span className="truncate">{item.url}</span>
          </a>
        ) : (
          <p className="mt-2 flex items-center gap-1.5 rounded-lg border border-dashed border-white/5 px-2 py-1.5 text-[11px] text-slate-600">
            <Link2 className="h-3 w-3 shrink-0" />
            Tanpa tautan sumber
          </p>
        )}
        {item.snippet ? (
          <p className="mt-2 line-clamp-3 text-xs leading-relaxed text-slate-500">{item.snippet}</p>
        ) : null}
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
                {data.source_type === "social" || data.source_type === "url" ? (
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
              <span>
                {(data.processing_ms / 1000).toLocaleString("id-ID", {
                  maximumFractionDigits: 1,
                })}{" "}detik
              </span>
            </div>
            <p className="mt-4 max-w-3xl text-sm leading-relaxed text-slate-300">{data.summary}</p>
            <div className="mt-4 flex flex-wrap items-center gap-3">
              <ConfidencePill value={data.confidence} />
            </div>
          </div>
          <div className="flex flex-col items-center gap-2 lg:items-end">
            <ScoreRing score={data.risk_score} />
            <p className="max-w-[150px] text-center text-[10px] leading-relaxed text-slate-500 lg:text-right">
              Indeks pola narasi 0–100 · bukan verdict fakta
            </p>
          </div>
        </div>
      </Card>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <div className="space-y-6">
          <DecisionCard decision={data.decision} />
          <div>
            <SectionHeading
              title="Analisis sinyal"
              subtitle="Indikator pembentuk indeks pola narasi (0–100)"
            />
            <div className="grid gap-4">
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
                    <ScoreBar score={signal.score} className="mt-2" />

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
              subtitle={
                data.claim_check?.status === "verified"
                  ? `Status klaim dinilai ${data.claim_check.model ?? "model bahasa"} dari ${data.claim_check.evidence_count ?? 0} sumber web · sitasi wajib diperiksa`
                  : "Kandidat klaim untuk diverifikasi analis manusia"
              }
            />
            {data.claims.length ? (
              <ol className="space-y-3">
                {data.claims.map((claim, index) => {
                  const meta = CLAIM_VERDICT_META[claim.verdict] ?? CLAIM_VERDICT_META.belum_diverifikasi;
                  const evidenceMeta = claim.evidence_status
                    ? CLAIM_EVIDENCE_META[claim.evidence_status]
                    : null;
                  const citations = claim.citations ?? [];
                  return (
                    <li
                      key={claim.id}
                      className="rounded-xl border border-white/5 bg-white/[0.015] p-4"
                    >
                      <div className="flex items-start gap-3">
                        <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-md border border-white/10 bg-white/5 text-[11px] font-semibold text-slate-400">
                          {String(index + 1).padStart(2, "0")}
                        </span>
                        <div className="min-w-0 flex-1">
                          <p className="text-sm leading-relaxed text-slate-200">{claim.text}</p>
                          <div className="mt-2.5 flex flex-wrap items-center gap-2">
                            <span className={cn("chip", meta.badge)}>{meta.label}</span>
                            {evidenceMeta ? (
                              <span className={cn("chip", evidenceMeta.badge)}>
                                {evidenceMeta.label}
                              </span>
                            ) : null}
                          </div>
                          <p className="mt-2 text-xs leading-relaxed text-slate-500">
                            {claim.verification_note || claim.rationale}
                          </p>
                          {citations.length ? (
                            <ul className="mt-2 space-y-1">
                              {citations.map((citation) => (
                                <li key={citation.url} className="text-[11px] leading-relaxed">
                                  <a
                                    href={citation.url}
                                    target="_blank"
                                    rel="noreferrer noopener"
                                    className="inline-flex items-center gap-1 font-medium text-cyan-400/80 hover:text-cyan-300"
                                  >
                                    <ExternalLink className="h-3 w-3 shrink-0" />
                                    {citation.publisher || citation.title}
                                  </a>
                                  <span className="text-slate-600"> · {citation.title}</span>
                                </li>
                              ))}
                            </ul>
                          ) : null}
                        </div>
                      </div>
                    </li>
                  );
                })}
              </ol>
            ) : data.claim_check?.claims?.length ? (
              <div className="space-y-3">
                <p className="text-[11px] leading-relaxed text-slate-500">
                  Tidak ada kalimat berpola klaim; {data.claim_check.model ?? "model bahasa"} menilai
                  kalimat pertama sebagai klaim pengganti agar sumbernya tetap dapat diaudit.
                </p>
                <ol className="space-y-3">
                  {data.claim_check.claims.map((claim, index) => {
                    const evidenceMeta = CLAIM_EVIDENCE_META[claim.status];
                    const citations = claim.citations ?? [];
                    return (
                      <li
                        key={`${claim.claim}-${index}`}
                        className="rounded-xl border border-white/5 bg-white/[0.015] p-4"
                      >
                        <p className="text-sm leading-relaxed text-slate-200">{claim.claim}</p>
                        <div className="mt-2.5 flex flex-wrap items-center gap-2">
                          {evidenceMeta ? (
                            <span className={cn("chip", evidenceMeta.badge)}>
                              {evidenceMeta.label}
                            </span>
                          ) : null}
                          <span className="chip border-white/10 bg-white/5 text-slate-400">
                            klaim pengganti
                          </span>
                        </div>
                        <p className="mt-2 text-xs leading-relaxed text-slate-500">
                          {claim.rationale}
                        </p>
                        {citations.length ? (
                          <ul className="mt-2 space-y-1">
                            {citations.map((citation) => (
                              <li key={citation.url} className="text-[11px] leading-relaxed">
                                <a
                                  href={citation.url}
                                  target="_blank"
                                  rel="noreferrer noopener"
                                  className="inline-flex items-center gap-1 font-medium text-cyan-400/80 hover:text-cyan-300"
                                >
                                  <ExternalLink className="h-3 w-3 shrink-0" />
                                  {citation.publisher || citation.title}
                                </a>
                                <span className="text-slate-600"> · {citation.title}</span>
                              </li>
                            ))}
                          </ul>
                        ) : null}
                      </li>
                    );
                  })}
                </ol>
              </div>
            ) : (
              <p className="text-sm text-slate-500">
                Tidak ada kalimat yang memenuhi pola klaim untuk diekstrak.
                {data.claim_check?.status === "verified"
                  ? " Pencarian sumber tetap dijalankan memakai judul atau kalimat pertama; hasilnya ada di panel Sumber & bukti."
                  : ""}
              </p>
            )}
            {data.claim_check?.message ? (
              <p className="mt-3 border-t border-white/5 pt-3 text-[11px] leading-relaxed text-slate-500">
                {data.claim_check.message}
              </p>
            ) : null}
          </Card>
        </div>

        <div className="space-y-6">
          <FactCheckCard
            factcheck={data.factcheck}
            notes={
              new Map(
                (data.decision.items ?? [])
                  .filter((item) => item.note)
                  .map((item) => [item.url, item.note as string]),
              )
            }
          />

          <Card>
            <SectionHeading
              title="Sumber & bukti"
              subtitle={
                data.evidence.length
                  ? `Jejak sumber yang dapat diaudit · ${data.evidence.filter((item) => item.url).length} tautan terbuka`
                  : "Jejak sumber yang dapat diaudit"
              }
            />
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
