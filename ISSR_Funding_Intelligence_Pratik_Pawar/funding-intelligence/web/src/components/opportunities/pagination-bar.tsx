import { ChevronLeft, ChevronRight } from "lucide-react";
import Link from "next/link";
import type { AnchorHTMLAttributes, ReactNode } from "react";

import { buildSearchParams } from "@/lib/search-params";
import { cn } from "@/lib/utils";

interface PaginationBarProps {
  page: number;
  pages: number;
  currentParams: Record<string, string | string[] | undefined>;
}

// Server-renderable: plain <Link>s, no client component or state needed --
// page numbers are a direct URL change, not something that benefits from
// debouncing or optimistic local state the way the search box does.
export function PaginationBar({ page, pages, currentParams }: PaginationBarProps) {
  if (pages <= 1) return null;

  const hrefFor = (targetPage: number) =>
    buildSearchParams(currentParams, { page: String(targetPage) }, { resetPage: false });

  // Windowed page list (current +/- 2), with the first/last page always
  // shown -- matches simpler.grants.gov's "1, 2, 3 ... 69, Next" pattern
  // rather than rendering every page number for a large result set.
  const windowStart = Math.max(2, page - 2);
  const windowEnd = Math.min(pages - 1, page + 2);
  const middle: number[] = [];
  for (let p = windowStart; p <= windowEnd; p++) middle.push(p);

  return (
    <nav aria-label="Pagination" className="flex items-center justify-center gap-1 py-6">
      <PageLink
        href={hrefFor(page - 1)}
        disabled={page <= 1}
        aria-label="Previous page"
      >
        <ChevronLeft className="size-4" />
      </PageLink>

      <PageLink href={hrefFor(1)} active={page === 1}>
        1
      </PageLink>
      {windowStart > 2 && <span className="px-1 text-muted-foreground">...</span>}
      {middle.map((p) => (
        <PageLink key={p} href={hrefFor(p)} active={page === p}>
          {p}
        </PageLink>
      ))}
      {windowEnd < pages - 1 && <span className="px-1 text-muted-foreground">...</span>}
      {pages > 1 && (
        <PageLink href={hrefFor(pages)} active={page === pages}>
          {pages}
        </PageLink>
      )}

      <PageLink href={hrefFor(page + 1)} disabled={page >= pages} aria-label="Next page">
        <ChevronRight className="size-4" />
      </PageLink>
    </nav>
  );
}

function PageLink({
  href,
  active,
  disabled,
  children,
  ...rest
}: {
  href: string;
  active?: boolean;
  disabled?: boolean;
  children: ReactNode;
} & AnchorHTMLAttributes<HTMLAnchorElement>) {
  if (disabled) {
    return (
      <span className="flex size-9 items-center justify-center rounded-md text-muted-foreground/40">
        {children}
      </span>
    );
  }
  return (
    <Link
      href={href}
      className={cn(
        "flex size-9 items-center justify-center rounded-md text-sm font-medium transition-colors",
        active
          ? "bg-primary text-primary-foreground"
          : "text-foreground hover:bg-accent hover:text-accent-foreground",
      )}
      {...rest}
    >
      {children}
    </Link>
  );
}
