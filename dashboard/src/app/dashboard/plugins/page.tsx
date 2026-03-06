"use client";

import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import { Puzzle } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Plugin {
  name: string;
  version: string;
  author: string;
  description: string;
  commands?: string[];
  _folder: string;
  enabled: boolean;
}

export default function PluginsPage() {
  const { data: session } = useSession();
  const token = (session as any)?.accessToken as string | undefined;
  const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };

  const [plugins, setPlugins] = useState<Plugin[]>([]);
  const [loading, setLoading] = useState(true);
  const [toggling, setToggling] = useState<string | null>(null);

  async function fetchPlugins() {
    if (!token) return;
    try {
      const res = await fetch(`${API_BASE}/api/manage/plugins`, { headers });
      const data = await res.json();
      setPlugins(data.plugins || []);
    } catch {
      setPlugins([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { fetchPlugins(); }, [token]);

  async function togglePlugin(plugin: Plugin) {
    setToggling(plugin._folder);
    const action = plugin.enabled ? "disable" : "enable";
    try {
      await fetch(`${API_BASE}/api/manage/plugins/${plugin._folder}/${action}`, {
        method: "POST", headers,
      });
      setPlugins(ps => ps.map(p =>
        p._folder === plugin._folder ? { ...p, enabled: !p.enabled } : p
      ));
    } catch {
    } finally {
      setToggling(null);
    }
  }

  if (loading) return (
    <div className="flex items-center justify-center h-64">
      <p className="text-muted-foreground text-sm">Loading plugins...</p>
    </div>
  );

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Plugins</h1>
        <p className="text-sm text-muted-foreground mt-1">
          {plugins.filter(p => p.enabled).length} of {plugins.length} plugin(s) enabled
        </p>
      </div>

      {plugins.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center h-48 gap-3">
            <Puzzle className="h-8 w-8 text-muted-foreground" />
            <p className="text-muted-foreground text-sm">No plugins found in the plugins/ directory.</p>
            <p className="text-xs text-muted-foreground">Add a plugin folder with a manifest.json to get started.</p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          {plugins.map(plugin => (
            <Card key={plugin._folder} className={`transition-all ${plugin.enabled ? "border-primary/50 bg-primary/5" : ""}`}>
              <CardContent className="pt-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <p className="font-medium text-sm">{plugin.name}</p>
                      <Badge variant="outline" className="text-xs">v{plugin.version}</Badge>
                      <Badge variant={plugin.enabled ? "default" : "secondary"} className="text-xs">
                        {plugin.enabled ? "Enabled" : "Disabled"}
                      </Badge>
                    </div>
                    <p className="text-xs text-muted-foreground mt-1">{plugin.description}</p>
                    <p className="text-xs text-muted-foreground mt-0.5">By: {plugin.author}</p>
                    {plugin.commands && plugin.commands.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-2">
                        {plugin.commands.map(cmd => (
                          <span key={cmd} className="text-xs bg-muted px-1.5 py-0.5 rounded font-mono">/{cmd}</span>
                        ))}
                      </div>
                    )}
                  </div>
                  <button
                    onClick={() => togglePlugin(plugin)}
                    disabled={toggling === plugin._folder}
                    className={`relative inline-flex h-6 w-11 flex-shrink-0 items-center rounded-full transition-colors disabled:opacity-50 ${plugin.enabled ? "bg-primary" : "bg-muted"}`}
                  >
                    <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${plugin.enabled ? "translate-x-6" : "translate-x-1"}`} />
                  </button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}