"use client";

import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import { HelpCircle, Plus, Trash2, Save, ChevronDown, ChevronUp } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface FAQItem {
  id?: number;
  question: string;
  answer: string;
  match_keywords: string;
}

export default function FAQPage() {
  const { data: session } = useSession();
  const token = (session as any)?.accessToken as string | undefined;
  const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };

  const [faqs, setFaqs] = useState<FAQItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);
  const [newFaq, setNewFaq] = useState<FAQItem>({ question: "", answer: "", match_keywords: "general" });
  const [showAdd, setShowAdd] = useState(false);

  useEffect(() => {
    if (!token) return;
    fetch(`${API_BASE}/api/manage/faq`, { headers })
      .then(r => r.json())
      .then(d => setFaqs(d.faqs || []))
      .catch(() => setFaqs([]))
      .finally(() => setLoading(false));
  }, [token]);

  async function saveFaq(faq: FAQItem, index?: number) {
    setSaving(true);
    try {
      await fetch(`${API_BASE}/api/manage/faq`, {
        method: "POST", headers, body: JSON.stringify(faq),
      });
      const res = await fetch(`${API_BASE}/api/manage/faq`, { headers });
      const d = await res.json();
      setFaqs(d.faqs || []);
    } finally {
      setSaving(false);
    }
  }

  async function deleteFaq(id: number) {
    try {
      await fetch(`${API_BASE}/api/manage/faq/${id}`, { method: "DELETE", headers });
      setFaqs(faqs.filter(f => f.id !== id));
    } catch {}
  }

  async function addFaq() {
    if (!newFaq.question || !newFaq.answer) return;
    await saveFaq(newFaq);
    setNewFaq({ question: "", answer: "", match_keywords: "general" });
    setShowAdd(false);
  }

  const categories = Array.from(new Set(faqs.map(f => f.match_keywords)));

  if (loading) return <div className="flex items-center justify-center h-64"><p className="text-muted-foreground text-sm">Loading...</p></div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">FAQ</h1>
          <p className="text-sm text-muted-foreground mt-1">Manage frequently asked questions for your server</p>
        </div>
        <Button onClick={() => setShowAdd(!showAdd)}>
          <Plus className="h-4 w-4 mr-2" /> Add FAQ
        </Button>
      </div>

      {showAdd && (
        <Card className="border-primary/50">
          <CardHeader><CardTitle className="text-base">New FAQ Entry</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-medium text-muted-foreground mb-1 block">Question</label>
                <Input
                  placeholder="What is...?"
                  value={newFaq.question}
                  onChange={e => setNewFaq({ ...newFaq, question: e.target.value })}
                />
              </div>
              <div>
                <label className="text-xs font-medium text-muted-foreground mb-1 block">Category</label>
                <Input
                  placeholder="e.g. General, Rules, Bot"
                  value={newFaq.match_keywords}
                  onChange={e => setNewFaq({ ...newFaq, match_keywords: e.target.value })}
                />
              </div>
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground mb-1 block">Answer</label>
              <Textarea
                placeholder="The answer to this question..."
                rows={3}
                value={newFaq.answer}
                onChange={e => setNewFaq({ ...newFaq, answer: e.target.value })}
              />
            </div>
            <div className="flex gap-2">
              <Button onClick={addFaq} disabled={!newFaq.question || !newFaq.answer || saving}>
                <Save className="h-4 w-4 mr-2" /> Save
              </Button>
              <Button variant="outline" onClick={() => setShowAdd(false)}>Cancel</Button>
            </div>
          </CardContent>
        </Card>
      )}

      {faqs.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center h-48 gap-3">
            <HelpCircle className="h-8 w-8 text-muted-foreground" />
            <p className="text-muted-foreground text-sm">No FAQ entries yet.</p>
            <Button variant="outline" onClick={() => setShowAdd(true)}>
              <Plus className="h-4 w-4 mr-2" /> Add your first FAQ
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {faqs.map((faq, i) => (
            <Card key={faq.id ?? i}>
              <CardContent className="pt-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <p className="font-medium text-sm">{faq.question}</p>
                      <span className="text-xs bg-muted px-2 py-0.5 rounded-full text-muted-foreground">{faq.match_keywords}</span>
                    </div>
                    {expanded === i && (
                      <div className="mt-3 space-y-3 border-t pt-3">
                        <Textarea
                          rows={3}
                          defaultValue={faq.answer}
                          onChange={e => {
                            const updated = [...faqs];
                            updated[i] = { ...updated[i], answer: e.target.value };
                            setFaqs(updated);
                          }}
                        />
                        <Button size="sm" onClick={() => saveFaq(faq)} disabled={saving}>
                          <Save className="h-4 w-4 mr-2" /> Save
                        </Button>
                      </div>
                    )}
                    {expanded !== i && (
                      <p className="text-sm text-muted-foreground mt-1 line-clamp-2">{faq.answer}</p>
                    )}
                  </div>
                  <div className="flex items-center gap-1 flex-shrink-0">
                    <Button variant="ghost" size="sm" onClick={() => setExpanded(expanded === i ? null : i)}>
                      {expanded === i ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                    </Button>
                    {faq.id && (
                      <Button variant="ghost" size="sm" className="text-red-500" onClick={() => deleteFaq(faq.id!)}>
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}