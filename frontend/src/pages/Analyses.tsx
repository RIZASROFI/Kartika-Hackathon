import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, SlidersHorizontal, Trash2 } from "lucide-react";
import { Link } from "react-router-dom";

import AnalysisTable from "../components/AnalysisTable";
import { Card, ConfirmDialog, EmptyState, ErrorPanel, Spinner } from "../components/ui";
import { api } from "../lib/api";
import { VERDICT_FILTERS } from "../lib/labels";
import type { AnalysisListItem, Verdict } from "../lib/types";
import { cn } from "../lib/utils";

export default function Analyses() {
  const queryClient = useQueryClient();
  const [verdict, setVerdict] = useState<Verdict | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [pending, setPending] = useState<AnalysisListItem[] | null>(null);

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["analyses", verdict],
    queryFn: () => api.listAnalyses({ verdict, limit: 100 }),
  });

  const deletion = useMutation({
    mutationFn: (items: AnalysisListItem[]) =>
      items.length === 1
        ? api.deleteAnalysis(items[0].id).then(() => ({ deleted: 1 }))
        : api.deleteAnalyses(items.map((item) => item.id)),
    onSuccess: () => {
      setPending(null);
      setSelected(new Set());
      void queryClient.invalidateQueries({ queryKey: ["analyses"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });

  const toggleOne = (id: string) => {
    setSelected((previous) => {
      const next = new Set(previous);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const toggleAll = (checked: boolean) => {
    setSelected(checked && data ? new Set(data.map((item) => item.id)) : new Set());
  };

  const requestBulkDelete = () => {
    if (!data) {
      return;
    }
    const items = data.filter((item) => selected.has(item.id));
    if (items.length) {
      setPending(items);
    }
  };

  const pendingCount = pending?.length ?? 0;
  const deletingId =
    deletion.isPending && pendingCount === 1 ? pending![0].id : null;

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
            onClick={() => {
              setVerdict(filter.value);
              setSelected(new Set());
            }}
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

      {selected.size > 0 ? (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-rose-400/20 bg-rose-400/5 px-4 py-3">
          <p className="text-xs font-medium text-rose-200">
            {selected.size} analisis dipilih
          </p>
          <div className="flex items-center gap-2">
            <button
              type="button"
              className="btn-ghost px-3 py-1.5 text-xs"
              onClick={() => setSelected(new Set())}
              disabled={deletion.isPending}
            >
              Batalkan pilihan
            </button>
            <button
              type="button"
              onClick={requestBulkDelete}
              disabled={deletion.isPending}
              className="inline-flex items-center gap-2 rounded-xl bg-rose-500 px-3.5 py-1.5 text-xs font-semibold text-white transition hover:bg-rose-400 disabled:cursor-not-allowed disabled:opacity-60"
            >
              <Trash2 className="h-3.5 w-3.5" />
              Hapus terpilih
            </button>
          </div>
        </div>
      ) : null}

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
                {selected.size ? ` · ${selected.size} dipilih` : ""}
              </p>
              <p className="text-xs text-slate-600">Diurutkan dari yang terbaru</p>
            </div>
            <AnalysisTable
              items={data}
              selectedIds={selected}
              onToggle={toggleOne}
              onToggleAll={toggleAll}
              onDelete={(item) => setPending([item])}
              deletingId={deletingId}
            />
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

      <ConfirmDialog
        open={pending !== null}
        title={pendingCount === 1 ? "Hapus analisis ini?" : `Hapus ${pendingCount} analisis?`}
        description="Riwayat analisis beserta sinyal, klaim, bukti, dan tautan koordinasi terkait akan dihapus permanen. Tindakan ini tidak dapat dibatalkan."
        confirmLabel={pendingCount > 1 ? `Hapus ${pendingCount}` : "Hapus"}
        busy={deletion.isPending}
        error={
          deletion.isError
            ? deletion.error instanceof Error
              ? deletion.error.message
              : "Gagal menghapus analisis."
            : null
        }
        onConfirm={() => {
          if (pending) {
            deletion.mutate(pending);
          }
        }}
        onCancel={() => {
          if (!deletion.isPending) {
            setPending(null);
            deletion.reset();
          }
        }}
      />
    </div>
  );
}
