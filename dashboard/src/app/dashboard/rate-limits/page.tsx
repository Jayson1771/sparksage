"use client";

import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import { Gauge, Save } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function RateLimitsPage() {
  const { data: session } = useSession();
  const token = (session as any)?.accessToken as string | undefined;
  const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };

  const [config, setConfig] = useState({
    messages_per_minute: 10,
    messages_per_hour: 100,
    messages_per_day: 500,
    cooldown_seconds: 5,
    max_tokens_per_message: 2000,
    enabled: true,
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (!token) return;
    fetch(`${API_BASE}/api/manage/rate-limits`, { headers })
      .then(r => r.json())
      .then(d => { if (d && !d.detail) setConfig(c => ({ ...c, ...d })); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [token]);

  async function save() {
    setSaving(true);
    try {
      await fetch(`${API_BASE}/api/manage/rate-limits`, {
        method: "POST", headers, body: JSON.stringify(config),
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <div className="flex items-center justify-center h-64"><p className="text-muted-foreground text-sm">Loading...</p></div>;

  const limits = [
    { key: "messages_per_minute", label: "Messages per Minute", description: "Max messages a user can send per minute", min: 1, max: 60 },
    { key: "messages_per_hour", label: "Messages per Hour", description: "Max messages a user can send per hour", min: 1, max: 500 },
    { key: "messages_per_day", label: "Messages per Day", description: "Max messages a user can send per day", min: 1, max: 5000 },
    { key: "cooldown_seconds", label: "Cooldown (seconds)", description: "Wait time between consecutive messages", min: 0, max: 300 },
    { key: "max_tokens_per_message", label: "Max Tokens per Message", description: "Maximum token length per AI response", min: 100, max: 8000 },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Rate Limits</h1>
          <p className="text-sm text-muted-foreground mt-1">Control how often users can interact with the bot</p>
        </div>
        <Button onClick={save} disabled={saving}>
          <Save className="h-4 w-4 mr-2" />
          {saving ? "Saving..." : saved ? "Saved!" : "Save Changes"}
        </Button>
      </div>

      <Card>
        <CardHeader><CardTitle className="text-base">Global Rate Limiting</CardTitle></CardHeader>
        <CardContent className="space-y-1">
          <div className="flex items-center justify-between py-2">
            <div>
              <p className="text-sm font-medium">Enable Rate Limiting</p>
              <p className="text-xs text-muted-foreground">Apply limits to all users globally</p>
            </div>
            <button
              onClick={() => setConfig(c => ({ ...c, enabled: !c.enabled }))}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${config.enabled ? "bg-primary" : "bg-muted"}`}
            >
              <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${config.enabled ? "translate-x-6" : "translate-x-1"}`} />
            </button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle className="text-base">Limit Configuration</CardTitle></CardHeader>
        <CardContent className="space-y-5">
          {limits.map(limit => (
            <div key={limit.key} className="flex items-center justify-between gap-4">
              <div className="flex-1">
                <p className="text-sm font-medium">{limit.label}</p>
                <p className="text-xs text-muted-foreground">{limit.description}</p>
              </div>
              <div className="flex items-center gap-2 w-36">
                <Input
                  type="number"
                  min={limit.min}
                  max={limit.max}
                  value={(config as any)[limit.key]}
                  onChange={e => setConfig(c => ({ ...c, [limit.key]: parseInt(e.target.value) || 0 }))}
                  className="text-center"
                  disabled={!config.enabled}
                />
              </div>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle className="text-base">Current Limits Summary</CardTitle></CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
            {limits.map(limit => (
              <div key={limit.key} className="bg-muted rounded-lg p-3 text-center">
                <p className="text-2xl font-bold">{(config as any)[limit.key]}</p>
                <p className="text-xs text-muted-foreground mt-1">{limit.label}</p>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
