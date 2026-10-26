export type Verdict =
  | "terkoordinasi"
  | "terindikasi_menyesatkan"
  | "provokatif"
  | "perlu_verifikasi"
  | "risiko_rendah";

export type RiskLevel = "rendah" | "sedang" | "tinggi" | "kritis";

export type SignalCategory = "hoax" | "provocation" | "coordination" | "bot_ai";

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

export interface Claim {
  id: string;
  text: string;
  verdict: string;
  rationale: string;
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

export interface RelatedAnalysis {
  id: string;
  title: string;
  verdict: Verdict;
  risk_score: number;
  similarity: number;
  hours_apart: number | null;
  shared_phrases: string[];
}

export interface ContentMeta {
  source_type: "url" | "text";
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
  source_type: "url" | "text";
  url: string | null;
  publisher: string | null;
  created_at: string;
}

export interface AnalysisDetail extends AnalysisListItem {
  engine_version: string;
  model_used: string | null;
  processing_ms: number;
  limitations: string[];
  content: ContentMeta;
  signals: Signal[];
  claims: Claim[];
  evidence: Evidence[];
  related: RelatedAnalysis[];
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
  coordination_links: number;
  claims: number;
}

export interface CoordinationAlert {
  analysis_id: string;
  title: string;
  verdict: Verdict;
  risk_score: number;
  related_title: string;
  similarity: number;
  hours_apart: number | null;
  created_at: string;
}

export interface DashboardSummary {
  generated_at: string;
  totals: DashboardTotals;
  verdict_distribution: VerdictSlice[];
  risk_trend: TrendPoint[];
  category_scores: CategoryScore[];
  recent_analyses: AnalysisListItem[];
  coordination_alerts: CoordinationAlert[];
}
