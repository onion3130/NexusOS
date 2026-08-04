"use client";

import { useEffect, useState } from "react";
import { CommandPalette } from "./command-palette";
import { ThemeToggle } from "./theme-toggle";
import { useTheme } from "./theme-provider";
import { AssistantWorkspace } from "./assistant-workspace";
import { SystemOverview } from "./system-overview";
import { TaskWorkspace } from "./task-workspace";
import { NotificationCenter } from "./notification-center";
import { NotesWorkspace } from "./notes-workspace";
import { SearchWorkspace } from "./search-workspace";
import { MaintenanceWorkspace } from "./maintenance-workspace";
import { CalendarWorkspace } from "./calendar-workspace";
import { FinanceWorkspace } from "./finance-workspace";
import { MediaWorkspace } from "./media-workspace";
import { PluginsWorkspace } from "./plugins-workspace";
import { FilesWorkspace } from "./files-workspace";
import { ProjectsWorkspace } from "./projects-workspace";
import { GitWorkspace } from "./git-workspace";
import { DockerWorkspace } from "./docker-workspace";
import { NotificationSettingsWorkspace } from "./notification-settings";
import { LockedState, StatusCard } from "./ui/status-card";
import type { User } from "../lib/auth";

const navigation = [
  { label: "Overview", icon: "◈", available: true },
  { label: "Assistant", icon: "✦", available: true },
  { label: "Tasks", icon: "□", available: true },
  { label: "Notifications", icon: "♢", available: true },
  { label: "Notes", icon: "▤", available: true },
  { label: "Search", icon: "⌕", available: true },
  { label: "Calendar", icon: "▦", available: true },
  { label: "Finance", icon: "₿", available: true },
  { label: "Media", icon: "▣", available: true },
  { label: "Plugins", icon: "◇", available: true },
  { label: "Maintenance", icon: "⚙", available: true },
  { label: "Files", icon: "▤", available: true },
  { label: "Projects", icon: "◈", available: true },
  { label: "Git", icon: "⌘", available: true },
  { label: "Docker", icon: "▣", available: true },
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
  const [activeView, setActiveView] = useState<"overview" | "assistant" | "tasks" | "notifications" | "notes" | "search" | "calendar" | "finance" | "media" | "plugins" | "maintenance" | "files" | "projects" | "git" | "docker">("overview");
  const [noteToOpen, setNoteToOpen] = useState<string | null>(null);

  function viewKey(label: string): typeof activeView {
    return label.toLowerCase() as typeof activeView;
  }

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
      {mobileNavOpen && <button aria-label="Close navigation" className="mobile-nav-backdrop" onClick={() => setMobileNavOpen(false)} type="button" />}
      <aside aria-label="Workspace navigation" className={`sidebar${mobileNavOpen ? " mobile-open" : ""}`} id="mobile-navigation">
        <div className="brand">
          <div className="brand-mark">N</div>
          <div><strong>NexusOS</strong><span>Personal command center</span></div>
        </div>
        <nav aria-label="Primary navigation" className="nav-list">
          <p className="eyebrow">Workspace</p>
          {navigation.map((item) => item.available ? (() => {
            const itemView = viewKey(item.label);
            const active = itemView === activeView;
            return <button aria-current={active ? "page" : undefined} className={`nav-item${active ? " active" : ""}`} key={item.label} onClick={() => { setActiveView(itemView); setMobileNavOpen(false); }} type="button">
              <span aria-hidden="true" className="nav-icon">{item.icon}</span>{item.label}{active && <span className="active-dot" />}
            </button>;
          })() : (
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
            <div><p className="breadcrumb">Workspace / {activeView === "assistant" ? "Assistant" : activeView === "tasks" ? "Tasks" : activeView === "notifications" ? "Notifications" : activeView === "notes" ? "Notes" : activeView === "search" ? "Search" : activeView === "calendar" ? "Calendar" : activeView === "finance" ? "Finance" : activeView === "media" ? "Media" : activeView === "plugins" ? "Plugins" : activeView === "maintenance" ? "Maintenance" : activeView === "files" ? "Files" : activeView === "projects" ? "Projects" : activeView === "git" ? "Git" : activeView === "docker" ? "Docker" : "Overview"}</p><h1>{activeView === "assistant" ? "Your assistant workspace." : activeView === "tasks" ? "Make progress visible." : activeView === "notifications" ? "Stay in the loop." : activeView === "notes" ? "Capture what matters." : activeView === "search" ? "Find your sources." : activeView === "calendar" ? "Make time visible." : activeView === "finance" ? "Know your numbers." : activeView === "media" ? "See your library." : activeView === "plugins" ? "Extend your command center safely." : activeView === "maintenance" ? "Keep your host healthy." : activeView === "files" ? "See what is changing." : activeView === "projects" ? "Your projects, in one place." : activeView === "git" ? "Review repository status." : activeView === "docker" ? "Inspect your containers." : `Good morning, ${user.username}.`}</h1></div>
          </div>
          <div className="topbar-actions">
            <NotificationCenter />
            <button aria-label="Open command palette" className="shortcut-button" onClick={() => setPaletteOpen(true)} type="button"><span>⌘ K</span><span className="shortcut-label">Commands</span></button>
            <ThemeToggle />
            <button aria-label="Sign out" className="avatar" onClick={signOut} type="button">↪</button>
          </div>
        </header>

        {activeView === "assistant" ? <AssistantWorkspace /> : activeView === "tasks" ? <TaskWorkspace /> : activeView === "notifications" ? <NotificationSettingsWorkspace /> : activeView === "notes" ? <NotesWorkspace initialNoteId={noteToOpen} onSearch={() => setActiveView("search")} /> : activeView === "search" ? <SearchWorkspace onBack={() => setActiveView("notes")} onOpenNote={(id) => { setNoteToOpen(id); setActiveView("notes"); }} /> : activeView === "calendar" ? <CalendarWorkspace /> : activeView === "finance" ? <FinanceWorkspace /> : activeView === "media" ? <MediaWorkspace /> : activeView === "plugins" ? <PluginsWorkspace /> : activeView === "maintenance" ? <MaintenanceWorkspace /> : activeView === "files" ? <FilesWorkspace /> : activeView === "projects" ? <ProjectsWorkspace /> : activeView === "git" ? <GitWorkspace /> : activeView === "docker" ? <DockerWorkspace /> : <>
        <div className="hero-card">
          <div className="hero-copy">
            <span className="status-pill"><span /> NexusOS v1.1 ready</span>
            <h2>Your digital life, <em>connected.</em></h2>
            <p>Your private workspace is authenticated and ready. The shell keeps deferred capabilities visible without pretending they are live.</p>
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
          <StatusCard action={<span className="lock-label">v1.0 foundation live</span>} description="The assistant gateway is available with owned conversations, bounded provider calls, and read-only system tools." eyebrow="Now available" icon="✦" title="Your assistant is ready" />
        </section>

        <section aria-label="Workspace modules" className="locked-grid">
          <LockedState description="Notes and scoped search are available from the workspace navigation." title="Notes" />
        </section>

        </>}
        <footer>Local-first. Private by default. <span>NexusOS 1.3.0</span></footer>
      </section>
      {paletteOpen && <CommandPalette onClose={() => setPaletteOpen(false)} onLogout={signOut} onSearch={() => { setPaletteOpen(false); setActiveView("search"); }} onToggleTheme={() => { toggleTheme(); setPaletteOpen(false); }} />}
    </main>
  );
}
