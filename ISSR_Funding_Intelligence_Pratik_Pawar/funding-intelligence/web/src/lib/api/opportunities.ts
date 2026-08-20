import { apiFetch } from "@/lib/api/client";
import type { FacetCounts, FoaDetail, PaginatedEnvelope, FoaListItem } from "@/lib/types";

export interface ListOpportunitiesParams {
  page?: number;
  size?: number;
  status?: string;
  agency?: string;
  sort?: string;
  order?: "ASC" | "DESC";
  query?: string;
}

function toQueryString(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") search.set(key, String(value));
  }
  const qs = search.toString();
  return qs ? `?${qs}` : "";
}

/**
 * Keyword search (POST /api/search/keyword) when `query` is set, otherwise
 * the plain listing (GET /api/opportunities) -- mirrors the old app's
 * behaviour of a single search box that either lists or searches.
 */
export function listOpportunities({
  query,
  ...params
}: ListOpportunitiesParams): Promise<PaginatedEnvelope<FoaListItem>> {
  if (query) {
    return apiFetch<PaginatedEnvelope<FoaListItem>>("/api/search/keyword", {
      method: "POST",
      body: JSON.stringify({ query, ...params }),
    });
  }
  return apiFetch<PaginatedEnvelope<FoaListItem>>(
    `/api/opportunities${toQueryString(params as Record<string, string | number | undefined>)}`,
  );
}

export function getOpportunityFacets(params: {
  status?: string;
  agency?: string;
}): Promise<FacetCounts> {
  return apiFetch<FacetCounts>(`/api/opportunities/facets${toQueryString(params)}`);
}

export function getOpportunity(foaId: string): Promise<FoaDetail> {
  return apiFetch<FoaDetail>(`/api/opportunities/${encodeURIComponent(foaId)}`);
}
