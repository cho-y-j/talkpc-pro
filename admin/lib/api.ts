// 어드민 서버 API 클라이언트 (브라우저 fetch)
//
// 토큰은 localStorage 에 보관 (어드민 화면 = 신뢰된 브라우저 전제).

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8001";
const TOKEN_KEY = "talkpc_admin_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown
): Promise<T> {
  const token = getToken();
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const j = await res.json();
      detail = j.detail || JSON.stringify(j);
    } catch {}
    throw new ApiError(res.status, detail);
  }
  return res.status === 204 ? (undefined as T) : await res.json();
}

// ── 타입 ──

export type UserRow = {
  id: string;
  email: string;
  license_key: string;
  status: "pending" | "active" | "expired" | "suspended" | "rejected";
  is_admin: boolean;
  expires_at: string | null;
  admin_note: string;
  last_login_at: string | null;
  status_changed_at: string;
  created_at: string;
  device_count: number;
  send_count_30d: number;
  device_limit: number | null;
  effective_device_limit: number;
};

export type UsersListResponse = {
  total: number;
  pending: number;
  active: number;
  expired: number;
  suspended: number;
  rejected: number;
  users: UserRow[];
};

export type StatsResponse = {
  total_users: number;
  active_users: number;
  pending_users: number;
  daily_sends: { date: string; count: number }[];
  top_users: { email: string; count: number }[];
  daily_signups: { date: string; count: number }[];
};

export type AuthResponse = {
  access_token: string | null;
  license_key: string;
  user_id: string;
  status: string;
  status_message: string;
  expires_at: string | null;
};

// ── API ──

export const api = {
  login: (email: string, password: string) =>
    request<AuthResponse>("POST", "/auth/login", {
      email,
      password,
      hwid: "admin-browser",
      hostname: "admin-web",
    }),

  listUsers: (params?: { status?: string; q?: string; limit?: number; offset?: number }) => {
    const qs = new URLSearchParams();
    if (params?.status) qs.set("status", params.status);
    if (params?.q) qs.set("q", params.q);
    if (params?.limit) qs.set("limit", String(params.limit));
    if (params?.offset) qs.set("offset", String(params.offset));
    const q = qs.toString();
    return request<UsersListResponse>("GET", `/admin/users${q ? "?" + q : ""}`);
  },

  changeUserStatus: (userId: string, status: string, note = "", expires_at: string | null = null) =>
    request<{ ok: boolean; status: string }>("PATCH", `/admin/users/${userId}/status`, {
      status,
      note,
      expires_at,
    }),

  deleteUser: (userId: string) =>
    request<{ ok: boolean }>("DELETE", `/admin/users/${userId}`),

  changeUserPassword: (userId: string, password: string) =>
    request<{ ok: boolean }>("PATCH", `/admin/users/${userId}/password`, {
      password,
    }),

  setDeviceLimit: (userId: string, limit: number | null) =>
    request<{ ok: boolean; device_limit: number | null; effective: number }>(
      "PATCH",
      `/admin/users/${userId}/device-limit`,
      { limit }
    ),

  getStats: (days = 30) =>
    request<StatsResponse>("GET", `/admin/stats?days=${days}`),

  // ── 부정 사용 탐지 ──

  detectAbuse: (days = 1, threshold = 100) =>
    request<AbuseRow[]>("GET", `/logs/admin/abuse?days=${days}&threshold=${threshold}`),
};

export type AbuseRow = {
  user_id: string;
  email: string;
  status: string;
  count: number;
  period_days: number;
};
