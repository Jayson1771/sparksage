"use client";

import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import { Swords, Save, Plus, Trash2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function ModerationPage() {
  const { data: session } = useSession();
  const token = (session as any)?.accessToken as string | undefined;
  const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };

  const [config, setConfig] = useState({
    auto_mod_enabled: true,
    sensitivity: "medium",
    filter_profanity: true,
    filter_spam: true,
    filter_links: false,
    filter_invites: true,
    max_mentions: 5,
    max_emojis: 10,
    log_channel_id: "",
    banned_words: [] as string[],
    warn_before_ban: true,
    max_warnings: 3,
    mute_duration_minutes: 10,
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [newWord, setNewWord] = useState("");

  useEffect(() => {
    if (!token) return;
    fetch(`${API_BASE}/api/manage/moderation`, { headers })
      .then(r => r.json())
      .then(d => { if (d && !d.detail) setConfig(c => ({ ...c, ...d })); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [token]);

  async function save() {
    setSaving(true);
    try {
      await fetch(`${API_BASE}/api/manage/moderation`, {
        method: "POST", headers, body: JSON.stringify(config),
      });
    } finally {
      setSaving(false);
    }
  }

  const toggles = [
    { key: "auto_mod_enabled", label: "Auto Moderation", desc: "Automatically moderate messages" },
    { key: "filter_profanity", label: "Filter Profanity", desc: "Remove messages with profanity" },
    { key: "filter_spam", label: "Filter Spam", desc: "Detect and remove spam messages" },
    { key: "filter_links", label: "Filter Links", desc: "Remove unauthorized links" },
    { key: "filter_invites", label: "Filter Invites", desc: "Block Discord server invites" },
    { key: "warn_before_ban", label: "Warn Before Ban", desc: "Issue warnings before banning" },
  ];

  if (loading) return <div className="flex items-center justify-center h-64"><p className="text-muted-foreground text-sm">Loading...</p></div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Moderation</h1>
          <p className="text-sm text-muted-foreground mt-1">Auto-moderate your server and manage user behavior</p>
        </div>
        <Button onClick={save} disabled={saving}>
          <Save className="h-4 w-4 mr-2" />
          {saving ? "Saving..." : "Save Changes"}
        </Button>
      </div>

      {/* Sensitivity */}
      <Card>
        <CardHeader><CardTitle className="text-base">AI Sensitivity</CardTitle></CardHeader>
        <CardContent>
          <div className="flex gap-3">
            {["low", "medium", "high"].map(level => (
              <button
                key={level}
                onClick={() => setConfig(c => ({ ...c, sensitivity: level }))}
                className={`flex-1 py-2 rounded-lg border text-sm font-medium transition-colors capitalize ${config.sensitivity === level ? "bg-primary text-primary-foreground border-primary" : "bg-transparent text-muted-foreground border-muted-foreground/30 hover:border-primary"}`}
              >
                {level}
              </button>
            ))}
          </div>
          <p className="text-xs text-muted-foreground mt-2">Low = only high severity · Medium = medium+high · High = flag everything</p>
        </CardContent>
      </Card>

      {/* Toggles */}
      <Card>
        <CardHeader><CardTitle className="text-base">Auto Moderation</CardTitle></CardHeader>
        <CardContent className="space-y-1 divide-y">
          {toggles.map(t => (
            <div key={t.key} className="flex items-center justify-between py-3">
              <div>
                <p className="text-sm font-medium">{t.label}</p>
                <p className="text-xs text-muted-foreground">{t.desc}</p>
              </div>
              <button
                onClick={() => setConfig(c => ({ ...c, [t.key]: !(c as any)[t.key] }))}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${(config as any)[t.key] ? "bg-primary" : "bg-muted"}`}
              >
                <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${(config as any)[t.key] ? "translate-x-6" : "translate-x-1"}`} />
              </button>
            </div>
          ))}
        </CardContent>
      </Card>

      {/* Limits */}
      <Card>
        <CardHeader><CardTitle className="text-base">Limits & Thresholds</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          {[
            { key: "max_mentions", label: "Max Mentions per Message", min: 1, max: 50 },
            { key: "max_emojis", label: "Max Emojis per Message", min: 1, max: 100 },
            { key: "max_warnings", label: "Max Warnings Before Ban", min: 1, max: 20 },
            { key: "mute_duration_minutes", label: "Mute Duration (minutes)", min: 1, max: 10080 },
          ].map(item => (
            <div key={item.key} className="flex items-center justify-between gap-4">
              <p className="text-sm font-medium">{item.label}</p>
              <Input
                type="number"
                min={item.min}
                max={item.max}
                value={(config as any)[item.key]}
                onChange={e => setConfig(c => ({ ...c, [item.key]: parseInt(e.target.value) || 0 }))}
                className="w-28 text-center"
              />
            </div>
          ))}
          <div className="flex items-center justify-between gap-4">
            <p className="text-sm font-medium">Log Channel ID</p>
            <Input
              placeholder="Channel ID for mod logs"
              value={config.log_channel_id}
              onChange={e => setConfig(c => ({ ...c, log_channel_id: e.target.value }))}
              className="w-48"
            />
          </div>
        </CardContent>
      </Card>

      {/* Banned Words */}
      <Card>
        <CardHeader><CardTitle className="text-base">Banned Words</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <div className="flex gap-2">
            <Input
              placeholder="Add a banned word or phrase"
              value={newWord}
              onChange={e => setNewWord(e.target.value)}
              onKeyDown={e => { if (e.key === "Enter" && newWord.trim()) { setConfig(c => ({ ...c, banned_words: [...c.banned_words, newWord.trim()] })); setNewWord(""); }}}
            />
            <Button variant="outline" onClick={() => { if (newWord.trim()) { setConfig(c => ({ ...c, banned_words: [...c.banned_words, newWord.trim()] })); setNewWord(""); }}}>
              <Plus className="h-4 w-4" />
            </Button>
          </div>
          <div className="flex flex-wrap gap-2">
            {config.banned_words.length === 0
              ? <p className="text-sm text-muted-foreground">No banned words configured.</p>
              : config.banned_words.map((word, i) => (
                <Badge key={i} variant="destructive" className="gap-1">
                  {word}
                  <button onClick={() => setConfig(c => ({ ...c, banned_words: c.banned_words.filter((_, idx) => idx !== i) }))}>×</button>
                </Badge>
              ))
            }
          </div>
        </CardContent>
      </Card>
    </div>
  );
}