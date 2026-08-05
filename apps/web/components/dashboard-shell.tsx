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
import { StatusCard } from "./ui/status-card";
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

type NavItem = { label: string; icon: string; view: WorkspaceView; hint?: string };

const navGroups: Array<{ title: string; items: NavItem[] }> = [
  {
    title: "Home",
    items: [
      { label: "Overview", icon: "◈", view: "overview", hint: "Dashboard" },
      { label: "Assistant", icon: "✦", view: "assistant", hint: "Chat" },
    ],
  },
  {
    title: "Work",
    items: [
      { label: "Tasks", icon: "□", view: "tasks" },
      { label: "Notes", icon: "▤", view: "notes" },
      { label: "Sources", icon: "◇", view: "sources" },
      { label: "Search", icon: "⌕", view: "search" },
      { label: "Calendar", icon: "▦", view: "calendar" },
      { label: "Finance", icon: "₿", view: "finance" },
    ],
  },
  {
    title: "System",
    items: [
      { label: "Notifications", icon: "♢", view: "notifications" },
      { label: "Media", icon: "▣", view: "media" },
      { label: "Files", icon: "▤", view: "files" },
      { label: "Projects", icon: "◈", view: "projects" },
      { label: "Git", icon: "⌘", view: "git" },
      { label: "Docker", icon: "▣", view: "docker" },
      { label: "Plugins", icon: "◇", view: "plugins" },
      { label: "Maintenance", icon: "⚙", view: "maintenance" },
    ],
  },
];

const quickModules: Array<{ label: string; detail: string; icon: string; view: WorkspaceView }> = [
  { label: "Assistant", detail: "Private chat with your model", icon: "✦", view: "assistant" },
  { label: "Tasks", detail: "Track work and reminders", icon: "□", view: "tasks" },
  { label: "Notes", detail: "Capture and search knowledge", icon: "▤", view: "notes" },
  { label: "System", detail: "Live Pi telemetry", icon: "◎", view: "overview" },
  { label: "Files", detail: "Approved workspace roots", icon: "▤", view: "files" },
  { label: "Maintenance", detail: "Backups and host actions", icon: "⚙", view: "maintenance" },
];

