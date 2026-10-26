import { ArrowUpRight, FileText, Link2 } from "lucide-react";
import { Link } from "react-router-dom";

import { ScoreBar, VerdictBadge } from "./ui";
import type { AnalysisListItem } from "../lib/types";
import { cn, formatDate } from "../lib/utils";

export default function AnalysisTable({ items }: { items: AnalysisListItem[] }) {
  return (
    <div className="-mx-5 overflow-x-auto sm:-mx-6">
      <table className="w-full min-w-[720px] border-collapse text-left text-sm">
        <thead>
          <tr className="border-y border-white/5 text-[11px] uppercase tracking-[0.14em] text-slate-500">
            <th className="px-5 py-3 font-medium sm:px-6">Konten</th>
            <th className="px-4 py-3 font-medium">Status</th>
            <th className="px-4 py-3 font-medium">Skor risiko</th>
            <th className="px-4 py-3 font-medium">Dianalisis</th>
            <th className="px-5 py-3 sm:px-6" aria-label="Aksi" />
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr
              key={item.id}
              className="group border-b border-white/5 transition last:border-0 hover:bg-white/[0.025]"
            >
              <td className="max-w-[360px] px-5 py-4 sm:px-6">
                <Link to={`/analisis/${item.id}`} className="block">
                  <span className="line-clamp-2 font-medium text-slate-100 transition group-hover:text-cyan-200">
                    {item.title}
                  </span>
                  <span className="mt-1 flex items-center gap-2 text-xs text-slate-500">
                    {item.source_type === "url" ? (
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
              <td className="w-[150px] px-4 py-4">
                <div className="flex items-center gap-2">
                  <span
                    className={cn(
                      "w-7 text-sm font-semibold tabular-nums",
                      item.risk_score >= 75
                        ? "text-rose-300"
                        : item.risk_score >= 50
                          ? "text-orange-300"
                          : item.risk_score >= 25
                            ? "text-amber-300"
                            : "text-emerald-300",
                    )}
                  >
                    {item.risk_score}
                  </span>
                  <ScoreBar score={item.risk_score} level={item.risk_level} className="w-16" />
                </div>
              </td>
              <td className="whitespace-nowrap px-4 py-4 text-xs text-slate-500">
                {formatDate(item.created_at)}
              </td>
              <td className="px-5 py-4 text-right sm:px-6">
                <Link
                  to={`/analisis/${item.id}`}
                  className="inline-flex rounded-lg border border-white/5 p-1.5 text-slate-500 transition group-hover:border-cyan-400/20 group-hover:text-cyan-300"
                  aria-label={`Buka detail ${item.title}`}
                >
                  <ArrowUpRight className="h-4 w-4" />
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
