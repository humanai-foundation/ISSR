import { Skeleton } from "@/components/ui/skeleton";

export default function OpportunitiesLoading() {
  return (
    <>
      <div className="flex h-16 shrink-0 items-center gap-3 border-b border-border px-6">
        <Skeleton className="size-8" />
        <Skeleton className="h-9 w-full max-w-xl" />
      </div>
      <main className="flex flex-1 gap-6 overflow-y-auto p-6">
        <div className="hidden w-64 shrink-0 flex-col gap-3 md:flex">
          <Skeleton className="h-5 w-16" />
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-4 w-full" />
          ))}
        </div>
        <div className="min-w-0 flex-1">
          <Skeleton className="mb-4 h-4 w-40" />
          <div className="flex flex-col gap-2">
            {Array.from({ length: 10 }).map((_, i) => (
              <Skeleton key={i} className="h-12 w-full" />
            ))}
          </div>
        </div>
      </main>
    </>
  );
}
