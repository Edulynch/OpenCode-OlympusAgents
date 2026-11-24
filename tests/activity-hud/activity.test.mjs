import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import { test } from "node:test"
import { activeChildren } from "../../.opencode/plugins/olympus-activity/activity.ts"

const root = { id: "root", agent: "kael" }
const child = (id, agent, title = "Inspect repository", parentID = "root") =>
  ({ id, parentID, agent, title })
const status = (running) => (id) => running.includes(id) ? "running" : "idle"

test("H4 root-only and direct children only", () => {
  const sessions = [root, child("a", "orin"), child("nested", "nox", "Validate", "a")]
  assert.deepEqual(activeChildren("a", sessions, status(["nested"])), [])
  assert.deepEqual(activeChildren("root", sessions, status(["nested"])), [])
  assert.deepEqual(activeChildren("missing", sessions, status(["a"])), [])
})

test("H5 running direct children appear and disappear on native status transitions", () => {
  const sessions = [root, child("a", "orin"), child("b", "kovan")]
  assert.deepEqual(activeChildren("root", sessions, status(["a"])).map((row) => row.agent), ["Orin — The Architect"])
  assert.deepEqual(activeChildren("root", sessions, status(["b"])).map((row) => row.agent), ["Kovan — The Coder"])
  assert.deepEqual(activeChildren("root", sessions, status([])), [])
})

test("H5 idle direct child stays visible for its active shell job", () => {
  const sessions = [root, child("a", "nox")]
  const jobs = [{ kind: "shell", sessionID: "a", status: "running" }]
  assert.deepEqual(activeChildren("root", sessions, status([]), jobs).map((row) => row.id), ["a"])
})

test("H5 all v2.4 job kinds use their native ownership anchor", () => {
  const sessions = [root, child("a", "nox")]
  for (const kind of ["shell", "subagent", "image", "video", "codemode"]) {
    const job = kind === "subagent"
      ? { kind, sessionID: "root", childSessionID: "a", status: "running" }
      : { kind, sessionID: "a", status: "running" }
    assert.deepEqual(activeChildren("root", sessions, status([]), [job]).map((row) => row.id), ["a"], kind)
  }
})

test("H5 active subagent jobs belong to a represented direct-child tree, not extra rows", () => {
  const sessions = [root, child("a", "nox"), child("nested", "orin", "Nested work", "a")]
  const jobs = [{ kind: "subagent", sessionID: "root", childSessionID: "nested", status: "running" }]
  assert.deepEqual(activeChildren("root", sessions, status([]), jobs).map((row) => row.id), ["a"])
  assert.deepEqual(activeChildren("root", [root, child("a", "nox")], status([]), jobs), [])
})

test("H5 root-owned, unknown-family, settled, and missing-status jobs do not activate a child", () => {
  const sessions = [root, child("a", "nox")]
  const jobs = [
    { kind: "shell", sessionID: "root", status: "running" },
    { kind: "shell", sessionID: "a", status: "completed" },
    { kind: "automation", sessionID: "a", status: "running" },
    { kind: "image", sessionID: "a" },
  ]
  assert.deepEqual(activeChildren("root", sessions, status([]), jobs), [])
})

test("H5 multiple jobs produce one row per direct child and parent cycles terminate", () => {
  const sessions = [root, child("a", "nox"), child("cycle-a", "orin", "Cycle", "cycle-b"), child("cycle-b", "veyra", "Cycle", "cycle-a")]
  const jobs = [
    { kind: "shell", sessionID: "a", status: "running" },
    { kind: "shell", sessionID: "a", status: "running" },
    { kind: "shell", sessionID: "cycle-a", status: "running" },
  ]
  assert.deepEqual(activeChildren("root", sessions, status([]), jobs).map((row) => row.id), ["a"])
})

test("H6 duplicate sessions remain distinct rows", () => {
  const rows = activeChildren("root", [root, child("a", "unknown-role"), child("b", "unknown-role")], status(["a", "b"]))
  assert.deepEqual(rows.map((row) => row.id), ["a", "b"])
  assert.deepEqual(rows.map((row) => row.agent), ["unknown-role", "unknown-role"])
})

test("H7 fallback, truncation and Olympus display names", () => {
  const rows = activeChildren("root", [root, child("a", "unknown-role", "New session"), child("b", "veyra", "x".repeat(90))], status(["a", "b"]))
  assert.equal(rows[0].title, "Subagent task")
  assert.equal(rows[1].agent, "Veyra — The Explorer")
  assert.ok(rows[1].title.length <= 64)
})

test("H8 slot is passive and only reads native state", () => {
  const view = readFileSync(new URL("../../.opencode/plugins/olympus-activity/tui.tsx", import.meta.url), "utf8")
  assert.match(view, /append: "session\.composer\.top"/)
  assert.match(view, /context\.data\.session\.list\(\)/)
  assert.match(view, /context\.data\.session\.status\(id\)/)
  assert.match(view, /job\?\.list\(sessionID\)/)
  assert.doesNotMatch(view, /job\.(?:sync|invalidate)\(/)
  assert.doesNotMatch(view, /\b(?:onMouse\w*|onKey\w*|keymap|navigate|interrupt|cancel|setInterval|setTimeout|client\.)\b/)
  assert.match(view, /slice\(0, 4\)/)
})
