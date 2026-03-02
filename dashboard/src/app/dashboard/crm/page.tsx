"use client";

import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import { Plus, Trash2, ChevronDown, ChevronUp, Copy, Check } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const GUILD_ID = process.env.NEXT_PUBLIC_GUILD_ID || "default";

const TAG_COLORS: Record<string, string> = {
  lead: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
  prospect: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200",
  customer: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
  churned: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
};

export default function CRMPage() {
  const { data: session, status } = useSession();
  const token = (session as any)?.accessToken as string | undefined;

  const [tab, setTab] = useState<"contacts" | "sequences" | "ai">("contacts");
  const [contacts, setContacts] = useState<any[]>([]);
  const [sequences, setSequences] = useState<any[]>([]);
  const [expandedSeq, setExpandedSeq] = useState<number | null>(null);

  const [newContact, setNewContact] = useState({ name: "", email: "", company: "", phone: "", tag: "lead", notes: "" });
  const [newSeq, setNewSeq] = useState({ name: "", description: "" });
  const [newStep, setNewStep] = useState<Record<number, { subject: string; body: string; delay_days: number }>>({});
  const [assignContact, setAssignContact] = useState("");
  const [assignSeq, setAssignSeq] = useState("");

  const [aiForm, setAiForm] = useState({ name: "", company: "", tone: "professional", prompt: "" });
  const [aiResult, setAiResult] = useState<{ subject: string; body: string } | null>(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [copied, setCopied] = useState(false);

  const headers = { "Content-Type": "application/json", Authorization: `Bearer ${token}` };

  async function loadContacts() {
    if (!token) return;
    const r = await fetch(`${API_BASE}/api/crm/contacts/${GUILD_ID}`, { headers });
    const d = await r.json();
    setContacts(d.contacts || []);
  }

  async function loadSequences() {
    if (!token) return;
    const r = await fetch(`${API_BASE}/api/crm/sequences/${GUILD_ID}`, { headers });
    const d = await r.json();
    setSequences(d.sequences || []);
  }

  useEffect(() => {
    if (status === "authenticated" && token) {
      loadContacts();
      loadSequences();
    }
  }, [status, token]);

  async function createContact() {
    if (!newContact.name || !newContact.email) return;
    await fetch(`${API_BASE}/api/crm/contacts`, {
      method: "POST", headers,
      body: JSON.stringify({ ...newContact, guild_id: GUILD_ID }),
    });
    setNewContact({ name: "", email: "", company: "", phone: "", tag: "lead", notes: "" });
    loadContacts();
  }

  async function deleteContact(id: number) {
    await fetch(`${API_BASE}/api/crm/contacts/${id}`, { method: "DELETE", headers });
    loadContacts();
  }

  async function createSequence() {
    if (!newSeq.name) return;
    await fetch(`${API_BASE}/api/crm/sequences`, {
      method: "POST", headers,
      body: JSON.stringify({ ...newSeq, guild_id: GUILD_ID }),
    });
    setNewSeq({ name: "", description: "" });
    loadSequences();
  }

  async function addStep(seqId: number) {
    const step = newStep[seqId];
    if (!step?.subject || !step?.body) return;
    await fetch(`${API_BASE}/api/crm/sequences/${seqId}/steps`, {
      method: "POST", headers,
      body: JSON.stringify(step),
    });
    setNewStep(prev => ({ ...prev, [seqId]: { subject: "", body: "", delay_days: 0 } }));
    loadSequences();
  }

  async function deleteSequence(id: number) {
    await fetch(`${API_BASE}/api/crm/sequences/${id}`, { method: "DELETE", headers });
    loadSequences();
  }

  async function assignSequence() {
    if (!assignContact || !assignSeq) return;
    await fetch(`${API_BASE}/api/crm/assign`, {
      method: "POST", headers,
      body: JSON.stringify({ contact_id: parseInt(assignContact), sequence_id: parseInt(assignSeq) }),
    });
    setAssignContact(""); setAssignSeq("");
  }

  async function generateEmail() {
    if (!aiForm.prompt) return;
    setAiLoading(true); setAiResult(null);
    try {
      const r = await fetch(`${API_BASE}/api/crm/ai-email`, {
        method: "POST", headers,
        body: JSON.stringify({ guild_id: GUILD_ID, ...aiForm }),
      });
      const d = await r.json();
      setAiResult({ subject: d.subject || "", body: d.body || "" });
    } finally { setAiLoading(false); }
  }

  async function copyEmail() {
    if (!aiResult) return;
    await navigator.clipboard.writeText(`Subject: ${aiResult.subject}\n\n${aiResult.body}`);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  if (status === "loading") return <div className="p-8 text-muted-foreground">Loading...</div>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">CRM</h1>

      <div className="flex gap-2 border-b">
        {(["contacts", "sequences", "ai"] as const).map(t => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium capitalize border-b-2 transition-colors ${
              tab === t ? "border-primary text-primary" : "border-transparent text-muted-foreground hover:text-foreground"
            }`}>
            {t === "ai" ? "AI Composer" : t}
          </button>
        ))}
      </div>

      {tab === "contacts" && (
        <div className="space-y-6">
          <Card>
            <CardHeader><CardTitle className="text-base">Add Contact</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              <div className="grid gap-3 sm:grid-cols-2">
                <Input placeholder="Name *" value={newContact.name} onChange={e => setNewContact(p => ({ ...p, name: e.target.value }))} />
                <Input placeholder="Email *" value={newContact.email} onChange={e => setNewContact(p => ({ ...p, email: e.target.value }))} />
                <Input placeholder="Company" value={newContact.company} onChange={e => setNewContact(p => ({ ...p, company: e.target.value }))} />
                <Input placeholder="Phone" value={newContact.phone} onChange={e => setNewContact(p => ({ ...p, phone: e.target.value }))} />
              </div>
              <div className="flex gap-3 flex-wrap">
                <select value={newContact.tag} onChange={e => setNewContact(p => ({ ...p, tag: e.target.value }))}
                  className="flex h-9 rounded-md border border-input bg-background px-3 py-1 text-sm">
                  {["lead", "prospect", "customer", "churned"].map(t => <option key={t} value={t}>{t}</option>)}
                </select>
                <Input className="flex-1" placeholder="Notes" value={newContact.notes} onChange={e => setNewContact(p => ({ ...p, notes: e.target.value }))} />
              </div>
              <Button onClick={createContact} size="sm"><Plus className="h-4 w-4 mr-2" />Add Contact</Button>
            </CardContent>
          </Card>

          {contacts.length > 0 && sequences.length > 0 && (
            <Card>
              <CardHeader><CardTitle className="text-base">Assign Sequence</CardTitle></CardHeader>
              <CardContent className="flex flex-wrap gap-3">
                <select value={assignContact} onChange={e => setAssignContact(e.target.value)}
                  className="flex h-9 rounded-md border border-input bg-background px-3 py-1 text-sm">
                  <option value="">Select contact</option>
                  {contacts.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                </select>
                <select value={assignSeq} onChange={e => setAssignSeq(e.target.value)}
                  className="flex h-9 rounded-md border border-input bg-background px-3 py-1 text-sm">
                  <option value="">Select sequence</option>
                  {sequences.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
                </select>
                <Button onClick={assignSequence} size="sm">Assign</Button>
              </CardContent>
            </Card>
          )}

          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {contacts.map(c => (
              <Card key={c.id}>
                <CardContent className="pt-4 space-y-2">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="font-medium truncate">{c.name}</p>
                      <p className="text-xs text-muted-foreground truncate">{c.email}</p>
                      {c.company && <p className="text-xs text-muted-foreground truncate">{c.company}</p>}
                    </div>
                    <div className="flex items-center gap-1 shrink-0">
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${TAG_COLORS[c.tag] || ""}`}>{c.tag}</span>
                      <button onClick={() => deleteContact(c.id)} className="text-muted-foreground hover:text-red-500 transition-colors">
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </div>
                  {c.notes && <p className="text-xs text-muted-foreground line-clamp-2">{c.notes}</p>}
                </CardContent>
              </Card>
            ))}
          </div>

          {contacts.length === 0 && (
            <div className="flex items-center justify-center h-32">
              <p className="text-muted-foreground text-sm">No contacts yet. Add one above.</p>
            </div>
          )}
        </div>
      )}

      {tab === "sequences" && (
        <div className="space-y-6">
          <Card>
            <CardHeader><CardTitle className="text-base">Create Sequence</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              <div className="grid gap-3 sm:grid-cols-2">
                <Input placeholder="Sequence name *" value={newSeq.name} onChange={e => setNewSeq(p => ({ ...p, name: e.target.value }))} />
                <Input placeholder="Description" value={newSeq.description} onChange={e => setNewSeq(p => ({ ...p, description: e.target.value }))} />
              </div>
              <Button onClick={createSequence} size="sm"><Plus className="h-4 w-4 mr-2" />Create Sequence</Button>
            </CardContent>
          </Card>

          <div className="space-y-3">
            {sequences.map(seq => (
              <Card key={seq.id}>
                <CardContent className="pt-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-medium">{seq.name}</p>
                      {seq.description && <p className="text-xs text-muted-foreground">{seq.description}</p>}
                      <p className="text-xs text-muted-foreground mt-0.5">{seq.steps?.length || 0} steps</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <button onClick={() => setExpandedSeq(expandedSeq === seq.id ? null : seq.id)} className="text-muted-foreground hover:text-foreground">
                        {expandedSeq === seq.id ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                      </button>
                      <button onClick={() => deleteSequence(seq.id)} className="text-muted-foreground hover:text-red-500">
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </div>

                  {expandedSeq === seq.id && (
                    <div className="space-y-3 border-t pt-3">
                      {seq.steps?.map((step: any, i: number) => (
                        <div key={step.id} className="rounded-md border p-3 text-sm space-y-1">
                          <p className="font-medium">Step {i + 1} — Day {step.delay_days}</p>
                          <p className="text-muted-foreground">Subject: {step.subject}</p>
                          <p className="text-xs text-muted-foreground line-clamp-2">{step.body}</p>
                        </div>
                      ))}
                      <div className="space-y-2 border-t pt-3">
                        <p className="text-xs font-medium text-muted-foreground">Add Step</p>
                        <Input placeholder="Subject"
                          value={newStep[seq.id]?.subject || ""}
                          onChange={e => setNewStep(p => ({ ...p, [seq.id]: { ...p[seq.id], subject: e.target.value } }))} />
                        <Textarea placeholder="Body (use {{name}}, {{company}})" rows={3}
                          value={newStep[seq.id]?.body || ""}
                          onChange={e => setNewStep(p => ({ ...p, [seq.id]: { ...p[seq.id], body: e.target.value } }))} />
                        <div className="flex items-center gap-3">
                          <Input type="number" placeholder="Delay days" className="w-32"
                            value={newStep[seq.id]?.delay_days || 0}
                            onChange={e => setNewStep(p => ({ ...p, [seq.id]: { ...p[seq.id], delay_days: parseInt(e.target.value) || 0 } }))} />
                          <Button onClick={() => addStep(seq.id)} size="sm"><Plus className="h-4 w-4 mr-1" />Add Step</Button>
                        </div>
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>
            ))}
            {sequences.length === 0 && (
              <div className="flex items-center justify-center h-32">
                <p className="text-muted-foreground text-sm">No sequences yet. Create one above.</p>
              </div>
            )}
          </div>
        </div>
      )}

      {tab === "ai" && (
        <div className="space-y-6 max-w-2xl">
          <Card>
            <CardHeader><CardTitle className="text-base">Generate Email with AI</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              <div className="grid gap-3 sm:grid-cols-2">
                <Input placeholder="Contact name (optional)" value={aiForm.name} onChange={e => setAiForm(p => ({ ...p, name: e.target.value }))} />
                <Input placeholder="Company (optional)" value={aiForm.company} onChange={e => setAiForm(p => ({ ...p, company: e.target.value }))} />
              </div>
              <select value={aiForm.tone} onChange={e => setAiForm(p => ({ ...p, tone: e.target.value }))}
                className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm">
                {["professional", "friendly", "urgent", "casual", "formal"].map(t => (
                  <option key={t} value={t}>{t.charAt(0).toUpperCase() + t.slice(1)}</option>
                ))}
              </select>
              <Textarea placeholder="Describe the email you want to write..." rows={4}
                value={aiForm.prompt} onChange={e => setAiForm(p => ({ ...p, prompt: e.target.value }))} />
              <Button onClick={generateEmail} disabled={aiLoading || !aiForm.prompt}>
                {aiLoading ? "Generating..." : "Generate Email"}
              </Button>
            </CardContent>
          </Card>

          {aiResult && (
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base">Generated Email</CardTitle>
                  <Button variant="outline" size="sm" onClick={copyEmail}>
                    {copied ? <Check className="h-4 w-4 mr-1" /> : <Copy className="h-4 w-4 mr-1" />}
                    {copied ? "Copied!" : "Copy"}
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="space-y-3">
                <div>
                  <p className="text-xs font-medium text-muted-foreground mb-1">Subject</p>
                  <Input value={aiResult.subject} onChange={e => setAiResult(p => p ? { ...p, subject: e.target.value } : p)} />
                </div>
                <div>
                  <p className="text-xs font-medium text-muted-foreground mb-1">Body</p>
                  <Textarea rows={10} value={aiResult.body} onChange={e => setAiResult(p => p ? { ...p, body: e.target.value } : p)} />
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}