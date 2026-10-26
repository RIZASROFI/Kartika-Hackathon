import { useMutation, useQueryClient } from "@tanstack/react-query";
import { zodResolver } from "@hookform/resolvers/zod";
import {
  ArrowRight,
  Bot,
  FileText,
  Flame,
  Info,
  Link2,
  Loader2,
  Network,
  Newspaper,
  ScanLine,
  ShieldAlert,
  Sparkles,
} from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Card, ErrorPanel } from "../components/ui";
import { api } from "../lib/api";
import type { AnalysisPayload } from "../lib/types";
import { cn, wordCount } from "../lib/utils";

const schema = z
  .object({
    mode: z.enum(["url", "text"]),
    url: z.string().optional(),
    text: z.string().optional(),
    title: z.string().max(512, "Judul maksimal 512 karakter.").optional(),
    publisher: z.string().max(256, "Nama penerbit maksimal 256 karakter.").optional(),
  })
  .superRefine((data, ctx) => {
    if (data.mode === "url") {
      const value = data.url?.trim() ?? "";
      if (!value) {
        ctx.addIssue({ code: "custom", path: ["url"], message: "URL artikel wajib diisi." });
      } else if (!/^https?:\/\/\S+$/i.test(value)) {
        ctx.addIssue({
          code: "custom",
          path: ["url"],
          message: "URL harus diawali http:// atau https:// dan tanpa spasi.",
        });
      }
    } else {
      const value = data.text?.trim() ?? "";
      if (!value) {
        ctx.addIssue({ code: "custom", path: ["text"], message: "Teks konten wajib diisi." });
      } else if (wordCount(value) < 8) {
        ctx.addIssue({
          code: "custom",
          path: ["text"],
          message: "Minimal 8 kata agar analisis memiliki cukup sinyal.",
        });
      }
    }
  });

type FormValues = z.infer<typeof schema>;

const MODES = [
  { value: "url" as const, label: "URL artikel", icon: Link2 },
  { value: "text" as const, label: "Teks manual", icon: FileText },
];

const ANALYSIS_AREAS = [
  { icon: Newspaper, label: "Hoaks & fakta", text: "Atribusi sumber dan tekanan menyebarkan." },
  { icon: Flame, label: "Provokasi", text: "Leksikon eskalasi dan polarisasi." },
  { icon: Network, label: "Koordinasi", text: "Kemiripan narasi dan kedekatan waktu." },
  { icon: Bot, label: "Bot & AI", text: "Pola templat dan keseragaman kalimat." },
];

