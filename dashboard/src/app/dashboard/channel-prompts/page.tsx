"use client";

import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import { Hash, Plus, Trash2, Save, ChevronDown, ChevronUp } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface ChannelPrompt {
  id?: number;
  channel_id: string;
  channel_name: string;
  system_prompt: string;
  enabled: boolean;
}

export default function ChannelPromptsPage() {
  const { data: session } = useSession();
  const token = (session as any)?.accessToken as string | undefined;

  const [prompts, setPrompts] = useState<ChannelPrompt[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [newPrompt, setNewPrompt] = useState<ChannelPrompt>({
    channel_id: "",
    channel_name: "",
    system_prompt: "",
    enabled: true,
  });
  const [showAdd, setShowAdd] = useState(false);

  const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };

  async function fetchPrompts() {
    try {
      const res = await fetch(`${API_BASE}/api/manage/channel-prompts`, { headers });
      const data = await res.json();
      setPrompts(data.prompts || []);
    } catch {
      setPrompts([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { if (token) fetchPrompts(); }, [token]);

  async function savePrompt(prompt: ChannelPrompt) {
    setSaving(prompt.channel_id);
    try {
      await fetch(`${API_BASE}/api/manage/channel-prompts`, {
        method: "POST",
        headers,
        body: JSON.stringify(prompt),
      });
      await fetchPrompts();
    } finally {
      setSaving(null);
    }
  }

  async function deletePrompt(channelId: string) {
    try {
      await fetch(`${API_BASE}/api/manage/channel-prompts/${channelId}`, { method: "DELETE", headers });
      await fetchPrompts();
    } catch {}
  }

  async function addPrompt() {
    if (!newPrompt.channel_id || !newPrompt.system_prompt) return;
    await savePrompt(newPrompt);
    setNewPrompt({ channel_id: "", channel_name: "", system_prompt: "", enabled: true });
    setShowAdd(false);
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Channel Prompts</h1>
          <p className="text-sm text-muted-foreground mt-1">Set custom AI system prompts per channel</p>
        </div>
        <Button onClick={() => setShowAdd(!showAdd)}>
          <Plus className="h-4 w-4 mr-2" />
          Add Channel Prompt
        </Button>
      </div>

      {showAdd && (
        <Card className="border-primary/50">
          <CardHeader>
            <CardTitle className="text-base">New Channel Prompt</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-medium text-muted-foreground mb-1 block">Channel ID</label>
                <Input
                  placeholder="e.g. 123456789"
                  value={newPrompt.channel_id}
                  onChange={e => setNewPrompt({ ...newPrompt, channel_id: e.target.value })}
                />
              </div>
              <div>
                <label className="text-xs font-medium text-muted-foreground mb-1 block">Channel Name (optional)</label>
                <Input
                  placeholder="e.g. #support"
                  value={newPrompt.channel_name}
                  onChange={e => setNewPrompt({ ...newPrompt, channel_name: e.target.value })}
                />
              </div>
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground mb-1 block">System Prompt</label>
              <Textarea
                placeholder="You are a helpful assistant for this channel..."
                rows={4}
                value={newPrompt.system_prompt}
                onChange={e => setNewPrompt({ ...newPrompt, system_prompt: e.target.value })}
              />
            </div>
            <div className="flex gap-2">
              <Button onClick={addPrompt} disabled={!newPrompt.channel_id || !newPrompt.system_prompt}>
                <Save className="h-4 w-4 mr-2" /> Save
              </Button>
              <Button variant="outline" onClick={() => setShowAdd(false)}>Cancel</Button>
            </div>
          </CardContent>
        </Card>
      )}

      {loading ? (
        <div className="flex items-center justify-center h-48">
          <p className="text-muted-foreground text-sm">Loading...</p>
        </div>
      ) : prompts.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center h-48 gap-3">
            <Hash className="h-8 w-8 text-muted-foreground" />
            <p className="text-muted-foreground text-sm">No channel prompts configured yet.</p>
            <Button variant="outline" onClick={() => setShowAdd(true)}>
              <Plus className="h-4 w-4 mr-2" /> Add your first prompt
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {prompts.map((prompt) => (
            <Card key={prompt.channel_id}>
              <CardContent className="pt-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <Hash className="h-4 w-4 text-muted-foreground" />
                    <div>
                      <p className="font-medium text-sm">{prompt.channel_name || `Channel ${prompt.channel_id}`}</p>
                      <p className="text-xs text-muted-foreground">{prompt.channel_id}</p>
                    </div>
                    <Badge variant={prompt.enabled ? "default" : "secondary"}>
                      {prompt.enabled ? "Active" : "Disabled"}
                    </Badge>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setExpanded(expanded === prompt.channel_id ? null : prompt.channel_id)}
                    >
                      {expanded === prompt.channel_id ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-red-500 hover:text-red-600"
                      onClick={() => deletePrompt(prompt.channel_id)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
                {expanded === prompt.channel_id && (
                  <div className="mt-4 space-y-3 border-t pt-4">
                    <Textarea
                      rows={4}
                      defaultValue={prompt.system_prompt}
                      onChange={e => {
                        const updated = prompts.map(p =>
                          p.channel_id === prompt.channel_id ? { ...p, system_prompt: e.target.value } : p
                        );
                        setPrompts(updated);
                      }}
                    />
                    <Button
                      size="sm"
                      disabled={saving === prompt.channel_id}
                      onClick={() => savePrompt(prompt)}
                    >
                      <Save className="h-4 w-4 mr-2" />
                      {saving === prompt.channel_id ? "Saving..." : "Save Changes"}
                    </Button>
                  </div>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}