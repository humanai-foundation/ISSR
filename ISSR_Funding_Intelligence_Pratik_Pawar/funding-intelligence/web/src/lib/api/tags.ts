import { apiFetch } from "@/lib/api/client";
import type { TagCategorySummary } from "@/lib/types";

export function getTagCategories(): Promise<{ categories: TagCategorySummary[] }> {
  return apiFetch<{ categories: TagCategorySummary[] }>("/api/tags/categories");
}
