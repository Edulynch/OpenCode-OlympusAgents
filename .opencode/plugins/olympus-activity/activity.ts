// Pure presentation logic; OpenCode's session store remains the source of truth.
type Session = { id: string; parentID?: string | null; agent?: string; title?: string }
type Row = { id: string; agent: string; title: string }

const names: Record<string, string> = {
  kael: "Kael", veyra: "Veyra", orin: "Orin", kovan: "Kovan",
  nox: "Nox", vera: "Vera", sorin: "Sorin", maintenance: "Maintenance",
}

function label(agent?: string): string {
  const id = agent?.trim() || ""
  return names[id.toLowerCase()] ?? (id || "Subagent")
}

function title(session: Session): string {
  const value = (session.title || "").replace(/\s+/g, " ").trim()
  if (!value || /^(?:(?:new |child )?session|(?:subagent )?task|untitled)(?: \d+)?$/i.test(value)) {
    return session.agent?.toLowerCase() === "maintenance" ? "Maintenance task" : "Subagent task"
  }
  return value.length > 64 ? value.slice(0, 61) + "…" : value
}

export function activeChildren(
  currentID: string,
  sessions: readonly Session[],
  status: (id: string) => string,
): Row[] {
  const current = sessions.find((session) => session.id === currentID)
  if (!current || current.parentID != null) return []
  return sessions.filter((session) => session.parentID === currentID && status(session.id) === "running")
    .map((session) => ({ id: session.id, agent: label(session.agent), title: title(session) }))
}
