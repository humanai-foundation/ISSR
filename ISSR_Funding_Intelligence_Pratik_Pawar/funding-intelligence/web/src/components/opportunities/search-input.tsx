"use client";

import { Search } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { Input } from "@/components/ui/input";
import { useDebouncedValue } from "@/hooks/use-debounced-value";
import { buildSearchParams } from "@/lib/search-params";

const DEBOUNCE_MS = 300;

export function SearchInput() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const urlQuery = searchParams.get("query") ?? "";

  const [value, setValue] = useState(urlQuery);
  // Tracks the last URL value this component has already synced FROM, so the
  // render-time adjustment below fires exactly once per external URL change
  // (a facet click resetting the page, browser back/forward, a shared link)
  // and not on every render. This is React's own documented pattern for
  // "adjust state when a prop changes" -- setState during render, not inside
  // an effect: React discards the in-progress render and re-renders
  // immediately with the new state, without the extra committed frame (and
  // the set-state-in-effect lint violation) an effect would cause here.
  const [lastSyncedQuery, setLastSyncedQuery] = useState(urlQuery);
  if (urlQuery !== lastSyncedQuery) {
    setLastSyncedQuery(urlQuery);
    setValue(urlQuery);
  }

  const debounced = useDebouncedValue(value, DEBOUNCE_MS);

  useEffect(() => {
    if (debounced === urlQuery) return;
    const qs = buildSearchParams(
      Object.fromEntries(searchParams.entries()),
      { query: debounced || undefined },
    );
    router.replace(`${pathname}${qs}`, { scroll: false });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- re-running on searchParams/router identity would fight the debounce
  }, [debounced]);

  return (
    <div className="relative w-full max-w-2xl">
      <Search className="pointer-events-none absolute top-1/2 left-4 size-5 -translate-y-1/2 text-muted-foreground" />
      <Input
        type="search"
        placeholder="Search funding opportunities, agencies, or CFDA numbers..."
        value={value}
        onChange={(e) => setValue(e.target.value)}
        className="h-12 pl-11 text-base"
        aria-label="Search funding opportunities"
      />
    </div>
  );
}
