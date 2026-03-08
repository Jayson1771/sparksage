import { auth } from "@/lib/auth";
import { redirect } from "next/navigation";
import { AppSidebar } from "@/components/sidebar/app-sidebar";
import { SidebarProvider, SidebarInset, SidebarTrigger } from "@/components/ui/sidebar";
import { Separator } from "@/components/ui/separator";

export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const session = await auth();
  if (!session) redirect("/login");

  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset>
        {/* Mobile header with hamburger trigger */}
        <header className="flex h-12 items-center gap-2 border-b px-4 md:hidden">
          <SidebarTrigger className="-ml-1" />
          <Separator orientation="vertical" className="h-4" />
          <span className="font-semibold text-sm">SparkSage</span>
        </header>
        <div className="flex-1 p-4 sm:p-6">
          {children}
        </div>
      </SidebarInset>
    </SidebarProvider>
  );
}