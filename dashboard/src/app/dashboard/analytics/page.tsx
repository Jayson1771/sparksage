"use client";

import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import {
  LineChart, Line, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer
} from "recharts";
import { Activity, MessageSquare, Zap, Server } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";

const PROVIDER_COLORS: Record<string, string> = {
  gemini: "#4285F4",
  groq: "#F55036",
  openrouter: "#7C3AED",
  anthropic: "#D97706",
  openai: "#10A37F",
  none: "#9CA3AF",
};

interface AnalyticsSummary {
  total_events: number;
  counts: Record<string, number>;
  avg_latency: number;
  provider_distribution: { provider: string; count: number }[];
  daily_history: { date: string; count: number }[];
}

export default function AnalyticsPage() {
  const { data: session } = useSession();
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null);
  const [loading, setLoading] = useState(true);

  const token = (session as { accessToken?: string })?.accessToken;

  useEffect(() => {
    if (!token) return;
    fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/analytics/summary`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => r.json())
      .then((data) => {
        setSummary(data);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [token]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-muted-foreground">Loading analytics...</p>
      </div>
    );
  }

  if (!summary) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-muted-foreground">No analytics data yet. Start chatting with the bot!</p>
      </div>
    );
  }

  const totalMessages = (summary.counts?.command || 0) + (summary.counts?.mention || 0);
  const totalCommands = summary.counts?.command || 0;
  const totalMentions = summary.counts?.mention || 0;
  const totalFaqs = summary.counts?.faq || 0;

  // Format provider distribution for pie chart
  const providerData = summary.provider_distribution?.map((p) => ({
    name: p.provider,
    value: p.count,
    color: PROVIDER_COLORS[p.provider] || "#9CA3AF",
  })) || [];

  // Format daily history for line chart
  const dailyData = summary.daily_history?.map((d) => ({
    date: d.date?.slice(5), // Show MM-DD
    messages: d.count,
  })) || [];

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Analytics</h1>

      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Total Messages</CardTitle>
            <MessageSquare className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{totalMessages.toLocaleString()}</p>
            <p className="text-xs text-muted-foreground mt-1">
              {totalCommands} commands · {totalMentions} mentions
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Avg Latency</CardTitle>
            <Zap className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">
              {summary.avg_latency ? `${Math.round(summary.avg_latency)}ms` : "--"}
            </p>
            <p className="text-xs text-muted-foreground mt-1">Average AI response time</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Total Events</CardTitle>
            <Server className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{summary.total_events?.toLocaleString() || 0}</p>
            <p className="text-xs text-muted-foreground mt-1">All tracked bot events</p>
          </CardContent>
        </Card>
      </div>

      {/* Messages Per Day Line Chart */}
      {dailyData.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Messages Per Day (Last 30 Days)</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={250}>
              <LineChart data={dailyData}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                <XAxis dataKey="date" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip />
                <Line
                  type="monotone"
                  dataKey="messages"
                  stroke="#6366f1"
                  strokeWidth={2}
                  dot={false}
                  name="Messages"
                />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      )}

      <div className="grid gap-4 md:grid-cols-2">
        {/* Provider Distribution Pie Chart */}
        {providerData.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Provider Usage</CardTitle>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={250}>
                <PieChart>
                  <Pie
                    data={providerData}
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={100}
                    paddingAngle={3}
                    dataKey="value"
                    nameKey="name"
                    label={({ name, percent }) =>
                      `${name} ${((percent ?? 0) * 100).toFixed(0)}%`
                    }
                    labelLine={false}
                  >
                    {providerData.map((entry, index) => (
                      <Cell key={index} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip
                    formatter={(value: number | undefined, name: string | undefined) => [
                      `${value ?? 0} requests`,
                      name ?? "",
        ]}
                  />
                </PieChart>
              </ResponsiveContainer>
              {/* Legend */}
              <div className="flex flex-wrap gap-2 mt-2 justify-center">
                {providerData.map((p) => (
                  <div key={p.name} className="flex items-center gap-1 text-xs">
                    <div
                      className="h-2 w-2 rounded-full"
                      style={{ backgroundColor: p.color }}
                    />
                    <span className="capitalize">{p.name}</span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Event Type Bar Chart */}
        {summary.counts && Object.keys(summary.counts).length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Event Breakdown</CardTitle>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={250}>
                <BarChart
                  data={Object.entries(summary.counts).map(([type, count]) => ({
                    type: type.charAt(0).toUpperCase() + type.slice(1),
                    count,
                  }))}
                >
                  <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                  <XAxis dataKey="type" tick={{ fontSize: 12 }} />
                  <YAxis tick={{ fontSize: 12 }} />
                  <Tooltip />
                  <Bar dataKey="count" fill="#6366f1" radius={[4, 4, 0, 0]} name="Events" />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        )}
      </div>

      {providerData.length === 0 && dailyData.length === 0 && (
        <Card>
          <CardContent className="flex items-center justify-center h-32">
            <p className="text-muted-foreground text-sm">
              No data yet — start using the bot to see analytics here.
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}