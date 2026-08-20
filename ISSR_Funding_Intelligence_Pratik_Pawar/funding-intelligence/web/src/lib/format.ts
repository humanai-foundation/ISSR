// Shared by the opportunities table and the FOA detail view -- kept in one
// place so the two never quietly disagree on how a null close_date or a
// missing award_floor renders.

export function formatDate(value: string | null): string {
  if (!value) return "Continuous";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

export function formatMoney(value: number | null): string {
  if (value === null || value === undefined) return "—";
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `$${(value / 1_000).toFixed(0)}K`;
  return `$${value}`;
}

export function awardRange(floor: number | null, ceiling: number | null): string {
  if (floor === null && ceiling === null) return "Not specified";
  if (floor === null) return `Up to ${formatMoney(ceiling)}`;
  if (ceiling === null) return `From ${formatMoney(floor)}`;
  if (floor === ceiling) return formatMoney(floor);
  return `${formatMoney(floor)} – ${formatMoney(ceiling)}`;
}

const SOURCE_LAYER_LABEL: Record<string, string> = {
  layer_1_terminological: "L1 Exact",
  layer_2_embedding: "L2 AI Match",
  layer_3_llm: "L3 LLM Verified",
  layer_4_cfda_crosswalk: "CFDA Crosswalk",
};

export function formatSourceLayer(layer: string): string {
  return SOURCE_LAYER_LABEL[layer] ?? layer;
}

const TAG_CATEGORY_LABEL: Record<string, string> = {
  research_domain: "Research Domain",
  research_discipline: "Research Discipline",
  method: "Method",
  population: "Population",
  sponsor_theme: "Sponsor Theme",
};

export function formatTagCategory(category: string): string {
  return TAG_CATEGORY_LABEL[category] ?? category;
}
