"use client";

import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import {
  BarChart, Bar, LineChart, Line, XAxis, YAxis,
  CartesianGrid, Tooltip, Legend, ResponsiveContainer, Cell
} from "recharts";
import { DollarSign, TrendingUp, AlertTriangle, Zap } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const PROVIDER_COLORS: Record<string, string> = {
  gemini: "#4285F4",
  groq: "#F55036",
  openrouter: "#7C3AED",
  anthropic: "#D97706",
  openai: "#10A37F",
};

interface ProviderCost {
  provider: string;
  total_cost: number;
  total_requests: number;
  total_input_tokens: number;
  total_output_tokens: number;
}

interface DailyCost {
  date: string;
  provider: string;
  daily_cost: number;
  requests: number;
}

interface Projection {
  week_cost: number;
  daily_avg_cost: number;
  daily_avg_requests: number;
  projected_monthly: number;
}

function formatCost(cost: number): string {
  if (cost === 0) return "Free";
  if (cost < 0.001) return `$${cost.toFixed(6)}`;
  if (cost < 0.01) return `$${cost.toFixed(4)}`;
  return `$${cost.toFixed(2)}`;
}

const PRICING = [
  { provider: "gemini",      input: 0,    output: 0,     free: true },
  { provider: "groq",        input: 0,    output: 0,     free: true },
  { provider: "openrouter",  input: 0,    output: 0,     free: true },
  { provider: "anthropic",   input: 3.00, output: 15.00, free: false },
  { provider: "openai",      input: 2.50, output: 10.00, free: false },
];

export default function CostPage() {
  const { data: session } = useSession();
  const [providerCosts, setProviderCosts] = useState<ProviderCost[]>([]);
  const [dailyCosts, setDailyCosts] = useState<DailyCost[]>([]);
  const [projection, setProjection] = useState<Projection | null>(null);
  const [threshold] = useState(10.0);
  const [loading, setLoading] = useState(true);

  const token = (session as { accessToken?: string })?.accessToken;
  const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  useEffect(() => {
    if (!token) return;
    const headers = { Authorization: `Bearer ${token}` };

    Promise.all([
      fetch(`${apiBase}/api/analytics/costs/providers`, { headers }).then(r => r.json()),
      fetch(`${apiBase}/api/analytics/costs/daily`, { headers }).then(r => r.json()),
      fetch(`${apiBase}/api/analytics/costs/projection`, { headers }).then(r => r.json()),
    ]).then(([providers, daily, proj]) => {
      setProviderCosts(providers.providers || []);
      setDailyCosts(daily.history || []);
      setProjection(proj);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, [token]);

  const totalCost = providerCosts.reduce((sum, p) => sum + (p.total_cost || 0), 0);
  const monthPercent = Math.min(100, (totalCost / threshold) * 100);

  // Aggregate daily costs across providers for line chart
  const dailyAggregated = Object.entries(
    dailyCosts.reduce((acc: Record<string, number>, row) => {
      const d = row.date?.slice(5) || row.date;
      acc[d] = (acc[d] || 0) + (row.daily_cost || 0);
      return acc;
    }, {})
  ).map(([date, cost]) => ({ date, cost })).slice(-14);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-muted-foreground">Loading cost data...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Cost Tracking</h1>

      {/* Summary Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">This Month</CardTitle>
            <DollarSign className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{formatCost(totalCost)}</p>
            <div className="mt-2 h-1.5 w-full rounded-full bg-muted">
              <div
                className={`h-1.5 rounded-full transition-all ${
                  monthPercent >= 100 ? "bg-red-500" :
                  monthPercent >= 80  ? "bg-orange-400" : "bg-green-500"
                }`}
                style={{ width: `${monthPercent}%` }}
              />
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              {monthPercent.toFixed(0)}% of ${threshold} budget
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Projected Monthly</CardTitle>
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">
              {projection ? formatCost(projection.projected_monthly) : "--"}
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              Based on last 7 days
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Daily Average</CardTitle>
            <Zap className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">
              {projection ? formatCost(projection.daily_avg_cost) : "--"}
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              {projection?.daily_avg_requests?.toFixed(0) || 0} requests/day
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Alert Threshold</CardTitle>
            <AlertTriangle className={`h-4 w-4 ${monthPercent >= 80 ? "text-orange-400" : "text-muted-foreground"}`} />
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">${threshold.toFixed(2)}</p>
            <p className={`text-xs mt-1 ${
              monthPercent >= 100 ? "text-red-500" :
              monthPercent >= 80  ? "text-orange-400" : "text-muted-foreground"
            }`}>
              {monthPercent >= 100 ? "⚠️ Threshold exceeded!" :
               monthPercent >= 80  ? "⚠️ Approaching limit" : "✅ Within budget"}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Daily Cost Line Chart */}
      {dailyAggregated.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Daily Cost — Last 14 Days</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={dailyAggregated}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                <XAxis dataKey="date" tick={{ fontSize: 12 }} />
                <YAxis
                  tick={{ fontSize: 12 }}
                  tickFormatter={(v) => v === 0 ? "$0" : `$${v.toFixed(4)}`}
                />
                <Tooltip formatter={(v: number | undefined) => formatCost(v ?? 0)} />
                <Line
                  type="monotone"
                  dataKey="cost"
                  stroke="#f59e0b"
                  strokeWidth={2}
                  dot={false}
                  name="Cost"
                />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      )}

      {/* Cost by Provider Bar Chart */}
      {providerCosts.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Cost by Provider (30 Days)</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={providerCosts}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                <XAxis dataKey="provider" tick={{ fontSize: 12 }} />
                <YAxis
                  tick={{ fontSize: 12 }}
                  tickFormatter={(v) => v === 0 ? "Free" : `$${v.toFixed(4)}`}
                />
                <Tooltip
                  formatter={(v: number | undefined, name: string | undefined) => [formatCost(v ?? 0), name ?? ""]}
                />
                <Bar dataKey="total_cost" name="Cost" radius={[4, 4, 0, 0]}>
                  {providerCosts.map((entry) => (
                    <Cell
                      key={entry.provider}
                      fill={PROVIDER_COLORS[entry.provider] || "#6366f1"}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      )}

      {/* Pricing Table */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Provider Pricing (per 1M tokens)</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b">
                  <th className="text-left py-2 font-medium">Provider</th>
                  <th className="text-right py-2 font-medium">Input</th>
                  <th className="text-right py-2 font-medium">Output</th>
                  <th className="text-right py-2 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {PRICING.map((p) => (
                  <tr key={p.provider} className="border-b last:border-0">
                    <td className="py-2 font-mono">{p.provider}</td>
                    <td className="py-2 text-right">
                      {p.free ? <span className="text-green-500">Free</span> : `$${p.input.toFixed(2)}`}
                    </td>
                    <td className="py-2 text-right">
                      {p.free ? <span className="text-green-500">Free</span> : `$${p.output.toFixed(2)}`}
                    </td>
                    <td className="py-2 text-right">
                      {p.free
                        ? <span className="text-green-500 font-medium">✅ Free</span>
                        : <span className="text-orange-400">💰 Paid</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-xs text-muted-foreground mt-3">
            Costs are estimated from token counts. Actual charges may vary slightly.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}