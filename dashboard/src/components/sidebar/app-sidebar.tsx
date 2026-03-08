"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { signOut } from "next-auth/react";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";
import {
  Zap, LayoutDashboard, Cpu, Settings, MessageSquare, Wand2, LogOut,
  Sun, Moon, BarChart2, DollarSign,
  Hash, BookOpen, Gauge, HelpCircle, Shield, Swords, Puzzle, CalendarClock,
} from "lucide-react";
import {
  Sidebar, SidebarContent, SidebarFooter, SidebarGroup,
  SidebarGroupContent, SidebarGroupLabel, SidebarHeader,
  SidebarMenu, SidebarMenuButton, SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar";
import { Button } from "@/components/ui/button";

const NAV_ITEMS = [
  { title: "Overview", href: "/dashboard", icon: LayoutDashboard },
  { title: "Providers", href: "/dashboard/providers", icon: Cpu },
  { title: "Settings", href: "/dashboard/settings", icon: Settings },
  { title: "Conversations", href: "/dashboard/conversations", icon: MessageSquare },
  { title: "Analytics", href: "/dashboard/analytics", icon: BarChart2 },
  { title: "Cost", href: "/dashboard/costs", icon: DollarSign },
];

const MANAGE_ITEMS = [
  { title: "Channel Prompts", href: "/dashboard/channel-prompts", icon: Hash },
  { title: "Onboarding", href: "/dashboard/onboarding", icon: BookOpen },
  { title: "Rate Limits", href: "/dashboard/rate-limits", icon: Gauge },
  { title: "FAQ", href: "/dashboard/faq", icon: HelpCircle },
  { title: "Permissions", href: "/dashboard/permissions", icon: Shield },
  { title: "Moderation", href: "/dashboard/moderation", icon: Swords },
  { title: "Plugins", href: "/dashboard/plugins", icon: Puzzle },
  { title: "Daily Digest", href: "/dashboard/daily-digest", icon: CalendarClock },
];

function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  if (!mounted) return null;
  return (
    <button
      onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
      className="flex items-center justify-center w-7 h-7 rounded-md text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
      aria-label="Toggle theme"
    >
      {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
    </button>
  );
}

function NavLink({ item, pathname }: { item: { title: string; href: string; icon: any }; pathname: string }) {
  const { setOpenMobile } = useSidebar();
  return (
    <SidebarMenuItem>
      <SidebarMenuButton asChild isActive={pathname === item.href}>
        <Link href={item.href} onClick={() => setOpenMobile(false)}>
          <item.icon className="h-4 w-4" />
          <span>{item.title}</span>
        </Link>
      </SidebarMenuButton>
    </SidebarMenuItem>
  );
}

export function AppSidebar() {
  const pathname = usePathname();
  return (
    <Sidebar collapsible="offcanvas">
      <SidebarHeader>
        <div className="flex items-center justify-between px-2 py-1">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
              <Zap className="h-4 w-4" />
            </div>
            <span className="font-semibold">SparkSage</span>
          </div>
          <ThemeToggle />
        </div>
      </SidebarHeader>

      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>Dashboard</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {NAV_ITEMS.map((item) => (
                <NavLink key={item.href} item={item} pathname={pathname} />
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        <SidebarGroup>
          <SidebarGroupLabel>Manage</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {MANAGE_ITEMS.map((item) => (
                <NavLink key={item.href} item={item} pathname={pathname} />
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        <SidebarGroup>
          <SidebarGroupLabel>Tools</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              <NavLink item={{ title: "Setup Wizard", href: "/wizard", icon: Wand2 }} pathname={pathname} />
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter>
        <Button
          variant="ghost"
          className="w-full justify-start"
          onClick={() => signOut({ callbackUrl: "/login" })}
        >
          <LogOut className="mr-2 h-4 w-4" />
          Sign Out
        </Button>
      </SidebarFooter>
    </Sidebar>
  );
}