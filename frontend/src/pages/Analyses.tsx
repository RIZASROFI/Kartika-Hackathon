import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Plus, SlidersHorizontal } from "lucide-react";
import { Link } from "react-router-dom";

import AnalysisTable from "../components/AnalysisTable";
import { Card, EmptyState, ErrorPanel, Spinner } from "../components/ui";
import { api } from "../lib/api";
import { VERDICT_FILTERS } from "../lib/labels";
import type { Verdict } from "../lib/types";
import { cn } from "../lib/utils";

export default function Analyses() {
  const [verdict, setVerdict] = useState<Verdict | null>(null);

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["analyses", verdict],
    queryFn: () => api.listAnalyses({ verdict, limit: 100 }),
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <p className="label">Case archive</p>
          <h1 className="mt-1.5 text-2xl font-semibold tracking-tight text-white">
            Riwayat Analisis
          </h1>
          <p className="mt-1.5 max-w-2xl text-sm text-slate-400">
            Seluruh konten yang pernah diperiksa. Gunakan filter status untuk memprioritaskan
            tinjauan analis.
          </p>
        </div>
        <Link to="/analisis/baru" className="btn-primary shrink-0">
          <Plus className="h-4 w-4" />
          Analisis Baru
        </Link>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <span className="mr-1 inline-flex items-center gap-1.5 text-xs text-slate-500">
          <SlidersHorizontal className="h-3.5 w-3.5" />
          Status
        </span>
        {VERDICT_FILTERS.map((filter) => (
          <button
            key={filter.label}
            type="button"
            onClick={() => setVerdict(filter.value)}
            className={cn(
              "rounded-full border px-3 py-1.5 text-xs transition",
              verdict === filter.value
                ? "border-cyan-400/30 bg-cyan-400/10 font-medium text-cyan-200"
                : "border-white/5 text-slate-400 hover:border-white/10 hover:text-slate-200",
            )}
          >
            {filter.label}
          </button>
        ))}
      </div>

      <Card className="overflow-hidden">
        {isLoading ? (
          <Spinner label="Memuat riwayat analisis" />
        ) : isError ? (
          <ErrorPanel
            message={error instanceof Error ? error.message : "Riwayat tidak tersedia."}
            onRetry={() => void refetch()}
          />
        ) : data && data.length ? (
          <>
            <div className="mb-4 flex items-center justify-between">
              <p className="text-xs text-slate-500">
                Menampilkan <span className="font-medium text-slate-300">{data.length}</span> analisis
              </p>
              <p className="text-xs text-slate-600">Diurutkan dari yang terbaru</p>
            </div>
            <AnalysisTable items={data} />
          </>
        ) : (
          <EmptyState
            title="Tidak ada analisis pada filter ini"
            description={
              verdict
                ? "Coba pilih status lain atau jalankan analisis baru dengan konten terkait."
                : "Belum ada konten yang dianalisis. Mulai dengan menempelkan URL atau teks."
            }
            action={
              <Link to="/analisis/baru" className="btn-primary">
                <Plus className="h-4 w-4" /> Analisis konten
              </Link>
            }
          />
        )}
      </Card>
    </div>
  );
}
