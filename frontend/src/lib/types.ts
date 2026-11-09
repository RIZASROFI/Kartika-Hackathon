export type Verdict =
  | "terindikasi_fakta"
  | "terindikasi_hoaks"
  | "campuran"
  | "perlu_verifikasi"
  | "belum_dapat_dinilai"
  // Format lama (engine heuristic-1.x) tetap dibaca agar riwayat tidak rusak.
  | "terindikasi_menyesatkan"
  | "risiko_rendah";

export type EvidenceStance = "mendukung" | "membantah" | "sebagian" | "netral";

export interface DecisionItem {
  title: string;
  url: string;
  publisher: string;
  snippet: string;
  stance: EvidenceStance;
  stance_label: string;
  kind: string;
  provider: string;
  relevance: number;
  credibility: number;
  recency: number;
  weight: number;
  group: string;
  published_at: string | null;
  note?: string | null;
}

export interface EvidenceDecision {
  engine: string;
  verdict: Verdict;
  label: string;
  confidence: number;
  rationale: string;
  summary: string;
  sufficient: boolean;
  insufficient_reason: string | null;
  conflict: boolean;
  support_weight: number;
  refute_weight: number;
  partial_weight: number;
  support_groups: number;
  refute_groups: number;
  partial_groups: number;
  independent_groups: number;
  item_count: number;
  /** Skor maksimum tiap dimensi; UI menulis bobot sebagai "nilai/maksimum". */
  scales?: {
    relevance: number;
    credibility: number;
    recency: number;
    weight: number;
  };
  narrative_risk: number;
  provider_status: Record<string, string>;
  items: DecisionItem[];
}

export type RiskLevel = "rendah" | "sedang" | "tinggi" | "kritis";

export type SignalCategory = "hoax" | "indobert";

export interface Signal {
  id: string;
  category: SignalCategory;
  title: string;
  score: number;
  level: RiskLevel;
  confidence: number;
  explanation: string;
  details: string[];
}

export type EvidenceStatus = "didukung" | "dibantah" | "tidak_cukup_bukti";

export interface ClaimCitation {
  title: string;
  url: string;
  publisher: string;
  snippet?: string;
}

export interface Claim {
  id: string;
  text: string;
  verdict: string;
  rationale: string;
  evidence_status?: EvidenceStatus | "";
  verification_note?: string;
  citations?: ClaimCitation[];
  verified_at?: string | null;
}

export interface ClaimCheckSummary {
  provider: string;
  status: "verified" | "no_evidence" | "unavailable" | "disabled";
  model: string | null;
  message: string | null;
  claim_count: number;
  verified_count: number;
  evidence_count: number;
  claims: Array<{
    claim: string;
    status: EvidenceStatus;
    rationale: string;
    citations: ClaimCitation[];
  }>;
}

export interface Evidence {
  id: string;
  title: string;
  url: string | null;
  publisher: string | null;
  kind: string;
  snippet: string | null;
  retrieved_at: string;
}

export type FactCheckVerdict = "hoax" | "sebagian_benar" | "fakta" | "tidak_jelas";

export interface FactCheckHit {
  claim: string;
  rating: string;
  status: FactCheckVerdict;
  publisher: string;
  url: string;
  title: string;
  review_date: string | null;
  query: string;
  provider?: string;
  reference_only?: boolean;
}

export interface FactCheckSummary {
  provider: string;
  providers?: string[];
  status: "matched" | "no_match" | "unavailable" | "disabled";
  queries: string[];
  keywords?: string[];
  checked_at: string;
  message: string | null;
  hit_count: number;
  hits: FactCheckHit[];
}

export interface ContentMeta {
  source_type: "url" | "text" | "social";
  url: string | null;
  title: string | null;
  author: string | null;
  publisher: string | null;
  word_count: number;
  published_at: string | null;
}

export interface AnalysisListItem {
  id: string;
  title: string;
  verdict: Verdict;
  risk_score: number;
  risk_level: RiskLevel;
  confidence: number;
  summary: string;
  source_type: "url" | "text" | "social";
  url: string | null;
  publisher: string | null;
  created_at: string;
}

export interface AnalysisDetail extends AnalysisListItem {
  engine_version: string;
  model_used: string | null;
  processing_ms: number;
  limitations: string[];
  factcheck: Partial<FactCheckSummary>;
  claim_check: Partial<ClaimCheckSummary>;
  decision: Partial<EvidenceDecision>;
  content: ContentMeta;
  signals: Signal[];
  claims: Claim[];
  evidence: Evidence[];
}

export interface AnalysisPayload {
  url?: string;
  text?: string;
  title?: string;
  publisher?: string;
}

export interface VerdictSlice {
  verdict: Verdict;
  label: string;
  count: number;
}

export interface TrendPoint {
  date: string;
  analyses: number;
  average_risk: number;
  high_risk: number;
}

export interface CategoryScore {
  category: SignalCategory;
  label: string;
  average_score: number;
  max_score: number;
}

export interface DashboardTotals {
  analyses: number;
  contents: number;
  high_risk: number;
  average_risk: number;
  claims: number;
}

export interface DashboardSummary {
  generated_at: string;
  totals: DashboardTotals;
  verdict_distribution: VerdictSlice[];
  risk_trend: TrendPoint[];
  category_scores: CategoryScore[];
  recent_analyses: AnalysisListItem[];
}
