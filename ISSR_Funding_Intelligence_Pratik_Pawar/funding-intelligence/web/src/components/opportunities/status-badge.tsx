import { cn } from "@/lib/utils";
import type { FoaStatus } from "@/lib/types";

const LABEL: Record<FoaStatus, string> = {
  open: "Open",
  closed: "Closed",
  forecasted: "Forecasted",
};

// Functional, not brand -- kept as plain green/red/amber (--status-* tokens,
// globals.css) rather than crimson, and identical between light and dark.
const DOT_CLASS: Record<FoaStatus, string> = {
  open: "bg-status-open",
  closed: "bg-status-closed",
  forecasted: "bg-status-forecasted",
};

export function StatusBadge({ status }: { status: FoaStatus }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-sm font-medium">
      <span className={cn("size-2 rounded-full", DOT_CLASS[status])} aria-hidden="true" />
      {LABEL[status] ?? status}
    </span>
  );
}
