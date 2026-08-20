import { FacetFilterMenu } from "@/components/opportunities/facet-filter-menu";
import { OpportunitiesTable } from "@/components/opportunities/opportunities-table";
import { PaginationBar } from "@/components/opportunities/pagination-bar";
import { SearchInput } from "@/components/opportunities/search-input";
import { Topbar } from "@/components/layout/topbar";
import { getOpportunityFacets, listOpportunities } from "@/lib/api/opportunities";

const PAGE_SIZE = 20;

export default async function OpportunitiesPage({
  searchParams,
}: PageProps<"/opportunities">) {
  const params = await searchParams;
  const page = Number(params.page) || 1;
  const status = typeof params.status === "string" ? params.status : "open";
  const agency = typeof params.agency === "string" ? params.agency : undefined;
  const query = typeof params.query === "string" ? params.query : undefined;
  const sort = typeof params.sort === "string" ? params.sort : undefined;
  const order = params.order === "ASC" ? "ASC" : "DESC";

  // Independent requests -- facets intentionally ignore `query` (see
  // opportunities/routes.py: an FTS5 join for facet counts under free-text
  // search is real extra work, deferred), so they don't need to wait on or
  // be re-derived from the search result.
  const [{ items, total, pages }, facets] = await Promise.all([
    listOpportunities({ page, size: PAGE_SIZE, status, agency, query, sort, order }),
    getOpportunityFacets({ status, agency }),
  ]);

  return (
    <>
      <Topbar>
        <SearchInput />
        <FacetFilterMenu
          statusOptions={facets.status}
          agencyOptions={facets.agency}
          activeStatus={status}
          activeAgency={agency}
        />
      </Topbar>
      <main className="flex-1 overflow-y-auto p-6">
        <p className="mb-4 text-sm text-muted-foreground">
          {total.toLocaleString()} {status ?? ""} opportunit{total === 1 ? "y" : "ies"}
        </p>
        <OpportunitiesTable items={items} />
        <PaginationBar page={page} pages={pages} currentParams={params} />
      </main>
    </>
  );
}
