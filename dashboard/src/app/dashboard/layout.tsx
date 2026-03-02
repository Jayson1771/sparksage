import { auth } from "@/lib/auth";
import { redirect } from "next/navigation";
import { AppSidebar } from "@/components/sidebar/app-sidebar";
import {
  SidebarProvider,
  SidebarInset,
} from "@/components/ui/sidebar";

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
        <div className="flex-1 p-4 sm:p-6">
          {children}
        </div>
      </SidebarInset>
    </SidebarProvider>
  );
}