"use client";

import { useRouter } from "next/navigation";
import type { ReactNode } from "react";

import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";

/**
 * Shell for the intercepting-route detail modal. Always rendered open --
 * this route only mounts when the modal should be showing at all (Next's
 * @modal/default.tsx renders null the rest of the time). Closing navigates
 * back rather than to a fixed URL, so it returns to wherever the user
 * actually came from (the list, with its filters/scroll position intact)
 * instead of assuming /opportunities.
 */
export function DetailModal({ title, children }: { title: string; children: ReactNode }) {
  const router = useRouter();

  return (
    <Dialog open onOpenChange={(open) => !open && router.back()}>
      <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-2xl">
        {/* Visually hidden: FoaDetail renders its own visible <h1>, this
            just satisfies Radix's accessibility requirement that every
            dialog have an accessible name. */}
        <DialogTitle className="sr-only">{title}</DialogTitle>
        {children}
      </DialogContent>
    </Dialog>
  );
}
