"use client";

import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import { BookOpen, Save, Plus, Trash2, GripVertical } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function OnboardingPage() {
  const { data: session } = useSession();
  const token = (session as any)?.accessToken as string | undefined;
  const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };

  const [config, setConfig] = useState({
    enabled: true,
    welcome_channel_id: "",
    welcome_message: "Welcome to the server, {user}! 🎉",
    dm_enabled: false,
    dm_message: "Thanks for joining! Here's what you need to know...",
    roles_to_assign: [] as string[],
    steps: [] as { title: string; description: string }[],
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [newRole, setNewRole] = useState("");

  useEffect(() => {
    if (!token) return;
    fetch(`${API_BASE}/api/manage/onboarding`, { headers })
      .then(r => r.json())
      .then(d => { if (d) setConfig(c => ({ ...c, ...d })); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [token]);

  async function save() {
    setSaving(true);
    try {
      await fetch(`${API_BASE}/api/manage/onboarding`, {
        method: "POST", headers, body: JSON.stringify(config),
      });
    } finally {
      setSaving(false);
    }
  }

  function addStep() {
    setConfig(c => ({ ...c, steps: [...c.steps, { title: "", description: "" }] }));
  }

  function removeStep(i: number) {
    setConfig(c => ({ ...c, steps: c.steps.filter((_, idx) => idx !== i) }));
  }

  function addRole() {
    if (!newRole.trim()) return;
    setConfig(c => ({ ...c, roles_to_assign: [...c.roles_to_assign, newRole.trim()] }));
    setNewRole("");
  }

  if (loading) return <div className="flex items-center justify-center h-64"><p className="text-muted-foreground text-sm">Loading...</p></div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Onboarding</h1>
          <p className="text-sm text-muted-foreground mt-1">Configure new member welcome experience</p>
        </div>
        <Button onClick={save} disabled={saving}>
          <Save className="h-4 w-4 mr-2" />
          {saving ? "Saving..." : "Save Changes"}
        </Button>
      </div>

      {/* Enable/Disable */}
      <Card>
        <CardHeader><CardTitle className="text-base">General Settings</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium">Enable Onboarding</p>
              <p className="text-xs text-muted-foreground">Automatically greet new members</p>
            </div>
            <button
              onClick={() => setConfig(c => ({ ...c, enabled: !c.enabled }))}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${config.enabled ? "bg-primary" : "bg-muted"}`}
            >
              <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${config.enabled ? "translate-x-6" : "translate-x-1"}`} />
            </button>
          </div>
          <div>
            <label className="text-xs font-medium text-muted-foreground mb-1 block">Welcome Channel ID</label>
            <Input
              placeholder="Channel ID where welcome messages are sent"
              value={config.welcome_channel_id}
              onChange={e => setConfig(c => ({ ...c, welcome_channel_id: e.target.value }))}
            />
          </div>
          <div>
            <label className="text-xs font-medium text-muted-foreground mb-1 block">Welcome Message</label>
            <Textarea
              rows={3}
              placeholder="Use {user} for mention, {server} for server name"
              value={config.welcome_message}
              onChange={e => setConfig(c => ({ ...c, welcome_message: e.target.value }))}
            />
            <p className="text-xs text-muted-foreground mt-1">Variables: {"{user}"}, {"{server}"}, {"{member_count}"}</p>
          </div>
        </CardContent>
      </Card>

      {/* DM Settings */}
      <Card>
        <CardHeader><CardTitle className="text-base">Direct Message</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium">Send Welcome DM</p>
              <p className="text-xs text-muted-foreground">Send a DM to new members on join</p>
            </div>
            <button
              onClick={() => setConfig(c => ({ ...c, dm_enabled: !c.dm_enabled }))}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${config.dm_enabled ? "bg-primary" : "bg-muted"}`}
            >
              <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${config.dm_enabled ? "translate-x-6" : "translate-x-1"}`} />
            </button>
          </div>
          {config.dm_enabled && (
            <div>
              <label className="text-xs font-medium text-muted-foreground mb-1 block">DM Message</label>
              <Textarea
                rows={4}
                value={config.dm_message}
                onChange={e => setConfig(c => ({ ...c, dm_message: e.target.value }))}
              />
            </div>
          )}
        </CardContent>
      </Card>

      {/* Auto Roles */}
      <Card>
        <CardHeader><CardTitle className="text-base">Auto-Assign Roles</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <div className="flex gap-2">
            <Input
              placeholder="Role ID to assign on join"
              value={newRole}
              onChange={e => setNewRole(e.target.value)}
              onKeyDown={e => e.key === "Enter" && addRole()}
            />
            <Button onClick={addRole} variant="outline"><Plus className="h-4 w-4" /></Button>
          </div>
          <div className="flex flex-wrap gap-2">
            {config.roles_to_assign.map((role, i) => (
              <div key={i} className="flex items-center gap-1 bg-muted px-2 py-1 rounded-md text-sm">
                <span>{role}</span>
                <button onClick={() => setConfig(c => ({ ...c, roles_to_assign: c.roles_to_assign.filter((_, idx) => idx !== i) }))}>
                  <Trash2 className="h-3 w-3 text-muted-foreground hover:text-red-500" />
                </button>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Onboarding Steps */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-base">Onboarding Steps</CardTitle>
          <Button variant="outline" size="sm" onClick={addStep}>
            <Plus className="h-4 w-4 mr-2" /> Add Step
          </Button>
        </CardHeader>
        <CardContent className="space-y-3">
          {config.steps.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-4">No steps configured. Add steps to guide new members.</p>
          ) : (
            config.steps.map((step, i) => (
              <div key={i} className="flex gap-3 items-start border rounded-lg p-3">
                <GripVertical className="h-4 w-4 text-muted-foreground mt-2 flex-shrink-0" />
                <div className="flex-1 space-y-2">
                  <Input
                    placeholder={`Step ${i + 1} title`}
                    value={step.title}
                    onChange={e => {
                      const steps = [...config.steps];
                      steps[i] = { ...steps[i], title: e.target.value };
                      setConfig(c => ({ ...c, steps }));
                    }}
                  />
                  <Textarea
                    placeholder="Step description..."
                    rows={2}
                    value={step.description}
                    onChange={e => {
                      const steps = [...config.steps];
                      steps[i] = { ...steps[i], description: e.target.value };
                      setConfig(c => ({ ...c, steps }));
                    }}
                  />
                </div>
                <Button variant="ghost" size="sm" className="text-red-500" onClick={() => removeStep(i)}>
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            ))
          )}
        </CardContent>
      </Card>
    </div>
  );
}