"use client";

import { useEffect, useRef, useState, type KeyboardEvent } from "react";

type Command = {
  id: string;
  label: string;
  hint: string;
  icon: string;
  action: () => void;
};

type CommandPaletteProps = {
  onClose: () => void;
  onLogout: () => void;
  onToggleTheme: () => void;
  onSearch: () => void;
  onAdmin?: () => void;
};

export function CommandPalette({ onClose, onLogout, onToggleTheme, onSearch, onAdmin }: CommandPaletteProps) {
  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const paletteRef = useRef<HTMLElement>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    previousFocusRef.current = document.activeElement as HTMLElement | null;
    inputRef.current?.focus();
    return () => previousFocusRef.current?.focus();
  }, []);

  const commands: Command[] = [
    { id: "overview", label: "Open overview", hint: "Workspace", icon: "◈", action: onClose },
    { id: "search", label: "Search notes", hint: "Sources", icon: "⌕", action: onSearch },
    ...(onAdmin ? [{ id: "admin", label: "Open Admin / NVIDIA NIM", hint: "Owner setup", icon: "★", action: onAdmin }] : []),
    { id: "theme", label: "Toggle appearance", hint: "Theme", icon: "☼", action: onToggleTheme },
    { id: "logout", label: "Sign out", hint: "Account", icon: "↪", action: onLogout },
  ];
  const filteredCommands = commands.filter((command) =>
    `${command.label} ${command.hint}`.toLowerCase().includes(query.trim().toLowerCase()),
  );

  useEffect(() => {
    setSelectedIndex(0);
  }, [query]);

  function handlePaletteKeyDown(event: KeyboardEvent<HTMLElement>) {
    if (event.key === "Escape") {
      event.preventDefault();
      onClose();
      return;
    }
    if (event.key === "ArrowDown" && filteredCommands.length > 0) {
      event.preventDefault();
      setSelectedIndex((index) => (index + 1) % filteredCommands.length);
      return;
    }
    if (event.key === "ArrowUp" && filteredCommands.length > 0) {
      event.preventDefault();
      setSelectedIndex((index) => (index - 1 + filteredCommands.length) % filteredCommands.length);
      return;
    }
    if (event.key === "Enter" && filteredCommands[selectedIndex]) {
      event.preventDefault();
      filteredCommands[selectedIndex].action();
      return;
    }
    if (event.key !== "Tab") return;

    const focusable = paletteRef.current?.querySelectorAll<HTMLElement>(
      "button:not([disabled]), input:not([disabled])",
    );
    if (!focusable || focusable.length === 0) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  return (
    <div className="palette-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <section aria-labelledby="palette-heading" aria-modal="true" className="command-palette" onKeyDown={handlePaletteKeyDown} ref={paletteRef} role="dialog">
        <div className="palette-search">
          <span aria-hidden="true">⌕</span>
          <input
            aria-activedescendant={filteredCommands[selectedIndex] ? `command-${filteredCommands[selectedIndex].id}` : undefined}
            aria-controls="command-list"
            aria-expanded="true"
            aria-label="Search commands"
            onChange={(event) => setQuery(event.target.value)}
            role="combobox"
            placeholder="Search your workspace"
            ref={inputRef}
            value={query}
          />
          <kbd>ESC</kbd>
        </div>
        <div className="palette-content">
          <p className="eyebrow" id="palette-heading">Quick actions</p>
          {filteredCommands.length > 0 ? (
            <div className="command-list" id="command-list" role="listbox">
              {filteredCommands.map((command, index) => (
                <button
                  aria-selected={selectedIndex === index}
                  className={`command-item${selectedIndex === index ? " selected" : ""}`}
                  id={`command-${command.id}`}
                  key={command.id}
                  onClick={command.action}
                  role="option"
                  type="button"
                >
                  <span aria-hidden="true" className="command-icon">{command.icon}</span>
                  <span>
                    <strong>{command.label}</strong>
                    <small>{command.hint}</small>
                  </span>
                  <span aria-hidden="true" className="command-arrow">↵</span>
                </button>
              ))}
            </div>
          ) : (
            <div className="empty-state compact-state">
              <span className="empty-icon" aria-hidden="true">⌕</span>
              <strong>No commands found</strong>
              <span>Try a different search.</span>
            </div>
          )}
        </div>
        <footer className="palette-footer"><span>↑↓ navigate</span><span>↵ select</span><span>esc close</span></footer>
      </section>
    </div>
  );
}
