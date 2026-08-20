import { ExternalLink } from "lucide-react";
import type { ReactNode } from "react";

import { StatusBadge } from "@/components/opportunities/status-badge";
import { awardRange, formatDate, formatSourceLayer, formatTagCategory } from "@/lib/format";
import type { FoaDetail as FoaDetailType } from "@/lib/types";

/**
 * Shared by the canonical page (opportunities/[foa_id]/page.tsx) and the
 * intercepting-route modal (opportunities/@modal/(.)[foa_id]/page.tsx) --
 * one component, two shells around it, so the two views can't drift apart.
 */
export function FoaDetail({ foa }: { foa: FoaDetailType }) {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <p className="text-sm font-medium text-primary">
          {foa.agency ?? foa.agency_code ?? "Unknown agency"}
          {foa.opportunity_number ? ` · ${foa.opportunity_number}` : ""}
        </p>
        <h1 className="font-heading text-2xl font-semibold text-foreground">{foa.title}</h1>
      </div>

      <dl className="grid grid-cols-2 gap-4 rounded-md border border-border bg-card p-4 sm:grid-cols-4">
        <MetaItem label="Status">
          <StatusBadge status={foa.status} />
        </MetaItem>
        <MetaItem label="Close Date">{formatDate(foa.close_date)}</MetaItem>
        <MetaItem label="Award Range">{awardRange(foa.award_floor, foa.award_ceiling)}</MetaItem>
        <MetaItem label="CFDA Numbers">
          {foa.cfda_numbers.length > 0 ? foa.cfda_numbers.join(", ") : "N/A"}
        </MetaItem>
      </dl>

      <Section title="Program Description">
        <p className="whitespace-pre-line text-sm text-foreground">
          {foa.program_description || "No description available."}
        </p>
      </Section>

      <Section title="Eligibility">
        <p className="whitespace-pre-line text-sm text-foreground">
          {foa.eligibility_description || (foa.eligibility.length > 0 ? foa.eligibility.join(", ") : "Not specified.")}
        </p>
      </Section>

      {foa.tags.length > 0 && (
        <Section title="Semantic Tags & Evidence">
          <div className="flex flex-col gap-3">
            {foa.tags.map((tag) => (
              <div key={tag.tag_id} className="rounded-md border border-border bg-card p-3">
                <div className="mb-1.5 flex flex-wrap items-center justify-between gap-2">
                  <span className="inline-flex items-center gap-1.5">
                    <span className="rounded-full bg-secondary px-2.5 py-0.5 text-xs font-medium text-secondary-foreground">
                      {tag.label}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      {formatTagCategory(tag.category)}
                    </span>
                  </span>
                  <span className="text-xs text-muted-foreground">
                    {formatSourceLayer(tag.source_layer)} · {(tag.confidence * 100).toFixed(0)}% conf
                  </span>
                </div>
                {tag.context_snippet && (
                  <p className="border-l-2 border-border pl-3 text-sm text-muted-foreground italic">
                    &ldquo;...{tag.context_snippet}...&rdquo;
                  </p>
                )}
              </div>
            ))}
          </div>
        </Section>
      )}

      {foa.source_url && (
        <a
          href={foa.source_url}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center justify-center gap-2 self-start rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary-hover"
        >
          View Original on {foa.source === "grants_gov" ? "Grants.gov" : "Source"}
          <ExternalLink className="size-3.5" />
        </a>
      )}
    </div>
  );
}

function MetaItem({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <dt className="text-xs font-medium tracking-wide text-muted-foreground uppercase">{label}</dt>
      <dd className="mt-0.5 text-sm font-medium text-foreground">{children}</dd>
    </div>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div>
      <h2 className="mb-2 font-heading text-base font-semibold text-foreground">{title}</h2>
      {children}
    </div>
  );
}
