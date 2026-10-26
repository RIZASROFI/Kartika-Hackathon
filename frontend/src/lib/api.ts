import type {
  AnalysisDetail,
  AnalysisListItem,
  AnalysisPayload,
  DashboardSummary,
  Verdict,
} from "./types";

const BASE_URL = import.meta.env.VITE_API_URL ?? "/api/v1";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function extractDetail(payload: unknown): string {
  if (!payload || typeof payload !== "object") {
    return "Permintaan gagal diproses.";
  }
  const detail = (payload as { detail?: unknown }).detail;
  if (typeof detail === "string") {
    return detail;
  }
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (item && typeof item === "object" && "msg" in item) {
          return String((item as { msg: unknown }).msg);
        }
        return String(item);
      })
      .join("; ");
  }
  return "Permintaan gagal diproses.";
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers ?? {}),
      },
    });
  } catch {
    throw new ApiError(
      "Tidak dapat menghubungi server analisis. Pastikan backend berjalan di port 8000.",
      0,
    );
  }

  const payload: unknown = await response.json().catch(() => null);

  if (!response.ok) {
    throw new ApiError(extractDetail(payload), response.status);
  }

  return payload as T;
}

export const api = {
  createAnalysis(payload: AnalysisPayload): Promise<AnalysisDetail> {
    return request<AnalysisDetail>("/analyses", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  listAnalyses(options?: { verdict?: Verdict | null; limit?: number }): Promise<AnalysisListItem[]> {
    const params = new URLSearchParams();
    if (options?.verdict) {
      params.set("verdict", options.verdict);
    }
    params.set("limit", String(options?.limit ?? 50));
    return request<AnalysisListItem[]>(`/analyses?${params.toString()}`);
  },

  getAnalysis(id: string): Promise<AnalysisDetail> {
    return request<AnalysisDetail>(`/analyses/${id}`);
  },

  getDashboard(): Promise<DashboardSummary> {
    return request<DashboardSummary>("/dashboard/summary");
  },
};