export default function NewAnalysis() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const {
    register,
    handleSubmit,
    watch,
    setValue,
    clearErrors,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { mode: "url", url: "", text: "", title: "", publisher: "" },
  });

  const mode = watch("mode");
  const textValue = watch("text") ?? "";

  const mutation = useMutation({
    mutationFn: (values: FormValues) => {
      const payload: AnalysisPayload =
        values.mode === "url"
          ? { url: values.url?.trim() }
          : { text: values.text?.trim() };
      if (values.title?.trim()) {
        payload.title = values.title.trim();
      }
      if (values.publisher?.trim()) {
        payload.publisher = values.publisher.trim();
      }
      return api.createAnalysis(payload);
    },
    onSuccess: (analysis) => {
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      void queryClient.invalidateQueries({ queryKey: ["analyses"] });
      navigate(`/analisis/${analysis.id}`);
    },
  });

  return (
    <div className="space-y-6">
      <div>
        <p className="label">Ingest & analyze</p>
        <h1 className="mt-1.5 text-2xl font-semibold tracking-tight text-white">Analisis Konten</h1>
        <p className="mt-1.5 max-w-2xl text-sm text-slate-400">
          Tempelkan URL artikel atau teks mentah. Mesin akan mengekstrak isi, menghitung empat
          dimensi sinyal, dan menyusun laporan indikatif.
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
        <Card>
          <form
            onSubmit={handleSubmit((values) => mutation.mutate(values))}
            className="space-y-5"
            noValidate
          >
            <div>
              <span className="label">Sumber konten</span>
              <div className="mt-2 grid grid-cols-2 gap-2 rounded-xl border border-white/5 bg-ink-950/60 p-1">
                {MODES.map((item) => {
                  const Icon = item.icon;
                  const active = mode === item.value;
                  return (
                    <button
                      key={item.value}
                      type="button"
                      onClick={() => {
                        setValue("mode", item.value);
                        clearErrors(["url", "text"]);
                      }}
                      className={cn(
                        "flex items-center justify-center gap-2 rounded-lg px-3 py-2.5 text-sm transition",
                        active
                          ? "bg-cyan-400/15 font-medium text-cyan-200 shadow-[inset_0_0_0_1px_rgba(34,211,238,0.2)]"
                          : "text-slate-400 hover:text-slate-200",
                      )}
                    >
                      <Icon className="h-4 w-4" />
                      {item.label}
                    </button>
                  );
                })}
              </div>
            </div>

            {mode === "url" ? (
              <div>
                <label htmlFor="url" className="label">
                  URL artikel
                </label>
                <input
                  id="url"
                  type="url"
                  inputMode="url"
                  placeholder="https://contoh.id/artikel/yang-ingin-diperiksa"
                  className={cn("input mt-2", errors.url && "border-rose-400/50")}
                  aria-invalid={Boolean(errors.url)}
                  {...register("url")}
                />
                {errors.url ? (
                  <p className="mt-1.5 text-xs text-rose-300">{errors.url.message}</p>
                ) : (
                  <p className="mt-1.5 text-xs text-slate-500">
                    Server mengambil halaman, mengekstrak isi utama, lalu menganalisisnya. Host
                    internal diblokir.
                  </p>
                )}
              </div>
            ) : (
              <div>
                <div className="flex items-center justify-between">
                  <label htmlFor="text" className="label">
                    Teks konten
                  </label>
                  <span className="text-[11px] text-slate-500">
                    {wordCount(textValue)} kata
                  </span>
                </div>
                <textarea
                  id="text"
                  rows={10}
                  placeholder="Tempelkan isi postingan, komentar, atau artikel di sini…"
                  className={cn("input mt-2 resize-y leading-relaxed", errors.text && "border-rose-400/50")}
                  aria-invalid={Boolean(errors.text)}
                  {...register("text")}
                />
                {errors.text ? (
                  <p className="mt-1.5 text-xs text-rose-300">{errors.text.message}</p>
                ) : (
                  <p className="mt-1.5 text-xs text-slate-500">
                    Minimal 8 kata. Untuk analisis koordinasi, tambahkan beberapa konten serupa
                    secara berurutan.
                  </p>
                )}
              </div>
            )}

            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label htmlFor="title" className="label">
                  Judul <span className="normal-case tracking-normal text-slate-600">(opsional)</span>
                </label>
                <input
                  id="title"
                  placeholder="Judul konten"
                  className={cn("input mt-2", errors.title && "border-rose-400/50")}
                  {...register("title")}
                />
                {errors.title ? (
                  <p className="mt-1.5 text-xs text-rose-300">{errors.title.message}</p>
                ) : null}
              </div>
              <div>
                <label htmlFor="publisher" className="label">
                  Kanal / penerbit{" "}
                  <span className="normal-case tracking-normal text-slate-600">(opsional)</span>
                </label>
                <input
                  id="publisher"
                  placeholder="Nama media atau akun"
                  className={cn("input mt-2", errors.publisher && "border-rose-400/50")}
                  {...register("publisher")}
                />
                {errors.publisher ? (
                  <p className="mt-1.5 text-xs text-rose-300">{errors.publisher.message}</p>
                ) : null}
              </div>
            </div>

            {mutation.isError ? (
              <ErrorPanel message={(mutation.error as Error).message} />
            ) : null}

            <div className="flex flex-col-reverse gap-3 border-t border-white/5 pt-5 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-xs leading-relaxed text-slate-500">
                Hasil bersifat indikatif, bukan putusan kebenaran.
              </p>
              <button type="submit" disabled={mutation.isPending} className="btn-primary">
                {mutation.isPending ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Menganalisis…
                  </>
                ) : (
                  <>
                    <ScanLine className="h-4 w-4" />
                    Jalankan analisis
                    <ArrowRight className="h-4 w-4" />
                  </>
                )}
              </button>
            </div>
          </form>
        </Card>

        <div className="space-y-4">
          <Card>
            <div className="flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-cyan-300" />
              <h2 className="text-sm font-semibold text-white">Empat dimensi analisis</h2>
            </div>
            <ul className="mt-4 space-y-4">
              {ANALYSIS_AREAS.map((area) => {
                const Icon = area.icon;
                return (
                  <li key={area.label} className="flex gap-3">
                    <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border border-white/5 bg-white/[0.03]">
                      <Icon className="h-3.5 w-3.5 text-slate-400" />
                    </span>
                    <div>
                      <p className="text-xs font-medium text-slate-200">{area.label}</p>
                      <p className="mt-0.5 text-xs leading-relaxed text-slate-500">{area.text}</p>
                    </div>
                  </li>
                );
              })}
            </ul>
          </Card>

          <div className="rounded-2xl border border-amber-400/15 bg-amber-400/[0.04] p-4">
            <div className="flex items-center gap-2">
              <Info className="h-4 w-4 text-amber-300" />
              <p className="text-xs font-semibold text-amber-200">Batas kemampuan</p>
            </div>
            <p className="mt-2 text-xs leading-relaxed text-amber-100/60">
              Platform tidak mencocokkan fakta ke basis data eksternal dan tidak membaca metadata
              akun. Skor tinggi berarti perlu ditinjau, bukan otomatis salah atau buatan AI.
            </p>
          </div>

          <div className="rounded-2xl border border-white/5 bg-white/[0.02] p-4">
            <div className="flex items-center gap-2">
              <ShieldAlert className="h-4 w-4 text-slate-400" />
              <p className="text-xs font-semibold text-slate-300">Alur pemrosesan</p>
            </div>
            <ol className="mt-3 space-y-2 text-xs text-slate-500">
              <li>01 · Validasi sumber & proteksi SSRF</li>
              <li>02 · Ekstraksi isi artikel (Trafilatura + BS4)</li>
              <li>03 · Analisis heuristik empat dimensi</li>
              <li>04 · Pencocokan narasi dengan korpus tersimpan</li>
              <li>05 · Penyimpanan temuan & bukti</li>
            </ol>
          </div>
        </div>
      </div>
    </div>
  );
}
