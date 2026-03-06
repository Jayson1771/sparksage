"use client";

import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import { Save } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function DailyDigestPage() {
  const { data: session } = useSession();
  const token = (session as any)?.accessToken as string | undefined;
  const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };

  const [config, setConfig] = useState({ enabled: false, channel_id: "", send_time: "09:00" });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (!token) return;
    fetch(`${API_BASE}/api/manage/daily-digest`, { headers })
      .then(r => r.json())
      .then(d => { if (d && !d.detail) setConfig(c => ({ ...c, ...d })); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [token]);

  async function save() {
    setSaving(true);
    try {
      const res = await fetch(`${API_BASE}/api/manage/daily-digest`, {
        method: "POST", headers, body: JSON.stringify(config),
      });
      const data = await res.json();
      if (data.status === "ok") { setSaved(true); setTimeout(() => setSaved(false), 2000); }
    } finally { setSaving(false); }
  }

  if (loading) return <div className="flex items-center justify-center h-64"><p className="text-muted-foreground text-sm">Loading...</p></div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Daily Digest</h1>
          <p className="text-sm text-muted-foreground mt-1">AI-generated daily summary posted to a channel</p>
        </div>
        <Button onClick={save} disabled={saving}>
          <Save className="h-4 w-4 mr-2" />
          {saving ? "Saving..." : saved ? "✓ Saved!" : "Save Changes"}
        </Button>
      </div>

      <Card>
        <CardHeader><CardTitle className="text-base">Configuration</CardTitle></CardHeader>
        <CardContent className="space-y-5">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium">Enable Daily Digest</p>
              <p className="text-xs text-muted-foreground">Post an AI summary every day at the set time</p>
            </div>
            <button
              onClick={() => setConfig(c => ({ ...c, enabled: !c.enabled }))}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${config.enabled ? "bg-primary" : "bg-muted"}`}
            >
              <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${config.enabled ? "translate-x-6" : "translate-x-1"}`} />
            </button>
          </div>
          <div>
            <label className="text-xs font-medium text-muted-foreground mb-1 block">Channel ID</label>
            <Input
              placeholder="Right-click channel in Discord → Copy Channel ID"
              value={config.channel_id}
              onChange={e => setConfig(c => ({ ...c, channel_id: e.target.value }))}
              disabled={!config.enabled}
            />
          </div>
          <div>
            <label className="text-xs font-medium text-muted-foreground mb-1 block">Send Time (24h UTC)</label>
            <Input
              type="time"
              value={config.send_time}
              onChange={e => setConfig(c => ({ ...c, send_time: e.target.value }))}
              disabled={!config.enabled}
              className="w-36"
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle className="text-base">Discord Commands</CardTitle></CardHeader>
        <CardContent className="space-y-1.5 text-sm text-muted-foreground">
          {[
            ["/digest enable", "Enable the digest"],
            ["/digest disable", "Disable the digest"],
            ["/digest setchannel #channel", "Set the channel"],
            ["/digest settime 09:00", "Set send time"],
            ["/digest test", "Send a test digest now"],
            ["/digest status", "View current config"],
          ].map(([cmd, desc]) => (
            <div key={cmd} className="flex items-center gap-3">
              <code className="bg-muted px-1.5 py-0.5 rounded text-xs font-mono text-foreground">{cmd}</code>
              <span className="text-xs">{desc}</span>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}