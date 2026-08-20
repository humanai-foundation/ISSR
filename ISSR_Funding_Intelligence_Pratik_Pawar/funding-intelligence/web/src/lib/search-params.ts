/**
 * Filters/sort/pagination all live in the URL, not React state -- this is
 * the single place that builds a new query string from the current one plus
 * overrides, so every component that mutates search params (facet
 * checkboxes, column-sort clicks, the search box, pagination links) agrees
 * on the same rules: `undefined`/empty values are removed rather than
 * serialized as "undefined", and changing a filter always resets `page`
 * back to 1 (a stale page number past the new, smaller result set would
 * otherwise silently render an empty page).
 */
export function buildSearchParams(
  current: Record<string, string | string[] | undefined>,
  overrides: Record<string, string | undefined>,
  { resetPage = true }: { resetPage?: boolean } = {},
): string {
  const params = new URLSearchParams();

  for (const [key, value] of Object.entries(current)) {
    if (typeof value === "string" && value) params.set(key, value);
  }
  for (const [key, value] of Object.entries(overrides)) {
    if (value) {
      params.set(key, value);
    } else {
      params.delete(key);
    }
  }
  if (resetPage && !("page" in overrides)) {
    params.delete("page");
  }

  const qs = params.toString();
  return qs ? `?${qs}` : "";
}
