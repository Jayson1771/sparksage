const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface FetchOptions extends RequestInit {
  token?: string;
}

async function apiFetch<T>(path: string, options: FetchOptions = {}): Promise<T> {
  const { token, headers: customHeaders, ...rest } = options;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...((customHeaders as Record<string, string>) || {}),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_URL}${path}`, {
    headers,
    ...rest,
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail || `API error: ${res.status}`);
  }

  return res.json();
}

// Response types matching backend
export interface ProviderItem {
  name: string;
  display_name: string;
  model: string;
  free: boolean;
  configured: boolean;
  is_primary: boolean;
}

export interface ProvidersResponse {
  providers: ProviderItem[];
  fallback_order: string[];
}

export interface ChannelItem {
  channel_id: string;
  message_count: number;
  last_active: string;
}

export interface MessageItem {
  role: string;
  content: string;
  provider: string | null;
  created_at: string;
}

export interface GuildItem {
  id: string;
  name: string;
  member_count: number;
}

export interface BotStatus {
  online: boolean;
  latency_ms: number | null;
  latency: number | null;
  guild_count: number;
  guilds: GuildItem[];
  uptime: number | null;
  username: string | null;
}

export interface TestProviderResult {
  success: boolean;
  message: string;
  latency_ms?: number;
}

export const api = {
  // Auth
  login: (password: string) =>
    apiFetch<{ access_token: string; token_type: string }>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ password }),
    }),

  me: (token: string) =>
    apiFetch<{ username: string; role: string }>("/api/auth/me", { token }),

  // Config
  getConfig: (token: string) =>
    apiFetch<{ config: Record<string, string> }>("/api/config", { token }),

  updateConfig: (token: string, values: Record<string, string>) =>
    apiFetch<{ status: string }>("/api/config", {
      method: "PUT",
      body: JSON.stringify({ values }),
      token,
    }),

  // Providers
  getProviders: (token: string) =>
    apiFetch<ProvidersResponse>("/api/providers", { token }),

  testProvider: (token: string, provider: string) =>
    apiFetch<TestProviderResult>("/api/providers/test", {
      method: "POST",
      body: JSON.stringify({ provider }),
      token,
    }),

  setPrimaryProvider: (token: string, provider: string) =>
    apiFetch<{ status: string; primary: string }>("/api/providers/primary", {
      method: "PUT",
      body: JSON.stringify({ provider }),
      token,
    }),

  // Bot
  getBotStatus: (token: string) =>
    apiFetch<BotStatus>("/api/bot/status", { token }),

  // Conversations
  getConversations: (token: string) =>
    apiFetch<{ channels: ChannelItem[] }>("/api/conversations", { token }),

  getConversation: (token: string, channelId: string) =>
    apiFetch<{ channel_id: string; messages: MessageItem[] }>(
      `/api/conversations/${channelId}`,
      { token }
    ),

  deleteConversation: (token: string, channelId: string) =>
    apiFetch<{ status: string }>(`/api/conversations/${channelId}`, {
      method: "DELETE",
      token,
    }),

  // Wizard
  getWizardStatus: (token: string) =>
    apiFetch<{ completed: boolean; current_step: number }>("/api/wizard/status", { token }),

  completeWizard: (token: string, data: Record<string, string>) =>
    apiFetch<{ status: string }>("/api/wizard/complete", {
      method: "POST",
      body: JSON.stringify({ config: data }),
      token,
    }),
};
