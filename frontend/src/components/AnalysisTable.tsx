import { useEffect, useRef } from "react";
import { ArrowUpRight, FileText, Link2, Loader2, Trash2 } from "lucide-react";
import { Link } from "react-router-dom";

import { ScoreBar, VerdictBadge } from "./ui";
import type { AnalysisListItem } from "../lib/types";
import { cn, formatDate } from "../lib/utils";

type AnalysisTableProps = {
  items: AnalysisListItem[];
  selectedIds?: Set<string>;
  onToggle?: (id: string) => void;
  onToggleAll?: (checked: boolean) => void;
  onDelete?: (item: AnalysisListItem) => void;
  deletingId?: string | null;
};

export default function AnalysisTable({
  items,
  selectedIds,
  onToggle,
  onToggleAll,
  onDelete,
  deletingId,
}: AnalysisTableProps) {
  const selectable = Boolean(selectedIds && onToggle && onToggleAll);
  const allSelected =
    selectable && items.length > 0 && items.every((item) => selectedIds!.has(item.id));
  const someSelected = selectable && items.some((item) => selectedIds!.has(item.id));
  const headerCheckbox = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (headerCheckbox.current) {
      headerCheckbox.current.indeterminate = someSelected && !allSelected;
    }
  }, [someSelected, allSelected]);

  return (
    <div className="-mx-5 overflow-x-auto sm:-mx-6">
      <table className="w-full min-w-[720px] border-collapse text-left text-sm">
        <thead>
          <tr className="border-y border-white/5 text-[11px] uppercase tracking-[0.14em] text-slate-500">
            {selectable ? (
              <th className="w-10 py-3 pl-5 pr-1 sm:pl-6">
                <input
                  ref={headerCheckbox}
                  type="checkbox"
                  className="h-4 w-4 cursor-pointer accent-cyan-400"
                  checked={allSelected}
                  onChange={(event) => onToggleAll?.(event.target.checked)}
                  aria-label={allSelected ? "Batalkan pilihan semua" : "Pilih semua analisis"}
                />
              </th>
            ) : null}
            <th className={cn("py-3 font-medium", selectable ? "px-4" : "px-5 sm:px-6")}>
              Konten
            </th>
            <th className="px-4 py-3 font-medium">Status</th>
            <th className="px-4 py-3 font-medium">Indeks narasi</th>
            <th className="px-4 py-3 font-medium">Dianalisis</th>
            <th className="px-5 py-3 sm:px-6" aria-label="Aksi" />
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr
              key={item.id}
              className={cn(
                "group border-b border-white/5 transition last:border-0 hover:bg-white/[0.025]",
                selectedIds?.has(item.id) && "bg-cyan-400/[0.04]",
              )}
            >
              {selectable ? (
                <td className="py-4 pl-5 pr-1 sm:pl-6">
                  <input
                    type="checkbox"
                    className="h-4 w-4 cursor-pointer accent-cyan-400"
                    checked={selectedIds!.has(item.id)}
                    onChange={() => onToggle?.(item.id)}
                    aria-label={`Pilih ${item.title}`}
                  />
                </td>
              ) : null}
              <td className={cn("max-w-[360px] py-4", selectable ? "px-4" : "px-5 sm:px-6")}>
                <Link to={`/analisis/${item.id}`} className="block">
                  <span className="line-clamp-2 font-medium text-slate-100 transition group-hover:text-cyan-200">
                    {item.title}
                  </span>
                  <span className="mt-1 flex items-center gap-2 text-xs text-slate-500">
                    {item.source_type === "social" || item.source_type === "url" ? (
                      <Link2 className="h-3 w-3" />
                    ) : (
                      <FileText className="h-3 w-3" />
                    )}
                    {item.publisher ?? "Input manual"}
                  </span>
                </Link>
              </td>
              <td className="px-4 py-4">
                <VerdictBadge verdict={item.verdict} short />
              </td>
              <td className="w-[130px] px-4 py-4">
                <div className="flex items-center gap-2">
                  <span className="w-7 text-sm font-semibold tabular-nums text-cyan-200">
                    {item.risk_score}
                  </span>
                  <ScoreBar score={item.risk_score} className="w-16" />
                </div>
              </td>
              <td className="whitespace-nowrap px-4 py-4 text-xs text-slate-500">
                {formatDate(item.created_at)}
              </td>
              <td className="px-5 py-4 text-right sm:px-6">
                <div className="flex items-center justify-end gap-1.5">
                  {onDelete ? (
                    <button
                      type="button"
                      onClick={() => onDelete(item)}
                      disabled={deletingId === item.id}
                      className="inline-flex rounded-lg border border-white/5 p-1.5 text-slate-500 transition hover:border-rose-400/30 hover:text-rose-300 disabled:cursor-not-allowed disabled:opacity-50"
                      aria-label={`Hapus analisis ${item.title}`}
                    >
                      {deletingId === item.id ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Trash2 className="h-4 w-4" />
                      )}
                    </button>
                  ) : null}
                  <Link
                    to={`/analisis/${item.id}`}
                    className="inline-flex rounded-lg border border-white/5 p-1.5 text-slate-500 transition group-hover:border-cyan-400/20 group-hover:text-cyan-300"
                    aria-label={`Buka detail ${item.title}`}
                  >
                    <ArrowUpRight className="h-4 w-4" />
                  </Link>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
