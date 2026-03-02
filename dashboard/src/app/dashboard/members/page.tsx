"use client";

import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import {
  AreaChart, Area, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend
} from "recharts";
import { Users, TrendingUp, TrendingDown, MessageSquare } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const GUILD_ID = process.env.NEXT_PUBLIC_GUILD_ID || "default";

const HOUR_LABELS = Array.from({ length: 24 }, (_, i) => {
  const h = i % 12 || 12;
  return `${h}${i < 12 ? "am" : "pm"}`;
});

export default function MemberAnalyticsPage() {
  const { data: session, status } = useSession();
  const token = (session as any)?.accessToken as string | undefined;

  const [days, setDays] = useState(30);
  const [overview, setOverview] = useState<any>(null);
  const [history, setHistory] = useState<any[]>([]);
  const [topMembers, setTopMembers] = useState<any[]>([]);
  const [peakHours, setPeakHours] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function fetchAll(d: number, tok: string) {
    setLoading(true);
    setError(null);
    try {
      const headers = { Authorization: `Bearer ${tok}` };
      const [ov, hist, top, peak] = await Promise.all([
        fetch(`${API_BASE}/api/members/${GUILD_ID}/overview?days=${d}`, { headers }).then(r => r.json()),
        fetch(`${API_BASE}/api/members/${GUILD_ID}/history?days=${d}`, { headers }).then(r => r.json()),
        fetch(`${API_BASE}/api/members/${GUILD_ID}/top?days=${d}`, { headers }).then(r => r.json()),
        fetch(`${API_BASE}/api/members/${GUILD_ID}/peak-hours?days=${d}`, { headers }).then(r => r.json()),
      ]);
      setOverview(ov);
      setHistory((hist.history || []).map((h: any) => ({ ...h, date: h.date?.slice(5) })));
      setTopMembers(top.members || []);
      setPeakHours((peak.hours || []).map((h: any) => ({ ...h, label: HOUR_LABELS[h.hour] })));
    } catch (err) {
      setError("Failed to load analytics. Make sure the API is running.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (status === "authenticated" && token) {
      fetchAll(days, token);
    }
  }, [status, token, days]);

  if (status === "loading") {
    return <div className="flex items-center justify-center h-64"><p className="text-muted-foreground">Loading session...</p></div>;
  }

  if (status === "unauthenticated") {
    return <div className="flex items-center justify-center h-64"><p className="text-muted-foreground">Not authenticated.</p></div>;
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-red-500 text-sm">{error}</p>
      </div>
    );
  }

  const netGrowth = (overview?.joins_30d || 0) - (overview?.leaves_30d || 0);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Member Analytics</h1>
        <div className="flex gap-2">
          {[7, 30, 90].map(d => (
            <Button key={d} size="sm" variant={days === d ? "default" : "outline"} onClick={() => setDays(d)}>
              {d}d
            </Button>
          ))}
        </div>
      </div>

      {/* Overview Cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">New Joins</CardTitle>
            <TrendingUp className="h-4 w-4 text-green-500" />
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold text-green-600">{loading ? "..." : (overview?.joins_30d || 0)}</p>
            <p className="text-xs text-muted-foreground mt-1">Last {days} days</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Members Left</CardTitle>
            <TrendingDown className="h-4 w-4 text-red-500" />
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold text-red-600">{loading ? "..." : (overview?.leaves_30d || 0)}</p>
            <p className="text-xs text-muted-foreground mt-1">Last {days} days</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Net Growth</CardTitle>
            <Users className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <p className={`text-2xl font-bold ${netGrowth >= 0 ? "text-green-600" : "text-red-600"}`}>
              {loading ? "..." : `${netGrowth >= 0 ? "+" : ""}${netGrowth}`}
            </p>
            <p className="text-xs text-muted-foreground mt-1">Last {days} days</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Active Members</CardTitle>
            <MessageSquare className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{loading ? "..." : (overview?.active_members || 0)}</p>
            <p className="text-xs text-muted-foreground mt-1">{overview?.total_messages || 0} total messages</p>
          </CardContent>
        </Card>
      </div>

      {/* Join/Leave History Chart */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Member Growth (Last {days} Days)</CardTitle>
        </CardHeader>
        <CardContent>
          {history.length > 0 ? (
            <ResponsiveContainer width="100%" height={280}>
              <AreaChart data={history}>
                <defs>
                  <linearGradient id="joinGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#22c55e" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#22c55e" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="leaveGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#ef4444" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Legend />
                <Area type="monotone" dataKey="joins" stroke="#22c55e" fill="url(#joinGrad)" name="Joins" strokeWidth={2} />
                <Area type="monotone" dataKey="leaves" stroke="#ef4444" fill="url(#leaveGrad)" name="Leaves" strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex items-center justify-center h-48">
              <p className="text-muted-foreground text-sm">No join/leave data yet.</p>
            </div>
          )}
        </CardContent>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        {/* Peak Hours */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Peak Activity Hours</CardTitle>
          </CardHeader>
          <CardContent>
            {peakHours.some(h => h.messages > 0) ? (
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={peakHours}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="label" tick={{ fontSize: 10 }} interval={2} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip formatter={(v: number) => [`${v} messages`, "Activity"]} />
                  <Bar dataKey="messages" fill="#6366f1" radius={[3, 3, 0, 0]} name="Messages" />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex items-center justify-center h-48">
                <p className="text-muted-foreground text-sm">No message activity tracked yet.</p>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Top Active Members */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Top Active Members</CardTitle>
          </CardHeader>
          <CardContent>
            {topMembers.length > 0 ? (
              <div className="space-y-2">
                {topMembers.map((member, i) => (
                  <div key={member.user_id} className="flex items-center justify-between py-1.5 border-b last:border-0">
                    <div className="flex items-center gap-3">
                      <span className="text-sm font-medium text-muted-foreground w-5">#{i + 1}</span>
                      <p className="text-sm font-medium">{member.username}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-bold">{member.message_count}</span>
                      <span className="text-xs text-muted-foreground">msgs</span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="flex items-center justify-center h-48">
                <p className="text-muted-foreground text-sm">No message activity yet.</p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}