import { notFound } from "next/navigation";

import { DetailModal } from "@/components/detail/detail-modal";
import { FoaDetail } from "@/components/detail/foa-detail";
import { ApiError } from "@/lib/api/client";
import { getOpportunity } from "@/lib/api/opportunities";

/**
 * Intercepts same-level navigation from /opportunities (i.e. clicking a
 * title in the list) and renders the detail as a modal over it instead of a
 * full-page transition -- while the URL still becomes a real
 * /opportunities/{foa_id}, so a reload or a shared link lands on the
 * canonical page ([foa_id]/page.tsx) instead, per Next's intercepting-route
 * convention. Same fetch, same <FoaDetail>, different shell.
 */
export default async function InterceptedOpportunityModal({
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
    <DetailModal title={foa.title}>
      <FoaDetail foa={foa} />
    </DetailModal>
  );
}
