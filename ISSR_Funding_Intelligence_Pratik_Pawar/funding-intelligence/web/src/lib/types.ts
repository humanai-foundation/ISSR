/**
 * Shapes mirror the FastAPI backend exactly (src/foa_pipeline/api/routes/,
 * src/foa_pipeline/storage/database.py) -- see Documentation/MATCHING.md and this repo's
 * root README for the source of truth.
 */

export type FoaStatus = "open" | "closed" | "forecasted";

export interface FoaTag {
  tag_id: string;
  label: string;
  category: string;
  source_layer: string;
  confidence: number;
  context_snippet: string;
  ontology_concept_id: string;
}

/**
 * Fields present on every list/search endpoint. Deliberately narrower than
 * FoaDetail: list_foas()/search_fts() don't attach cfda_numbers/eligibility
 * (only the single-item detail query does), so a list item claiming to have
 * them would be lying about what the API actually returns.
 */
export interface FoaListItem {
  foa_id: string;
  source: string;
  source_id: string;
  source_url: string | null;
  title: string;
  agency: string | null;
  agency_code: string | null;
  opportunity_number: string | null;
  posted_date: string | null;
  close_date: string | null;
  archive_date: string | null;
  status: FoaStatus;
  funding_instrument: string | null;
  award_floor: number | null;
  award_ceiling: number | null;
  expected_awards: number | null;
  estimated_funding: number | null;
  program_description: string | null;
  eligibility_description: string | null;
  additional_info: string | null;
  funding_tiers: unknown[];
  ingestion_date: string;
  last_updated: string;
  tags: FoaTag[];
}

export interface FoaDetail extends FoaListItem {
  cfda_numbers: string[];
  eligibility: string[];
}

export interface PaginatedEnvelope<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

export interface FacetOption {
  value: string;
  count: number;
}

export interface FacetCounts {
  status: FacetOption[];
  agency: FacetOption[];
}

/** POST /api/match result item: a FoaListItem plus hybrid-score fields. */
export interface MatchResult extends FoaListItem {
  cosine_score: number;
  tag_overlap_ratio: number;
  matched_tags: string[];
  hybrid_score: number;
  match_explanation?: string;
  llm_relevance?: "strong" | "moderate" | "weak" | null;
}

export interface MatchResponse {
  items: MatchResult[];
  total: number;
  llm_available: boolean;
  message: string;
}

/**
 * POST /api/match/stream: same ranking/explanation as MatchResponse, spread
 * across newline-delimited events instead of one response at the end --
 * see matching/explain.py for why (explaining each candidate is a
 * sequential local-LLM call, seconds apiece, so an atomic response makes
 * the caller wait for all of them before seeing any). A discriminated
 * union on `type` so a switch over it is exhaustively checked.
 */
export type MatchStreamEvent =
  | {
      type: "ranked";
      items: MatchResult[];
      total: number;
      /** Leading item count to expect an "explanation" event for. */
      explain_window_size: number;
      message: string;
    }
  | {
      type: "explanation";
      foa_id: string;
      match_explanation: string;
      llm_relevance: "strong" | "moderate" | "weak" | null;
    }
  | { type: "reorder"; foa_ids: string[] }
  | { type: "done"; llm_available: boolean };

export interface TagCategorySummary {
  category: string;
  concept_count: number;
  total_uses: number;
}
