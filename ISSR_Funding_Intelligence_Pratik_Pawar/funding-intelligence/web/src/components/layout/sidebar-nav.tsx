"use client";

import { Table2, Tags, WandSparkles } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ComponentType } from "react";

import {
  Sidebar,
  SidebarContent,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar";

const NAV_ITEMS: { href: string; label: string; icon: ComponentType<{ className?: string }> }[] = [
  { href: "/opportunities", label: "Opportunities", icon: Table2 },
  { href: "/match", label: "AI Match", icon: WandSparkles },
  { href: "/tags", label: "Ontology Tags", icon: Tags },
];

export function SidebarNav() {
  const pathname = usePathname();
  const { setOpenMobile, isMobile } = useSidebar();

  // Off-canvas by default (see SidebarProvider defaultOpen={false} in
  // layout.tsx) and toggled by the hamburger (SidebarTrigger) in Topbar --
  // the user wants it hidden until opened, not a persistent column. On
  // mobile the sidebar is a Sheet overlay; closing it after a nav click
  // matches how every mobile drawer nav behaves (desktop can stay open
  // across navigations since it doesn't cover content).
  const handleNavigate = () => {
    if (isMobile) setOpenMobile(false);
  };

  return (
    <Sidebar collapsible="offcanvas">
      <SidebarHeader>
        <Link
          href="/opportunities"
          onClick={handleNavigate}
          className="flex flex-col items-center px-2 py-3 text-center"
        >
          <span className="font-wordmark text-base font-bold tracking-tight whitespace-nowrap text-sidebar-foreground">
            Funding Intelligence
          </span>
          <span className="text-[10px] font-semibold whitespace-nowrap text-sidebar-primary">
            Institute for Social Sciences and Research
          </span>
        </Link>
      </SidebarHeader>

      <SidebarContent>
        <SidebarMenu className="px-2">
          {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
            const active = pathname?.startsWith(href);
            return (
              <SidebarMenuItem key={href}>
                <SidebarMenuButton
                  asChild
                  isActive={active}
                  onClick={handleNavigate}
                  // The base component styles the active state via
                  // data-active:bg-sidebar-accent (a muted highlight). An
                  // unconditional bg-sidebar-primary override lost that fight
                  // silently: cn()/tailwind-merge treats a bare bg-* utility
                  // and a data-active:bg-* variant as non-conflicting, so
                  // both applied and CSS source order picked the base one.
                  // Targeting the SAME data-active: variant, always present
                  // (gated by the data-active attribute itself, exactly like
                  // the base classes are), gives predictable override order.
                  className="data-active:bg-sidebar-primary data-active:text-sidebar-primary-foreground data-active:hover:bg-sidebar-primary data-active:hover:text-sidebar-primary-foreground"
                >
                  <Link href={href}>
                    <Icon />
                    <span>{label}</span>
                  </Link>
                </SidebarMenuButton>
              </SidebarMenuItem>
            );
          })}
        </SidebarMenu>
      </SidebarContent>
    </Sidebar>
  );
}
