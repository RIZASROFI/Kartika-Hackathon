import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  ArrowRight,
  FileSearch,
  Gauge,
  Network,
  Plus,
  ShieldAlert,
  TriangleAlert,
} from "lucide-react";
import { Link } from "react-router-dom";
import {
  Area,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  LabelList,
  Line,
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
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
  VerdictBadge,
} from "../components/ui";
import { api } from "../lib/api";
import { VERDICT_META, verdictMeta } from "../lib/labels";
import { formatDay, formatPercent, hoursLabel } from "../lib/utils";

const TOOLTIP_STYLE = {
  background: "#0B1220",
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
            Pantau indikasi hoaks, provokasi, aktivitas terkoordinasi, dan sinyal konten otomatis
            dari konten yang dianalisis.
          </p>
        </div>
        <Link to="/analisis/baru" className="btn-primary shrink-0">
          <Plus className="h-4 w-4" />
          Analisis Baru
        </Link>
      </div>

      <div className="rounded-xl border border-cyan-400/15 bg-cyan-400/[0.04] px-4 py-3 text-xs leading-relaxed text-cyan-100/70">
        <span className="font-semibold text-cyan-200">Mode demo.</span> Sebagian data awal adalah
        skenario sintetis untuk memperagakan alur analisis. Semua skor bersifat indikatif dan
        memerlukan verifikasi analis.
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
          hint="Skala 0–100 dari seluruh dimensi sinyal"
          accent="border-amber-400/20 bg-amber-400/10 text-amber-300"
        />
        <StatCard
          icon={Network}
          label="Pasangan koordinasi"
          value={totals.coordination_links}
          hint="Konten dengan kemiripan narasi di atas ambang"
          accent="border-fuchsia-400/20 bg-fuchsia-400/10 text-fuchsia-300"
        />
      </div>

      <div className="grid gap-6 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <SectionHeading
            title="Tren analisis & risiko"
            subtitle="14 hari terakhir berdasarkan waktu analisis"
            action={
              <div className="hidden items-center gap-4 text-[11px] text-slate-500 sm:flex">
                <span className="flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-full bg-cyan-400" /> Analisis
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-full bg-amber-400" /> Rata-rata risiko
                </span>
              </div>
            }
          />
          <div className="h-[268px]">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={data.risk_trend} margin={{ top: 8, right: 4, left: -22, bottom: 0 }}>
                <defs>
                  <linearGradient id="trendFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#22d3ee" stopOpacity={0.28} />
                    <stop offset="100%" stopColor="#22d3ee" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="rgba(148,163,184,0.08)" vertical={false} />
                <XAxis
                  dataKey="date"
                  tickFormatter={formatDay}
                  tick={{ fill: "#64748b", fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                  minTickGap={18}
                />
                <YAxis
                  yAxisId="left"
                  allowDecimals={false}
                  tick={{ fill: "#64748b", fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  yAxisId="right"
                  orientation="right"
                  domain={[0, 100]}
                  tick={{ fill: "#64748b", fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                  width={32}
                />
                <Tooltip
                  contentStyle={TOOLTIP_STYLE}
                  labelStyle={{ color: "#94a3b8" }}
                  labelFormatter={(value) => formatDay(String(value))}
                />
                <Area
                  yAxisId="left"
                  type="monotone"
                  dataKey="analyses"
                  name="Analisis"
                  stroke="#22d3ee"
                  strokeWidth={2}
                  fill="url(#trendFill)"
                />
                <Line
                  yAxisId="right"
                  type="monotone"
                  dataKey="average_risk"
                  name="Rata-rata risiko"
                  stroke="#fbbf24"
                  strokeWidth={2}
                  dot={false}
                />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card>
          <SectionHeading title="Profil sinyal" subtitle="Rata-rata skor per dimensi" />
          <div className="h-[268px]">
            <ResponsiveContainer width="100%" height="100%">
              <RadarChart data={data.category_scores} outerRadius="72%">
                <PolarGrid stroke="rgba(148,163,184,0.12)" />
                <PolarAngleAxis
                  dataKey="label"
                  tick={{ fill: "#94a3b8", fontSize: 11 }}
                />
                <PolarRadiusAxis domain={[0, 100]} tick={false} axisLine={false} />
                <Radar
                  dataKey="average_score"
                  name="Rata-rata"
                  stroke="#22d3ee"
                  fill="#22d3ee"
                  fillOpacity={0.22}
                  strokeWidth={2}
                />
                <Tooltip contentStyle={TOOLTIP_STYLE} />
              </RadarChart>
            </ResponsiveContainer>
          </div>
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
            title="Peringatan koordinasi"
            subtitle="Pasangan konten dengan kemiripan narasi tinggi"
            action={
              <Link to="/analisis" className="text-xs font-medium text-cyan-300 hover:text-cyan-200">
                Lihat riwayat
              </Link>
            }
          />
          {data.coordination_alerts.length ? (
            <ul className="space-y-2.5">
              {data.coordination_alerts.slice(0, 4).map((alert) => (
                <li key={`${alert.analysis_id}-${alert.related_title}`}>
                  <Link
                    to={`/analisis/${alert.analysis_id}`}
                    className="group flex flex-col gap-3 rounded-xl border border-white/5 bg-white/[0.015] p-3.5 transition hover:border-fuchsia-400/25 hover:bg-fuchsia-400/[0.04] sm:flex-row sm:items-center sm:justify-between"
                  >
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-slate-200 group-hover:text-white">
                        {alert.title}
                      </p>
                      <p className="mt-1 truncate text-xs text-slate-500">
                        mirip dengan “{alert.related_title}” · {hoursLabel(alert.hours_apart)}
                      </p>
                    </div>
                    <div className="flex shrink-0 items-center gap-2.5">
                      <span className="rounded-full border border-fuchsia-400/20 bg-fuchsia-400/10 px-2 py-0.5 text-[11px] font-medium text-fuchsia-300">
                        {formatPercent(alert.similarity)} mirip
                      </span>
                      <VerdictBadge verdict={alert.verdict} short />
                      <ArrowRight className="h-4 w-4 text-slate-600 transition group-hover:translate-x-0.5 group-hover:text-fuchsia-300" />
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState
              title="Belum ada klaster terdeteksi"
              description="Analisis beberapa konten dengan narasi serupa untuk melihat indikasi amplifikasi."
            />
          )}
        </Card>
      </div>

      <Card>
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
