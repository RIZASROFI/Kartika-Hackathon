import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  FileSearch,
  Gauge,
  Plus,
  ShieldAlert,
  TriangleAlert,
} from "lucide-react";
import { Link } from "react-router-dom";
import {
  Bar,
  BarChart,
  Cell,
  LabelList,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import AnalysisTable from "../components/AnalysisTable";
import {
  Card,
  EmptyState,
  ErrorPanel,
  SectionHeading,
  Spinner,
} from "../components/ui";
import { api } from "../lib/api";
import { VERDICT_META, verdictMeta } from "../lib/labels";
import { formatPercent } from "../lib/utils";

const TOOLTIP_STYLE = {
  background: "#191C24",
  border: "1px solid rgba(255,255,255,0.08)",
  borderRadius: 12,
  fontSize: 12,
  color: "#e2e8f0",
} as const;

function StatCard({
  icon: Icon,
  label,
  value,
  hint,
  accent,
}: {
  icon: typeof Gauge;
  label: string;
  value: string | number;
  hint: string;
  accent: string;
}) {
  return (
    <div className="card card-hover p-5">
      <div className="flex items-start justify-between">
        <div>
          <p className="label">{label}</p>
          <p className="mt-3 text-2xl font-semibold tabular-nums text-white">{value}</p>
        </div>
        <span className={`flex h-9 w-9 items-center justify-center rounded-xl border ${accent}`}>
          <Icon className="h-4 w-4" />
        </span>
      </div>
      <p className="mt-3 text-xs text-slate-500">{hint}</p>
    </div>
  );
}

export default function Dashboard() {
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["dashboard"],
    queryFn: api.getDashboard,
    refetchInterval: 30_000,
  });

  if (isLoading) {
    return <Spinner label="Menyusun ringkasan intelijen" />;
  }

  if (isError || !data) {
    return (
      <ErrorPanel
        message={error instanceof Error ? error.message : "Ringkasan tidak tersedia."}
        onRetry={() => void refetch()}
      />
    );
  }

  const { totals } = data;
  const highRiskShare = totals.analyses ? totals.high_risk / totals.analyses : 0;
  const verdictData = data.verdict_distribution.map((slice) => ({
    name: verdictMeta(slice.verdict).short,
    value: slice.count,
    fill: VERDICT_META[slice.verdict]?.hex ?? "#38bdf8",
  }));

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <p className="label">Threat overview</p>
          <h1 className="mt-1.5 text-2xl font-semibold tracking-tight text-white">
            Dashboard Intelijen
          </h1>
          <p className="mt-1.5 max-w-2xl text-sm text-slate-400">
            Pantau indikasi hoaks dan hasil verifikasi fakta dari konten yang dianalisis.
          </p>
        </div>
        <Link to="/analisis/baru" className="btn-primary shrink-0">
          <Plus className="h-4 w-4" />
          Analisis Baru
        </Link>
      </div>

      <div className="rounded-xl border border-cyan-400/15 bg-cyan-400/[0.04] px-4 py-3 text-xs leading-relaxed text-cyan-100/70">
        <span className="font-semibold text-cyan-200">Catatan.</span> Semua skor bersifat indikatif
        dan memerlukan verifikasi analis sebelum dijadikan dasar tindakan.
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          icon={FileSearch}
          label="Total analisis"
          value={totals.analyses}
          hint={`${totals.contents} konten unik · ${totals.claims} klaim teridentifikasi`}
          accent="border-cyan-400/20 bg-cyan-400/10 text-cyan-300"
        />
        <StatCard
          icon={ShieldAlert}
          label="Risiko tinggi"
          value={totals.high_risk}
          hint={`${formatPercent(highRiskShare)} dari seluruh analisis berskor ≥ 50`}
          accent="border-rose-400/20 bg-rose-400/10 text-rose-300"
        />
        <StatCard
          icon={Gauge}
          label="Rata-rata risiko"
          value={totals.average_risk.toFixed(1)}
          hint="Risiko narasi 0–100, terpisah dari verdict fakta"
          accent="border-amber-400/20 bg-amber-400/10 text-amber-300"
        />
      </div>

      <div className="grid gap-6">
        <Card>
          <SectionHeading title="Profil sinyal" subtitle="Rata-rata skor sinyal tersimpan" />
          {data.category_scores.length ? (
            <div className="space-y-5">
              {data.category_scores.map((item) => (
                <div key={item.category}>
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-medium text-slate-300">{item.label}</span>
                    <span className="font-mono text-[11px] text-slate-500">
                      rata-rata {item.average_score.toFixed(1)}/100
                    </span>
                  </div>
                  <div className="mt-2 h-2 overflow-hidden rounded-full bg-white/5">
                    <div
                      className="h-full rounded-full bg-cyan-400"
                      style={{ width: `${Math.min(100, Math.max(0, item.average_score))}%` }}
                    />
                  </div>
                  <p className="mt-1.5 text-[11px] text-slate-600">
                    Skor tertinggi {item.max_score}/100
                  </p>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState title="Belum ada sinyal" description="Jalankan analisis pertama Anda." />
          )}
        </Card>
      </div>

      <div className="grid gap-6 xl:grid-cols-3">
        <Card>
          <SectionHeading title="Distribusi status" subtitle="Seluruh analisis tersimpan" />
          {verdictData.length ? (
            <div className="h-[220px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={verdictData}
                  layout="vertical"
                  margin={{ top: 0, right: 28, left: 0, bottom: 0 }}
                >
                  <XAxis type="number" hide />
                  <YAxis
                    type="category"
                    dataKey="name"
                    width={104}
                    tick={{ fill: "#94a3b8", fontSize: 11 }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <Tooltip contentStyle={TOOLTIP_STYLE} cursor={{ fill: "rgba(255,255,255,0.03)" }} />
                  <Bar dataKey="value" name="Analisis" radius={[0, 6, 6, 0]} barSize={16}>
                    {verdictData.map((entry) => (
                      <Cell key={entry.name} fill={entry.fill} />
                    ))}
                    <LabelList
                      dataKey="value"
                      position="right"
                      style={{ fill: "#94a3b8", fontSize: 11 }}
                    />
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <EmptyState title="Belum ada data" description="Jalankan analisis pertama Anda." />
          )}
        </Card>

        <Card className="xl:col-span-2">
          <SectionHeading
            title="Analisis terbaru"
            subtitle="Konten yang paling baru diperiksa mesin deteksi"
            action={
              <Link
                to="/analisis/baru"
                className="inline-flex items-center gap-1.5 text-xs font-medium text-cyan-300 hover:text-cyan-200"
              >
                <Activity className="h-3.5 w-3.5" />
                Periksa konten
              </Link>
            }
          />
          {data.recent_analyses.length ? (
            <AnalysisTable items={data.recent_analyses} />
          ) : (
            <EmptyState
              title="Belum ada analisis"
              description="Mulai dari menempelkan URL artikel atau teks yang ingin diperiksa."
              action={
                <Link to="/analisis/baru" className="btn-primary">
                  <Plus className="h-4 w-4" /> Analisis konten
                </Link>
              }
            />
          )}
        </Card>
      </div>

      <div className="flex items-start gap-3 rounded-xl border border-amber-400/15 bg-amber-400/[0.04] px-4 py-3.5 text-xs leading-relaxed text-amber-100/70">
        <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0 text-amber-300" />
        <p>
          Dashboard menampilkan indikasi berbasis sinyal, bukan putusan fakta. Selalu cocokkan
          temuan dengan sumber resmi dan libatkan analis manusia sebelum mengambil tindakan.
        </p>
      </div>
    </div>
  );
}
