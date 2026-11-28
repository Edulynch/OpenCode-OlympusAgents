// Pure presentation logic; OpenCode's session store remains the source of truth.
type Session = { id: string; parentID?: string | null; agent?: string; title?: string }
type Row = { id: string; agent: string; title: string }
export type Job = { kind?: string; sessionID?: string; childSessionID?: string; status?: string }
export type ActivityState = { observedChildren: ReadonlySet<string>; peakActive: number }
export type ActivitySnapshot = {
  observed: number
  active: number
  peak: number
  visibleRows: Row[]
  state: ActivityState
}

const jobKinds = new Set(["shell", "subagent", "image", "video", "codemode"])

const names: Record<string, string> = {
// {{display_names}}
}

function label(agent?: string): string {
  const id = agent?.trim() || ""
  return names[id.toLowerCase()] ?? (id || "Subagent")
}

function title(session: Session): string {
  const value = (session.title || "").replace(/\s+/g, " ").trim()
  if (!value || /^(?:(?:new |child )?session|(?:subagent )?task|untitled)(?: \d+)?$/i.test(value)) {
    return "Subagent task"
  }
  return value.length > 64 ? value.slice(0, 61) + "…" : value
}

function jobOwner(job: Job, children: Set<string>, sessions: Map<string, Session>): string | undefined {
  if (job.status !== "running" || !jobKinds.has(job.kind ?? "")) return
  let current: string | null | undefined = job.kind === "subagent" ? job.childSessionID : job.sessionID
  const seen = new Set<string>()
  while (current && !seen.has(current)) {
    if (children.has(current)) return current
    seen.add(current)
    current = sessions.get(current)?.parentID ??
      (job.kind === "subagent" && current === job.childSessionID ? job.sessionID : undefined)
  }
}

export function activeChildren(
  currentID: string,
  sessions: readonly Session[],
  status: (id: string) => string,
  jobs: readonly Job[] = [],
): Row[] {
  const current = sessions.find((session) => session.id === currentID)
  if (!current || current.parentID != null) return []
  const children = new Set(sessions.filter((session) => session.parentID === currentID).map((session) => session.id))
  const sessionByID = new Map(sessions.map((session) => [session.id, session] as const))
  const jobOwners = new Set(jobs.map((job) => jobOwner(job, children, sessionByID))
    .filter((owner): owner is string => owner !== undefined))
  return sessions.filter((session) => session.parentID === currentID &&
      (status(session.id) === "running" || jobOwners.has(session.id)))
    .map((session) => ({ id: session.id, agent: label(session.agent), title: title(session) }))
}

export function activitySnapshot(
  currentID: string,
  sessions: readonly Session[],
  status: (id: string) => string,
  jobs: readonly Job[] = [],
  previous: ActivityState = { observedChildren: new Set(), peakActive: 0 },
): ActivitySnapshot {
  const current = sessions.find((session) => session.id === currentID)
  const observedChildren = new Set(previous.observedChildren)
  if (current && current.parentID == null) {
    for (const session of sessions) {
      if (session.parentID === currentID) observedChildren.add(session.id)
    }
  }
  const activeRows = activeChildren(currentID, sessions, status, jobs)
  const peakActive = Math.max(previous.peakActive, activeRows.length)
  return {
    observed: observedChildren.size,
    active: activeRows.length,
    peak: peakActive,
    visibleRows: activeRows.slice(0, 4),
    state: { observedChildren, peakActive },
  }
}
