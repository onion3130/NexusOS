export type User = {
  id: string;
  username: string;
  roles: string[];
  permissions: string[];
  is_active: boolean;
  created_at: string;
};

type AuthResponse = {
  user: User;
  expires_at: string;
};

const API_ROOT = "/api/v1";

function csrfHeader(): Record<string, string> {
  const prefix = "nexus_csrf=";
  const cookie = document.cookie
    .split(";")
    .map((part) => part.trim())
    .find((part) => part.startsWith(prefix));
  if (!cookie) return {};
  const token = decodeURIComponent(cookie.slice(prefix.length));
  return token ? { "X-CSRF-Token": token } : {};
}

async function parseResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    throw new Error(`NexusOS request failed with ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export async function readCurrentUser(): Promise<User | null> {
  let response = await fetch(`${API_ROOT}/auth/me`, { credentials: "include" });
  if (response.status === 401) {
    const refreshed = await fetch(`${API_ROOT}/auth/refresh`, {
      method: "POST",
      credentials: "include",
      headers: csrfHeader(),
    });
    if (refreshed.ok) {
      response = await fetch(`${API_ROOT}/auth/me`, { credentials: "include" });
    }
  }
  if (response.status === 401) return null;
  return parseResponse<User>(response);
}

export async function login(username: string, password: string): Promise<User> {
  const response = await fetch(`${API_ROOT}/auth/login`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  const body = await parseResponse<AuthResponse>(response);
  return body.user;
}

export async function logout(): Promise<void> {
  const response = await fetch(`${API_ROOT}/auth/logout`, {
    method: "POST",
    credentials: "include",
    headers: csrfHeader(),
  });
  if (!response.ok && response.status !== 401) {
    throw new Error(`NexusOS logout failed with ${response.status}`);
  }
}
