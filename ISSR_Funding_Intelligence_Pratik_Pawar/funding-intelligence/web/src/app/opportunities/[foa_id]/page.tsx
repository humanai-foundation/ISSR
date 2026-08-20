import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { notFound } from "next/navigation";

import { Topbar } from "@/components/layout/topbar";
import { FoaDetail } from "@/components/detail/foa-detail";
import { ApiError } from "@/lib/api/client";
import { getOpportunity } from "@/lib/api/opportunities";

/**
 * Canonical detail route -- the must-ship half of Phase 3. Works on hard
 * refresh, direct navigation, and shared links regardless of whether the
 * intercepting modal (@modal/(.)[foa_id]) is also present; both render this
 * same fetch through the shared <FoaDetail>.
 */
export default async function OpportunityDetailPage({
  params,
}: PageProps<"/opportunities/[foa_id]">) {
  const { foa_id } = await params;

  let foa;
  try {
    foa = await getOpportunity(foa_id);
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) notFound();
    throw err;
  }

  return (
    <>
      <Topbar>
        <Link
          href="/opportunities"
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="size-4" />
          Back to Opportunities
        </Link>
      </Topbar>
      <main className="flex-1 overflow-y-auto p-6">
        <div className="mx-auto max-w-3xl">
          <FoaDetail foa={foa} />
        </div>
      </main>
    </>
  );
}
