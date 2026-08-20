import { Tags as TagsIcon } from "lucide-react";

import { Topbar } from "@/components/layout/topbar";
import { getTagCategories } from "@/lib/api/tags";
import { formatTagCategory } from "@/lib/format";

export default async function TagsPage() {
  const { categories } = await getTagCategories();

  return (
    <>
      <Topbar>
        <h1 className="font-heading text-lg font-semibold">Ontology Tags</h1>
      </Topbar>
      <main className="flex-1 overflow-y-auto p-6">
        <p className="mb-6 max-w-2xl text-sm text-muted-foreground">
          The controlled vocabulary the tagging pipeline applies to every funding opportunity --
          research domains, disciplines, methods, populations, and sponsor themes -- and how much
          each category is actually used across the ingested corpus.
        </p>

        {categories.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No tags found. Run the tagging pipeline first (make tag).
          </p>
        ) : (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {categories.map((cat) => (
              <div
                key={cat.category}
                className="flex flex-col gap-1 rounded-md border border-border bg-card p-4"
              >
                <div className="mb-1 flex items-center gap-2 text-primary">
                  <TagsIcon className="size-4" />
                  <span className="font-heading text-sm font-semibold">
                    {formatTagCategory(cat.category)}
                  </span>
                </div>
                <p className="text-2xl font-semibold text-foreground">
                  {cat.concept_count}
                  <span className="ml-1.5 text-sm font-normal text-muted-foreground">concepts</span>
                </p>
                <p className="text-sm text-muted-foreground">
                  Applied {cat.total_uses.toLocaleString()} time{cat.total_uses === 1 ? "" : "s"}
                </p>
              </div>
            ))}
          </div>
        )}
      </main>
    </>
  );
}
