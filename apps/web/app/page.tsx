"use client";

import { useCallback, useEffect, useState } from "react";
import { ConnectionError, LoadingScreen, LoginScreen } from "../components/auth-screen";
import { DashboardShell } from "../components/dashboard-shell";
import { ThemeProvider } from "../components/theme-provider";
import { logout, readCurrentUser } from "../lib/auth";
import type { User } from "../lib/auth";

function Workspace() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [connectionError, setConnectionError] = useState(false);

  const loadSession = useCallback(async () => {
    setLoading(true);
    setConnectionError(false);
    try {
      setUser(await readCurrentUser());
    } catch {
      setConnectionError(true);
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadSession();
  }, [loadSession]);

  async function handleLogout() {
    try {
      await logout();
    } finally {
      setUser(null);
    }
  }

  if (loading) return <LoadingScreen />;
  if (connectionError) return <ConnectionError onRetry={() => void loadSession()} />;
  if (!user) return <LoginScreen onLogin={setUser} />;
  return <DashboardShell onLogout={() => void handleLogout()} user={user} />;
}

export default function Home() {
  return (
    <ThemeProvider>
      <Workspace />
    </ThemeProvider>
  );
}
