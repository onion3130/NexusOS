const navigation = [
  { label: "Overview", icon: "◈", active: true },
  { label: "Assistant", icon: "✦", active: false },
  { label: "Tasks", icon: "□", active: false },
  { label: "Notes", icon: "▤", active: false },
];

const metrics = [
  { label: "System status", value: "Foundation ready", detail: "Health endpoints online", tone: "green" },
  { label: "AI provider", value: "Disabled", detail: "Enable when configured", tone: "purple" },
  { label: "Storage", value: "SQLite planned", detail: "Persistence is Milestone 2", tone: "blue" },
];

export default function Home() {
  return (
    <main className="shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">N</div>
          <div>
            <strong>NexusOS</strong>
            <span>Personal command center</span>
          </div>
        </div>

        <nav aria-label="Primary navigation" className="nav-list">
          <p className="eyebrow">Workspace</p>
          {navigation.map((item) => (
            <a className={`nav-item${item.active ? " active" : ""}`} href="#" key={item.label}>
              <span aria-hidden="true" className="nav-icon">{item.icon}</span>
              {item.label}
              {item.active && <span className="active-dot" aria-label="Current page" />}
            </a>
          ))}
        </nav>

        <div className="sidebar-footer">
          <div className="connection-dot" />
          <div>
            <strong>Local mode</strong>
            <span>Private by default</span>
          </div>
        </div>
      </aside>

      <section className="content">
        <header className="topbar">
          <div>
            <p className="breadcrumb">Workspace / Overview</p>
            <h1>Good morning, owner.</h1>
          </div>
          <div className="topbar-actions">
            <button className="icon-button" aria-label="Open command palette">⌘ K</button>
            <button className="avatar" aria-label="Open profile">O</button>
          </div>
        </header>

        <div className="hero-card">
          <div className="hero-copy">
            <span className="status-pill"><span /> Milestone 1 foundation</span>
            <h2>Your digital life, <em>connected.</em></h2>
            <p>NexusOS is ready for its first building blocks. The shell, secure configuration, and health boundary are in place.</p>
            <button className="primary-button">Explore the foundation <span aria-hidden="true">→</span></button>
          </div>
          <div className="hero-orbit" aria-hidden="true">
            <div className="orbit orbit-one"><span>AI</span></div>
            <div className="orbit orbit-two"><span>SYS</span></div>
            <div className="orbit orbit-three"><span>✦</span></div>
            <div className="core">N</div>
          </div>
        </div>

        <section className="section-block" aria-labelledby="status-heading">
          <div className="section-heading">
            <div>
              <p className="eyebrow">At a glance</p>
              <h2 id="status-heading">System status</h2>
            </div>
            <span className="updated">Updated just now</span>
          </div>
          <div className="metric-grid">
            {metrics.map((metric) => (
              <article className="metric-card" key={metric.label}>
                <div className={`metric-indicator ${metric.tone}`} />
                <p>{metric.label}</p>
                <strong>{metric.value}</strong>
                <span>{metric.detail}</span>
              </article>
            ))}
          </div>
        </section>

        <section className="next-card" aria-labelledby="next-heading">
          <div className="next-icon">✦</div>
          <div>
            <p className="eyebrow">Next up</p>
            <h2 id="next-heading">Build your personal workspace</h2>
            <p>Authentication and persistence are next. Once approved, your private dashboard will become a real place for tasks, notes, and conversations.</p>
          </div>
          <span className="lock-label">Locked until Milestone 2</span>
        </section>

        <footer>Local-first. Private by default. <span>NexusOS 0.1.0</span></footer>
      </section>
    </main>
  );
}
