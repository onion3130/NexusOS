"use client";

import { useEffect, useState } from "react";
import { CommandPalette } from "./command-palette";
import { ThemeToggle } from "./theme-toggle";
import { useTheme } from "./theme-provider";
import { AssistantWorkspace } from "./assistant-workspace";
import { SystemOverview } from "./system-overview";
import { TaskWorkspace } from "./task-workspace";
import { NotificationCenter } from "./notification-center";
import { LockedState, StatusCard } from "./ui/status-card";
import type { User } from "../lib/auth";

const navigation = [
  { label: "Overview", icon: "◈", available: true },
  { label: "Assistant", icon: "✦", available: true },
  { label: "Tasks", icon: "□", available: true },
  { label: "Notes", icon: "▤", available: false },
];

const metrics = [
  { label: "System status", value: "Foundation ready", detail: "Health endpoints online", tone: "green" },
  { label: "AI provider", value: "Disabled", detail: "Enable in a future milestone", tone: "purple" },
  { label: "Storage", value: "SQLite ready", detail: "Identity persistence online", tone: "blue" },
];

export function DashboardShell({ user, onLogout }: { user: User; onLogout: () => void }) {
  const { toggleTheme } = useTheme();
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [activeView, setActiveView] = useState<"overview" | "assistant" | "tasks">("overview");

  useEffect(() => {
    function handleShortcut(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setPaletteOpen((open) => !open);
      }
      if (event.key === "Escape") {
        setPaletteOpen(false);
        setMobileNavOpen(false);
      }
    }
    window.addEventListener("keydown", handleShortcut);
    return () => window.removeEventListener("keydown", handleShortcut);
  }, []);

  function signOut() {
    setPaletteOpen(false);
    onLogout();
  }

  return (
    <main className="shell">
      <a className="skip-link" href="#main-content">Skip to main content</a>
      <aside aria-label="Workspace navigation" className={`sidebar${mobileNavOpen ? " mobile-open" : ""}`} id="mobile-navigation">
        <div className="brand">
          <div className="brand-mark">N</div>
          <div><strong>NexusOS</strong><span>Personal command center</span></div>
        </div>
        <nav aria-label="Primary navigation" className="nav-list">
          <p className="eyebrow">Workspace</p>
          {navigation.map((item) => item.available ? (
            <button aria-current={(item.label === "Overview" && activeView === "overview") || (item.label === "Assistant" && activeView === "assistant") || (item.label === "Tasks" && activeView === "tasks") ? "page" : undefined} className={`nav-item${((item.label === "Overview" && activeView === "overview") || (item.label === "Assistant" && activeView === "assistant") || (item.label === "Tasks" && activeView === "tasks")) ? " active" : ""}`} key={item.label} onClick={() => { setActiveView(item.label === "Assistant" ? "assistant" : item.label === "Tasks" ? "tasks" : "overview"); setMobileNavOpen(false); }} type="button">
              <span aria-hidden="true" className="nav-icon">{item.icon}</span>{item.label}{((item.label === "Overview" && activeView === "overview") || (item.label === "Assistant" && activeView === "assistant") || (item.label === "Tasks" && activeView === "tasks")) && <span className="active-dot" />}
            </button>
          ) : (
            <button aria-disabled="true" className="nav-item nav-item-locked" key={item.label} type="button">
              <span aria-hidden="true" className="nav-icon">{item.icon}</span>{item.label}<span aria-hidden="true" className="nav-lock">⌁</span>
            </button>
          ))}
        </nav>
        <div className="sidebar-footer">
          <div className="connection-dot" />
          <div><strong>Local mode</strong><span>Private by default</span></div>
        </div>
      </aside>

      <section className="content" id="main-content">
        <header className="topbar">
          <div className="mobile-topbar-row">
            <button aria-controls="mobile-navigation" aria-expanded={mobileNavOpen} aria-label="Toggle navigation" className="menu-button" onClick={() => setMobileNavOpen((open) => !open)} type="button">☰</button>
            <div><p className="breadcrumb">Workspace / {activeView === "assistant" ? "Assistant" : activeView === "tasks" ? "Tasks" : "Overview"}</p><h1>{activeView === "assistant" ? "Your assistant workspace." : activeView === "tasks" ? "Make progress visible." : `Good morning, ${user.username}.`}</h1></div>
          </div>
          <div className="topbar-actions">
            <NotificationCenter />
            <button aria-label="Open command palette" className="shortcut-button" onClick={() => setPaletteOpen(true)} type="button"><span>⌘ K</span><span className="shortcut-label">Commands</span></button>
            <ThemeToggle />
            <button aria-label="Sign out" className="avatar" onClick={signOut} type="button">↪</button>
          </div>
        </header>

        {activeView === "assistant" ? <AssistantWorkspace /> : activeView === "tasks" ? <TaskWorkspace /> : <>
        <div className="hero-card">
          <div className="hero-copy">
            <span className="status-pill"><span /> Milestone 6 tasks online</span>
            <h2>Your digital life, <em>connected.</em></h2>
            <p>Your private workspace is authenticated and ready for the next Nexus modules. The shell keeps unfinished capabilities visible without pretending they are live.</p>
            <button className="primary-button" onClick={() => setPaletteOpen(true)} type="button">Explore commands <span aria-hidden="true">⌘ K</span></button>
          </div>
          <div aria-hidden="true" className="hero-orbit"><div className="orbit orbit-one"><span>AI</span></div><div className="orbit orbit-two"><span>SYS</span></div><div className="orbit orbit-three"><span>✦</span></div><div className="core">N</div></div>
        </div>

        <section aria-labelledby="status-heading" className="section-block">
          <div className="section-heading"><div><p className="eyebrow">At a glance</p><h2 id="status-heading">System status</h2></div><span className="updated">Authenticated locally</span></div>
          <div className="metric-grid">{metrics.map((metric) => <article className="metric-card" key={metric.label}><div className={`metric-indicator ${metric.tone}`} /><p>{metric.label}</p><strong>{metric.value}</strong><span>{metric.detail}</span></article>)}</div>
        </section>

        <SystemOverview />

        <section aria-labelledby="next-heading" className="section-block">
          <div className="section-heading"><div><p className="eyebrow">Workspace status</p><h2 id="next-heading">Build your personal workspace</h2></div><span className="updated">No feature data loaded</span></div>
          <StatusCard action={<span className="lock-label">Milestone 5 live</span>} description="The assistant gateway is available with owned conversations, bounded provider calls, and read-only system tools." eyebrow="Now available" icon="✦" title="Your assistant is ready" />
        </section>

        <section aria-label="Unavailable workspace modules" className="locked-grid">
          <LockedState description="Notes and scoped search arrive in Milestone 7." title="Notes" />
        </section>

        </>}
        <footer>Local-first. Private by default. <span>NexusOS 0.1.0</span></footer>
      </section>
      {paletteOpen && <CommandPalette onClose={() => setPaletteOpen(false)} onLogout={signOut} onToggleTheme={() => { toggleTheme(); setPaletteOpen(false); }} />}
    </main>
  );
}
