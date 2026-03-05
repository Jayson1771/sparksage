"use client";

import { useEffect, useState, useCallback } from "react";
import { useSession } from "next-auth/react";
import { Activity, Cpu, Wifi, WifiOff, Server, ArrowRight, RefreshCw } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import type { BotStatus, ProvidersResponse, ProviderItem } from "@/lib/api";

const REFRESH_INTERVAL_MS = 3000;

export default function DashboardOverview() {
  const { data: session } = useSession();
  const [botStatus, setBotStatus] = useState<BotStatus | null>(null);
  const [providersData, setProvidersData] = useState<ProvidersResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [lastRefreshed, setLastRefreshed] = useState<Date | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const token = (session as { accessToken?: string })?.accessToken;

  const fetchData = useCallback(
    async (isInitial = false) => {
      if (!token) return;
      if (!isInitial) setIsRefreshing(true);
      try {
        const [botResult, provResult] = await Promise.allSettled([
          api.getBotStatus(token),
          api.getProviders(token),
        ]);
        if (botResult.status === "fulfilled") setBotStatus(botResult.value);
        if (provResult.status === "fulfilled") setProvidersData(provResult.value);
        setLastRefreshed(new Date());
      } finally {
        if (isInitial) setLoading(false);
        setIsRefreshing(false);
      }
    },
    [token]
  );

  // Initial load
  useEffect(() => {
    fetchData(true);
  }, [fetchData]);

  // Auto-refresh every 3 seconds
  useEffect(() => {
    if (!token) return;
    const interval = setInterval(() => fetchData(false), REFRESH_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [token, fetchData]);

  const primaryProvider = providersData?.providers?.find((p) => p.is_primary);

  return (
    <div className="space-y-6">
      {/* Header with refresh indicator */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Overview</h1>
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <RefreshCw
            className={`h-3.5 w-3.5 ${isRefreshing ? "animate-spin text-indigo-500" : ""}`}
          />
          <span>
            {isRefreshing
              ? "Refreshing..."
              : lastRefreshed
              ? `Updated ${lastRefreshed.toLocaleTimeString()}`
              : ""}
          </span>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Bot Status</CardTitle>
            {botStatus?.online ? (
              <Wifi className="h-4 w-4 text-green-600" />
            ) : (
              <WifiOff className="h-4 w-4 text-muted-foreground" />
            )}
          </CardHeader>
          <CardContent>
            {loading ? (
              <p className="text-sm text-muted-foreground">Loading...</p>
            ) : (
              <Badge variant={botStatus?.online ? "default" : "secondary"}>
                {botStatus?.online ? "Online" : "Offline"}
              </Badge>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Latency</CardTitle>
            <Activity className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">
              {botStatus?.latency_ms != null ? `${Math.round(botStatus.latency_ms)}ms` : "--"}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Servers</CardTitle>
            <Server className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{botStatus?.guild_count ?? "--"}</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Active Provider</CardTitle>
            <Cpu className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {primaryProvider ? (
              <div>
                <p className="text-lg font-semibold">{primaryProvider.display_name}</p>
                <p className="text-xs text-muted-foreground">{primaryProvider.model}</p>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">--</p>
            )}
          </CardContent>
        </Card>
      </div>

      {providersData && providersData.fallback_order.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Fallback Chain</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap items-center gap-2">
              {providersData.fallback_order.map((name, i) => {
                const prov = providersData.providers.find((p: ProviderItem) => p.name === name);
                return (
                  <div key={name} className="flex items-center gap-2">
                    <div className="flex items-center gap-1.5 rounded-lg border px-3 py-1.5">
                      <div className={`h-2 w-2 rounded-full ${prov?.configured ? "bg-green-500" : "bg-gray-300"}`} />
                      <span className="text-sm">{prov?.display_name || name}</span>
                      {prov?.is_primary && (
                        <Badge variant="secondary" className="ml-1 text-xs">Primary</Badge>
                      )}
                    </div>
                    {i < providersData.fallback_order.length - 1 && (
                      <ArrowRight className="h-4 w-4 text-muted-foreground" />
                    )}
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}