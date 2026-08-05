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
import { SourcesWorkspace } from "./sources-workspace";
import { NotificationSettingsWorkspace } from "./notification-settings";
import { AdminStatusPanel } from "./admin-status-panel";
import { AdminWorkspace } from "./admin-workspace";
import { LockedState, StatusCard } from "./ui/status-card";
import type { User } from "../lib/auth";

type WorkspaceView =
  | "overview"
  | "assistant"
  | "tasks"
  | "notifications"
  | "notes"
  | "sources"
  | "search"
  | "calendar"
  | "finance"
  | "media"
  | "plugins"
  | "maintenance"
  | "files"
  | "projects"
  | "git"
  | "docker"
  | "admin";

const baseNavigation = [
  { label: "Overview", icon: "◈", available: true },
  { label: "Assistant", icon: "✦", available: true },
  { label: "Tasks", icon: "□", available: true },
  { label: "Notifications", icon: "♢", available: true },
  { label: "Notes", icon: "▤", available: true },
  { label: "Sources", icon: "◇", available: true },
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

export function DashboardShell({ user, onLogout }: { user: User; onLogout: () => void }) {
  const { toggleTheme } = useTheme();
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [activeView, setActiveView] = useState<WorkspaceView>("overview");
  const [noteToOpen, setNoteToOpen] = useState<string | null>(null);
  const isOwner = user.permissions.includes("admin.manage_users");
  const navigation = isOwner
    ? [...baseNavigation, { label: "Admin", icon: "★", available: true }]
    : baseNavigation;

  function viewKey(label: string): WorkspaceView {
    return label.toLowerCase() as WorkspaceView;
  }

  function titleForView(view: WorkspaceView): string {
    switch (view) {
      case "assistant":
        return "Assistant";
      case "tasks":
        return "Tasks";
      case "notifications":
        return "Notifications";
      case "notes":
        return "Notes";
      case "sources":
        return "Sources";
      case "search":
        return "Search";
      case "calendar":
        return "Calendar";
      case "finance":
        return "Finance";
      case "media":
        return "Media";
      case "plugins":
        return "Plugins";
      case "maintenance":
        return "Maintenance";
      case "files":
        return "Files";
      case "projects":
        return "Projects";
      case "git":
        return "Git";
      case "docker":
        return "Docker";
      case "admin":
        return "Admin";
      default:
        return `Welcome back, ${user.username}`;
    }
  }

  function breadcrumbForView(view: WorkspaceView): string {
    if (view === "overview") return "Workspace / Overview";
    return `Workspace / ${view.charAt(0).toUpperCase()}${view.slice(1)}`;
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
    <main className={`shell${activeView === "admin" ? " shell-admin" : ""}${activeView === "assistant" ? " shell-chat" : ""}`}>
      <a className="skip-link" href="#main-content">Skip to main content</a>
      {mobileNavOpen && <button aria-label="Close navigation" className="mobile-nav-backdrop" onClick={() => setMobileNavOpen(false)} type="button" />}
      {activeView !== "admin" && <aside aria-label="Workspace navigation" className={`sidebar${mobileNavOpen ? " mobile-open" : ""}`} id="mobile-navigation">        <div className="brand">
          <div className="brand-mark">N</div>
          <div><strong>NexusOS</strong><span>Homelab control plane</span></div>
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
      </aside>}

      <section className={`content${activeView === "admin" ? " content-admin" : ""}`} id="main-content">
        {activeView !== "admin" && (
        <header className="topbar">
          <div className="mobile-topbar-row">
            <button aria-controls="mobile-navigation" aria-expanded={mobileNavOpen} aria-label="Toggle navigation" className="menu-button" onClick={() => setMobileNavOpen((open) => !open)} type="button">☰</button>
            <div>
              <p className="breadcrumb">{breadcrumbForView(activeView)}</p>
              <h1>{titleForView(activeView)}</h1>
            </div>
          </div>
          <div className="topbar-actions">
            <NotificationCenter />
            <button aria-label="Open command palette" className="shortcut-button" onClick={() => setPaletteOpen(true)} type="button"><span>⌘ K</span><span className="shortcut-label">Commands</span></button>
            <ThemeToggle />
            <button aria-label="Sign out" className="avatar" onClick={signOut} type="button">↪</button>
          </div>
        </header>
        )}

        {activeView === "assistant" ? (
          <AssistantWorkspace
            onOpenAdmin={isOwner ? () => setActiveView("admin") : undefined}
            onOpenNote={(id) => { setNoteToOpen(id); setActiveView("notes"); }}
            onOpenSource={() => setActiveView("sources")}
          />
        ) : activeView === "tasks" ? (
          <TaskWorkspace />
        ) : activeView === "notifications" ? (
          <NotificationSettingsWorkspace />
        ) : activeView === "notes" ? (
          <NotesWorkspace initialNoteId={noteToOpen} onSearch={() => setActiveView("search")} />
        ) : activeView === "sources" ? (
          <SourcesWorkspace />
        ) : activeView === "search" ? (
          <SearchWorkspace onBack={() => setActiveView("notes")} onOpenNote={(id) => { setNoteToOpen(id); setActiveView("notes"); }} />
        ) : activeView === "calendar" ? (
          <CalendarWorkspace />
        ) : activeView === "finance" ? (
          <FinanceWorkspace />
        ) : activeView === "media" ? (
          <MediaWorkspace />
        ) : activeView === "plugins" ? (
          <PluginsWorkspace />
        ) : activeView === "maintenance" ? (
          <MaintenanceWorkspace />
        ) : activeView === "files" ? (
          <FilesWorkspace />
        ) : activeView === "projects" ? (
          <ProjectsWorkspace />
        ) : activeView === "git" ? (
          <GitWorkspace />
        ) : activeView === "docker" ? (
          <DockerWorkspace />
        ) : activeView === "admin" && isOwner ? (
          <AdminWorkspace
            onLogout={signOut}
            onNavigate={(target) => setActiveView(target === "overview" ? "overview" : target)}
            onOpenAssistant={() => setActiveView("assistant")}
            user={user}
          />
        ) : (
          <>
            <div className="hero-card">
              <div className="hero-copy">
                <span className="status-pill"><span /> System online</span>
                <h2>Your private <em>command center.</em></h2>
                <p>Local-first OS for your Pi — modern assistant, services, and tools in one clean dashboard.</p>
                <div className="hero-actions">
                  {isOwner && (
                    <button className="primary-button" onClick={() => setActiveView("admin")} type="button">
                      Open Admin
                    </button>
                  )}
                  <button className="refresh-button" onClick={() => setActiveView("assistant")} type="button">
                    Open Assistant
                  </button>
                  <button className="refresh-button" onClick={() => setPaletteOpen(true)} type="button">
                    Commands ⌘K
                  </button>
                </div>
              </div>
              <div aria-hidden="true" className="hero-orbit">
                <div className="orbit orbit-one"><span>AI</span></div>
                <div className="orbit orbit-two"><span>SYS</span></div>
                <div className="orbit orbit-three"><span>✦</span></div>
                <div className="core">N</div>
              </div>
            </div>

            {isOwner && (
              <section aria-labelledby="status-heading" className="section-block">
                <div className="section-heading">
                  <div>
                    <p className="eyebrow">At a glance</p>
                    <h2 id="status-heading">System status</h2>
                  </div>
                  <span className="updated">Authenticated locally</span>
                </div>
                <AdminStatusPanel onOpenAdmin={() => setActiveView("admin")} />
              </section>
            )}

            <SystemOverview />

            <section aria-labelledby="next-heading" className="section-block">
              <div className="section-heading">
                <div>
                  <p className="eyebrow">Workspace status</p>
                  <h2 id="next-heading">Build your personal workspace</h2>
                </div>
                <span className="updated">No feature data loaded</span>
              </div>
              <StatusCard
                action={<span className="lock-label">v1.0 foundation live</span>}
                description="The assistant gateway is available with owned conversations, bounded provider calls, and read-only system tools."
                eyebrow="Now available"
                icon="✦"
                title="Your assistant is ready"
              />
            </section>

            <section aria-label="Workspace modules" className="locked-grid">
              <LockedState description="Notes and scoped search are available from the workspace navigation." title="Notes" />
            </section>
          </>
        )}
        {activeView !== "admin" && <footer>Local-first. Private by default. <span>NexusOS 1.3.2</span></footer>}
      </section>
      {paletteOpen && (
        <CommandPalette
          onAdmin={isOwner ? () => { setPaletteOpen(false); setActiveView("admin"); } : undefined}
          onClose={() => setPaletteOpen(false)}
          onLogout={signOut}
          onSearch={() => { setPaletteOpen(false); setActiveView("search"); }}
          onToggleTheme={() => { toggleTheme(); setPaletteOpen(false); }}
        />
      )}
    </main>
  );
}
