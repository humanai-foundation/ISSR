import type { ReactNode } from "react";

import { ThemeToggle } from "@/components/layout/theme-toggle";
import { SidebarTrigger } from "@/components/ui/sidebar";

/**
 * Shell topbar: the search input itself is Phase 2 work (lives in the
 * Opportunities view, since it drives that view's URL-state filtering) --
 * this just reserves the row and carries the hamburger (opens the
 * off-canvas sidebar, see layout.tsx's SidebarProvider defaultOpen={false})
 * and the theme toggle, so every view has both from Phase 0 onward.
 */
export function Topbar({ children }: { children?: ReactNode }) {
  return (
    <header className="flex h-16 shrink-0 items-center justify-between gap-4 border-b-2 border-primary bg-background px-6">
      <div className="flex flex-1 items-center gap-3">
        <SidebarTrigger />
        {children}
      </div>
      <ThemeToggle />
    </header>
  );
}
