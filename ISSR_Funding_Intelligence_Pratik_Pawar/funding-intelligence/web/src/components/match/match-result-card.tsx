import { Loader2, Sparkles, Target, Zap } from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { MatchResult } from "@/lib/types";

const RELEVANCE_STYLE: Record<string, string> = {
  strong: "bg-status-open/15 text-status-open",
  moderate: "bg-status-forecasted/15 text-status-forecasted",
  weak: "bg-muted text-muted-foreground",
};

interface MatchResultCardProps {
  result: MatchResult;
  /** True while this specific card is awaiting its "explanation" stream
   * event -- it's within the explained window but hasn't arrived yet. */
  isExplaining?: boolean;
}

export function MatchResultCard({ result, isExplaining = false }: MatchResultCardProps) {
  return (
    <div className="rounded-md border border-border bg-card p-4">
      <div className="mb-2 flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-medium text-primary">
            {result.agency_code ?? result.agency ?? "Unknown agency"}
          </p>
          <Link
            href={`/opportunities/${result.foa_id}`}
            className="font-heading font-medium text-foreground hover:text-primary hover:underline"
          >
            {result.title}
          </Link>
        </div>
        <span className="inline-flex shrink-0 items-center gap-1 rounded-full bg-primary px-2.5 py-1 text-xs font-semibold text-primary-foreground">
          <Zap className="size-3" />
          {(result.hybrid_score * 100).toFixed(0)}% Match
        </span>
      </div>

      <div className="mb-3 flex flex-wrap gap-4 text-xs text-muted-foreground">
        <span className="inline-flex items-center gap-1">
          <Target className="size-3.5" />
          {(result.cosine_score * 100).toFixed(0)}% topic similarity
        </span>
        <span>{(result.tag_overlap_ratio * 100).toFixed(0)}% tag overlap</span>
      </div>

      {isExplaining ? (
        <div className="mb-3 flex items-center gap-2 rounded-md border border-primary/20 bg-primary/5 p-3 text-sm text-muted-foreground">
          <Loader2 className="size-3.5 shrink-0 animate-spin text-primary" />
          Generating AI explanation...
        </div>
      ) : (
        result.match_explanation && (
          <div className="mb-3 rounded-md border border-primary/20 bg-primary/5 p-3">
            <div className="mb-1 flex items-center gap-2 text-[0.65rem] font-bold tracking-wide text-primary uppercase">
              <Sparkles className="size-3" />
              AI Explanation
              {result.llm_relevance && (
                <Badge
                  className={cn(
                    "px-1.5 py-0 text-[0.6rem] uppercase",
                    RELEVANCE_STYLE[result.llm_relevance],
                  )}
                >
                  {result.llm_relevance}
                </Badge>
              )}
            </div>
            <p className="text-sm text-foreground">{result.match_explanation}</p>
          </div>
        )
      )}

      {result.matched_tags.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {result.matched_tags.map((tag) => (
            <span
              key={tag}
              className="rounded-full bg-secondary px-2.5 py-0.5 text-xs text-secondary-foreground"
            >
              {tag}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
