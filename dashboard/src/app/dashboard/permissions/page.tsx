"use client";

import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import { Shield, Save, Plus, Trash2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const COMMON_COMMANDS = ["ask", "review", "summarize", "translate", "faq", "onboarding", "moderation", "prompt", "digest", "plugin"];

export default function PermissionsPage() {
  const { data: session } = useSession();
  const token = (session as any)?.accessToken as string | undefined;
  const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };

  const [config, setConfig] = useState<{
    command_permissions: Record<string, string[]>;
    blocked_users: string[];
    admin_roles: string[];
  }>({ command_permissions: {}, blocked_users: [], admin_roles: [] });

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [newCmd, setNewCmd] = useState("");
  const [newRoles, setNewRoles] = useState<Record<string, string>>({});
  const [newBlockedUser, setNewBlockedUser] = useState("");
  const [newAdminRole, setNewAdminRole] = useState("");

  useEffect(() => {
    if (!token) return;
    fetch(`${API_BASE}/api/manage/permissions`, { headers })
      .then(r => r.json())
      .then(d => { if (d && !d.detail) setConfig(c => ({ ...c, ...d })); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [token]);

  async function save() {
    setSaving(true);
    try {
      const res = await fetch(`${API_BASE}/api/manage/permissions`, {
        method: "POST", headers, body: JSON.stringify(config),
      });
      const data = await res.json();
      if (data.status === "ok") { setSaved(true); setTimeout(() => setSaved(false), 2000); }
    } finally { setSaving(false); }
  }

  function addCommand() {
    const cmd = newCmd.trim().replace("/", "");
    if (!cmd || config.command_permissions[cmd] !== undefined) return;
    setConfig(c => ({ ...c, command_permissions: { ...c.command_permissions, [cmd]: [] } }));
    setNewCmd("");
  }

  function removeCommand(cmd: string) {
    const updated = { ...config.command_permissions };
    delete updated[cmd];
    setConfig(c => ({ ...c, command_permissions: updated }));
  }

  function addRoleToCommand(cmd: string) {
    const roleId = (newRoles[cmd] || "").trim();
    if (!roleId) return;
    setConfig(c => ({
      ...c,
      command_permissions: { ...c.command_permissions, [cmd]: [...(c.command_permissions[cmd] || []), roleId] },
    }));
    setNewRoles(r => ({ ...r, [cmd]: "" }));
  }

  if (loading) return <div className="flex items-center justify-center h-64"><p className="text-muted-foreground text-sm">Loading...</p></div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Permissions</h1>
          <p className="text-sm text-muted-foreground mt-1">Restrict bot commands to specific roles</p>
        </div>
        <Button onClick={save} disabled={saving}>
          <Save className="h-4 w-4 mr-2" />
          {saving ? "Saving..." : saved ? "✓ Saved!" : "Save Changes"}
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Command Restrictions</CardTitle>
          <p className="text-xs text-muted-foreground">Commands not listed here are usable by everyone</p>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex gap-2">
            <Input
              placeholder="Command name e.g. ask, review"
              value={newCmd}
              onChange={e => setNewCmd(e.target.value)}
              onKeyDown={e => e.key === "Enter" && addCommand()}
            />
            <Button variant="outline" onClick={addCommand}><Plus className="h-4 w-4" /></Button>
          </div>

          {/* Quick-add buttons */}
          <div className="flex flex-wrap gap-2">
            {COMMON_COMMANDS.filter(c => config.command_permissions[c] === undefined).map(cmd => (
              <button key={cmd}
                onClick={() => setConfig(c => ({ ...c, command_permissions: { ...c.command_permissions, [cmd]: [] } }))}
                className="text-xs px-2 py-1 rounded-md border border-dashed text-muted-foreground hover:border-primary hover:text-primary transition-colors">
                + /{cmd}
              </button>
            ))}
          </div>

          {Object.keys(config.command_permissions).length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-4">No restrictions — all commands open to everyone.</p>
          ) : (
            <div className="space-y-3">
              {Object.entries(config.command_permissions).map(([cmd, roles]) => (
                <div key={cmd} className="border rounded-lg p-3 space-y-2">
                  <div className="flex items-center justify-between">
                    <p className="font-medium text-sm">/{cmd}</p>
                    <Button variant="ghost" size="sm" className="text-red-500 h-7" onClick={() => removeCommand(cmd)}>
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {roles.length === 0
                      ? <span className="text-xs text-muted-foreground italic">Add a role ID to restrict this command</span>
                      : roles.map(role => (
                        <Badge key={role} variant="secondary" className="gap-1 text-xs">
                          {role}
                          <button onClick={() => setConfig(c => ({ ...c, command_permissions: { ...c.command_permissions, [cmd]: roles.filter(r => r !== role) } }))} className="ml-1 hover:text-red-500">×</button>
                        </Badge>
                      ))
                    }
                  </div>
                  <div className="flex gap-2">
                    <Input placeholder="Role ID" className="h-7 text-xs"
                      value={newRoles[cmd] || ""}
                      onChange={e => setNewRoles(r => ({ ...r, [cmd]: e.target.value }))}
                      onKeyDown={e => e.key === "Enter" && addRoleToCommand(cmd)} />
                    <Button variant="outline" size="sm" className="h-7" onClick={() => addRoleToCommand(cmd)}>
                      <Plus className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle className="text-base">Admin Roles</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <p className="text-xs text-muted-foreground">Role IDs that bypass all command restrictions</p>
          <div className="flex gap-2">
            <Input placeholder="Role ID" value={newAdminRole} onChange={e => setNewAdminRole(e.target.value)}
              onKeyDown={e => { if (e.key === "Enter" && newAdminRole) { setConfig(c => ({ ...c, admin_roles: [...c.admin_roles, newAdminRole] })); setNewAdminRole(""); }}} />
            <Button variant="outline" onClick={() => { if (newAdminRole) { setConfig(c => ({ ...c, admin_roles: [...c.admin_roles, newAdminRole] })); setNewAdminRole(""); }}}>
              <Plus className="h-4 w-4" />
            </Button>
          </div>
          <div className="flex flex-wrap gap-2">
            {config.admin_roles.length === 0
              ? <p className="text-xs text-muted-foreground">No admin roles set.</p>
              : config.admin_roles.map((r, i) => (
                <Badge key={i} variant="secondary" className="gap-1">{r}
                  <button onClick={() => setConfig(c => ({ ...c, admin_roles: c.admin_roles.filter((_, idx) => idx !== i) }))}>×</button>
                </Badge>
              ))}
          </div>
        </CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle className="text-base">Discord Commands</CardTitle></CardHeader>
        <CardContent className="space-y-1.5">
          {[
            ["/permissions set ask @Role", "Restrict /ask to a role"],
            ["/permissions remove ask @Role", "Remove role restriction"],
            ["/permissions clear ask", "Remove all restrictions from a command"],
            ["/permissions list", "View all restrictions"],
            ["/permissions check ask", "Check who can use a command"],
          ].map(([cmd, desc]) => (
            <div key={cmd} className="flex items-center gap-3">
              <code className="bg-muted px-1.5 py-0.5 rounded text-xs font-mono text-foreground">{cmd}</code>
              <span className="text-xs text-muted-foreground">{desc}</span>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}