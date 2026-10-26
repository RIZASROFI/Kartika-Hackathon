import { ArrowLeft } from "lucide-react";
import { Link } from "react-router-dom";

export default function NotFound() {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center text-center">
      <p className="font-mono text-xs uppercase tracking-[0.3em] text-cyan-400/70">404</p>
      <h1 className="mt-3 text-2xl font-semibold text-white">Halaman tidak ditemukan</h1>
      <p className="mt-2 max-w-md text-sm text-slate-400">
        Tautan yang Anda buka tidak tersedia atau sudah dipindahkan.
      </p>
      <Link to="/" className="btn-primary mt-6">
        <ArrowLeft className="h-4 w-4" /> Kembali ke dashboard
      </Link>
    </div>
  );
}
