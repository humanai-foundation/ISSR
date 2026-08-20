/**
 * Declares the @modal parallel route slot for the intercepting-route detail
 * modal (@modal/(.)[foa_id]/page.tsx). Deliberately no chrome of its own --
 * both opportunities/page.tsx (the list) and opportunities/[foa_id]/page.tsx
 * (the canonical detail page) already render their own <Topbar>+<main>, so
 * this layout is just a passthrough that also renders whichever modal slot
 * is active (or nothing, via @modal/default.tsx, when none is).
 */
export default function OpportunitiesLayout({
  children,
  modal,
}: LayoutProps<"/opportunities">) {
  return (
    <>
      {children}
      {modal}
    </>
  );
}