export function DashboardShell({ user, onLogout }: { user: User; onLogout: () => void }) {
  const { toggleTheme } = useTheme();
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [activeView, setActiveView] = useState<WorkspaceView>("overview");
  const [noteToOpen, setNoteToOpen] = useState<string | null>(null);
  const isOwner = user.permissions.includes("admin.manage_users");
  const groups = isOwner
    ? [
        ...navGroups,
        {
          title: "Admin",
          items: [{ label: "Admin", icon: "★", view: "admin" as WorkspaceView, hint: "Console" }],
        },
      ]
    : navGroups;

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

  function go(view: WorkspaceView) {
    setActiveView(view);
    setMobileNavOpen(false);
  }

  const initial = user.username.slice(0, 1).toUpperCase();

  return (
    <main className={`shell${activeView === "admin" ? " shell-admin" : ""}${activeView === "assistant" ? " shell-chat" : ""}`}>
      <a className="skip-link" href="#main-content">
        Skip to main content
      </a>
      {mobileNavOpen ? (
        <button aria-label="Close navigation" className="mobile-nav-backdrop" onClick={() => setMobileNavOpen(false)} type="button" />
      ) : null}

      {activeView !== "admin" ? (
        <aside aria-label="Workspace navigation" className={`sidebar${mobileNavOpen ? " mobile-open" : ""}`} id="mobile-navigation">
          <div className="brand">
            <div className="brand-mark">N</div>
            <div>
              <strong>NexusOS</strong>
              <span>Personal control plane</span>
            </div>
          </div>
          <nav aria-label="Primary navigation" className="nav-list">
            {groups.map((group) => (
              <div className="nav-group" key={group.title}>
                <p className="eyebrow">{group.title}</p>
                {group.items.map((item) => {
                  const active = item.view === activeView;
                  return (
                    <button
                      aria-current={active ? "page" : undefined}
                      className={`nav-item${active ? " active" : ""}`}
                      key={item.label}
                      onClick={() => go(item.view)}
                      type="button"
                    >
                      <span aria-hidden="true" className="nav-icon">
                        {item.icon}
                      </span>
                      {item.label}
                      {active ? <span className="active-dot" /> : null}
                    </button>
                  );
                })}
              </div>
            ))}
          </nav>
          <div className="sidebar-footer">
            <div className="connection-dot" />
            <div>
              <strong>{user.username}</strong>
              <span>{isOwner ? "Owner · local mode" : "Member · local mode"}</span>
            </div>
          </div>
        </aside>
      ) : null}

      <section className={`content${activeView === "admin" ? " content-admin" : ""}${activeView === "assistant" ? " content-chat" : ""}`} id="main-content">
        {activeView !== "admin" && activeView !== "assistant" ? (
          <header className="topbar">
            <div className="mobile-topbar-row">
              <button
                aria-controls="mobile-navigation"
                aria-expanded={mobileNavOpen}
                aria-label="Toggle navigation"
                className="menu-button"
                onClick={() => setMobileNavOpen((open) => !open)}
                type="button"
              >
                ☰
              </button>
              <div>
                <p className="breadcrumb">{breadcrumbForView(activeView)}</p>
                <h1>{titleForView(activeView)}</h1>
              </div>
            </div>
            <div className="topbar-actions">
              <span className="user-chip" title={user.username}>
                <span className="user-chip-avatar" aria-hidden="true">
                  {initial}
                </span>
                {user.username}
              </span>
              <NotificationCenter />
              <button aria-label="Open command palette" className="shortcut-button" onClick={() => setPaletteOpen(true)} type="button">
                <span>⌘ K</span>
                <span className="shortcut-label">Commands</span>
              </button>
              <ThemeToggle />
              <button aria-label="Sign out" className="avatar" onClick={signOut} type="button">
                ↪
              </button>
            </div>
          </header>
        ) : null}

        {activeView === "assistant" ? (
          <AssistantWorkspace
            onOpenAdmin={isOwner ? () => setActiveView("admin") : undefined}
            onOpenHome={() => setActiveView("overview")}
            onOpenNote={(id) => {
              setNoteToOpen(id);
              setActiveView("notes");
            }}
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
          <SearchWorkspace
            onBack={() => setActiveView("notes")}
            onOpenNote={(id) => {
              setNoteToOpen(id);
              setActiveView("notes");
            }}
          />
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
                <span className="status-pill">
                  <span /> System online
                </span>
                <h2>
                  Your private <em>command center.</em>
                </h2>
                <p>
                  NexusOS keeps AI, services, and operations on your Raspberry Pi—local-first, private by default, and ready when you are.
                </p>
                <div className="hero-actions">
                  {isOwner ? (
                    <button className="primary-button" onClick={() => setActiveView("admin")} type="button">
                      Open Admin
                    </button>
                  ) : null}
                  <button className="refresh-button" onClick={() => setActiveView("assistant")} type="button">
                    Open Assistant
                  </button>
                  <button className="refresh-button" onClick={() => setPaletteOpen(true)} type="button">
                    Commands ⌘K
                  </button>
                </div>
              </div>
              <div aria-hidden="true" className="hero-orbit">
                <div className="orbit orbit-one">
                  <span>AI</span>
                </div>
                <div className="orbit orbit-two">
                  <span>SYS</span>
                </div>
                <div className="orbit orbit-three">
                  <span>✦</span>
                </div>
                <div className="core">N</div>
              </div>
            </div>

            {isOwner ? (
              <section aria-labelledby="status-heading" className="section-block">
                <div className="section-heading">
                  <div>
                    <p className="eyebrow">Operations</p>
                    <h2 id="status-heading">System status</h2>
                  </div>
                  <span className="updated">Authenticated locally</span>
                </div>
                <AdminStatusPanel onOpenAdmin={() => setActiveView("admin")} />
              </section>
            ) : null}

            <SystemOverview />

            <section aria-labelledby="modules-heading" className="section-block">
              <div className="section-heading">
                <div>
                  <p className="eyebrow">Workspace</p>
                  <h2 id="modules-heading">Jump to a module</h2>
                </div>
                <span className="updated">Everything stays on your Pi</span>
              </div>
              <div className="quick-module-grid">
                {quickModules.map((item) => (
                  <button className="quick-module" key={item.label} onClick={() => go(item.view)} type="button">
                    <span aria-hidden="true" className="quick-module-icon">
                      {item.icon}
                    </span>
                    <strong>{item.label}</strong>
                    <span>{item.detail}</span>
                  </button>
                ))}
              </div>
            </section>

            <section aria-labelledby="ready-heading" className="section-block">
              <div className="section-heading">
                <div>
                  <p className="eyebrow">Assistant</p>
                  <h2 id="ready-heading">Ready when you are</h2>
                </div>
              </div>
              <StatusCard
                action={
                  <button className="primary-button" onClick={() => setActiveView("assistant")} type="button">
                    Open chat
                  </button>
                }
                description="Conversations stay private. Models run through your configured provider; tools that change the system ask for confirmation."
                eyebrow="Now available"
                icon="✦"
                title="Nexus Assistant is online"
              />
            </section>
          </>
        )}

        {activeView !== "admin" ? (
          <footer>
            <span>Local-first · Private by default</span>
            <span>NexusOS 1.5.0</span>
          </footer>
        ) : null}
      </section>

      {paletteOpen ? (
        <CommandPalette
          onAdmin={
            isOwner
              ? () => {
                  setPaletteOpen(false);
                  setActiveView("admin");
                }
              : undefined
          }
          onClose={() => setPaletteOpen(false)}
          onLogout={signOut}
          onSearch={() => {
            setPaletteOpen(false);
            setActiveView("search");
          }}
          onToggleTheme={() => {
            toggleTheme();
            setPaletteOpen(false);
          }}
        />
      ) : null}
    </main>
  );
}
